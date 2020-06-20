/*
Classical conditioning

Handles hardware for control of behavioral session.
Use with Python GUI "conditioning.py".

Example inputs:
3000+3000+3+1+1+3000+3000+60000+500+1000+500+1000+0+500+500+5000+0+500+0+100+50
3000+3000+3+1+0+45000+3000+120000+500+1000+500+1000+0+500+500+5000+0+500+0+100+50
*/


#include "Behavior.h"

#define IMGPINDUR 100     // Length of imaging signal pulse
#define CODEEND 48
#define STARTCODE 69
#define CODETRIAL 70
#define DELIM ","         // Delimiter used for serial communication


// Pins
const int pin_track_a = 2;
const int pin_track_b = 4;

const int pin_lick = 3;
const int pin_sol_0 = 5;
const int pin_sol_1 = 6;

const int pin_tone = 7;

const int pin_img_start = 9;
const int pin_img_stop  = 10;


// Output codes
const int code_end = 0;
const int code_lick = 1;
const int code_track = 2;
const int code_trial_start = 3;
const int code_cs_start = 4;
const int code_us_start = 5;

// Variables via serial
unsigned long pre_session;
unsigned long post_session;
int cs0_num;
int cs1_num;

boolean uniform_iti;
unsigned long mean_iti;
unsigned long min_iti;
unsigned long max_iti;
unsigned long pre_stim;
unsigned long post_stim;

unsigned int cs0_dur;
unsigned int cs0_freq;
unsigned int us0_delay;
unsigned int us0_dur;
unsigned int cs1_dur;
unsigned int cs1_freq;
unsigned int us1_delay;
unsigned int us1_dur;

boolean image_all;
unsigned int image_ttl_dur;
unsigned int track_period;

unsigned int us_delay;

// Other variables
boolean *cs0_trials;
unsigned long next_trial_ts;
unsigned long trial_num;
unsigned long trial_dur;
volatile int track_change = 0;   // Rotations within tracking epochs
volatile int lick_on = 0;        // Lick onset counter (shouldn't really exceed 1)
volatile int lick_off = 0;       // Lick offest counter (shouldn't really exceed 1)

Behavior behav;
Stream &stream = Serial;


void Track() {
  // Track changes in rotary encoder via interrupt
  if (digitalRead(pin_track_b)) track_change++;
  else track_change--;
}


void EndSession(unsigned long ts) {
  // Send "end" signal
  behav.SendData(stream, code_end, ts, 0);

  // Reset pins
  digitalWrite(pin_img_start, LOW);
  digitalWrite(pin_img_stop, HIGH);
  delay(IMGPINDUR);
  digitalWrite(pin_img_stop, LOW);

  while (1);
}


void GetParams() {
  // Retrieve parameters from serial
  const int paramNum = 21;
  unsigned long parameters[paramNum];

  for (int p = 0; p < paramNum; p++) {
    parameters[p] = Serial.parseInt();
  }

  pre_session = parameters[0];
  post_session = parameters[1];
  cs0_num = parameters[2];
  cs1_num = parameters[3];

  uniform_iti = parameters[4];
  mean_iti = parameters[5];
  min_iti = parameters[6];
  max_iti = parameters[7];
  pre_stim = parameters[8];
  post_stim = parameters[9];

  cs0_dur = parameters[10];
  cs0_freq = parameters[11];
  us0_delay = parameters[12];
  us0_dur = parameters[13];
  cs1_dur = parameters[14];
  cs1_freq = parameters[15];
  us1_delay = parameters[16];
  us1_dur = parameters[17];

  image_all = parameters[18];
  image_ttl_dur = parameters[19];
  track_period = parameters[20];

  us_delay = us0_delay;
  trial_num = cs0_num + cs1_num;
  trial_dur = pre_stim + post_stim;
}


void WaitForStart() {
  byte reading;

  while (1) {
    reading = Serial.read();
    switch(reading) {
      case CODEEND:
        EndSession(0);
      case STARTCODE:
        return;   // Start session
    }
  }
}


void Tone(int pin, unsigned int freq, unsigned int dur) {
  // Turn off all tones before playing to ensure next one will play
  noTone(pin);
  tone(pin, freq, dur);
}


void setup() {
  Serial.begin(9600);
  randomSeed(analogRead(0));

  // Set pins
  pinMode(pin_track_a, INPUT);
  pinMode(pin_track_b, INPUT);

  pinMode(pin_lick, INPUT);
  pinMode(pin_sol_0, OUTPUT);
  pinMode(pin_sol_1, OUTPUT);

  pinMode(pin_img_start, OUTPUT);
  pinMode(pin_img_stop, OUTPUT);

  // Wait for parameters from serial
  Serial.println(
    "Classical conditioning\n"
    "Waiting for parameters..."
  );
  while (Serial.available() <= 0);
  GetParams();
  Serial.println("Paremeters processed");

  // First trial
  if (uniform_iti) {
    next_trial_ts = pre_session + mean_iti;
  }
  else {
    // Create ITIs from an exponential distribution

    // Make sure min_iti is valid
    if (min_iti < trial_dur) min_iti = trial_dur;

    next_trial_ts = (unsigned long) pre_session + behav.ExpDistro(mean_iti, min_iti, max_iti);  // Casting unnecessary?
  }

  // Shuffle trials
  cs0_trials = new () boolean[trial_num];
  for (int tt = 0; tt < trial_num; tt++) {
    // Assign appropriate number of CS+ trials
    if (tt < cs0_num) cs0_trials[tt] = true;
    else cs0_trials[tt] = false;
  }
  behav.Shuffle(cs0_trials, trial_num);

  // Wait for start signal
  Serial.println("Waiting for start signal ('E')");
  WaitForStart();

  // Set interrupt
  attachInterrupt(digitalPinToInterrupt(pin_track_a), Track, RISING);
  digitalWrite(pin_img_start, HIGH);
  Serial.println("Session started\n");
}


void loop() {

  // Variables
  static unsigned long img_start_ts;      // Timestamp pin was last on
  static unsigned long img_stop_ts;
  static unsigned long next_track_ts = track_period;  // Timer used for motion tracking and conveyor movement

  static boolean manual_trial;
  static unsigned long ts_trial_start;
  static unsigned long ts_stim;
  static unsigned long ts_us;
  static unsigned long ts_trial_end;
  static unsigned int trial_ix;
  static unsigned int trial_tone_freq;    // Defines tone frequency for trial
  static unsigned int trial_tone_dur;     // Defines tone duration for trial
  static unsigned int trial_sol_pin;      // Defines solenoid to trigger for trial
  static unsigned int trial_sol_dur;      // Defines solenoid duration for trial
  static boolean in_trial;
  static boolean stimmed;
  static boolean rewarded;
  static boolean lick_state;

  // Timestamp
  static const unsigned long start = millis();  // record start of session
  unsigned long ts = millis() - start;          // current timestamp

  // Turn off events
  if (ts >= img_start_ts + IMGPINDUR) digitalWrite(pin_img_start, LOW);
  if (ts >= img_stop_ts + IMGPINDUR) digitalWrite(pin_img_stop, LOW);
  if (ts >= ts_us + trial_sol_dur) digitalWrite(trial_sol_pin, LOW);

  // -- SESSION CONTROL -- //

  // -- 0. SERIAL SCAN -- //
  // Read from computer
  if (Serial.available() > 0) {
    // Watch for information from computer.
    byte reading = Serial.read();
    switch(reading) {
      case CODEEND:
        EndSession(ts);
        break;
      case CODETRIAL:
        // Only works if not already in trial
        if (! in_trial) {
          in_trial = true;
        }
        break;
      break;
    }
  }

  // -- 1. TRIAL CONTROL -- //

  // Check for trial start or session end
  if (trial_ix < trial_num && ! in_trial && ts >= next_trial_ts) {
    // Beginning of trial
    in_trial = true;

    // Determine CS/US parameters
    if (cs0_trials[trial_ix]) {
      trial_tone_freq = cs0_freq;
      trial_tone_dur = cs0_dur;
      trial_sol_pin = pin_sol_0;
      trial_sol_dur = us0_dur;
    }
    else {
      trial_tone_freq = cs1_freq;
      trial_tone_dur = cs1_dur;
      trial_sol_pin = pin_sol_1;
      trial_sol_dur = us1_dur;
    }

    // Determine timestamps for events
    ts_trial_start = ts;
    ts_stim = ts_trial_start + pre_stim;
    ts_us = ts_stim + us_delay;
    ts_trial_end = ts_trial_start + trial_dur;

    // Start imaging (if applicable)
    if (! image_all) digitalWrite(pin_img_start, HIGH);

    // Determine next trial
    if (uniform_iti) next_trial_ts += mean_iti;
    else next_trial_ts += behav.ExpDistro(mean_iti, min_iti, max_iti);

    behav.SendData(stream, code_trial_start, ts, cs0_trials[trial_ix]);
  }
  else if (trial_ix >= trial_num && ! in_trial && ts >= ts_trial_start + post_session) {
    EndSession(ts);
  }

  // Control trial events (when in trial)
  if (in_trial) {
    if (! stimmed && ts >= ts_stim) {
      // Present CS
      stimmed = true;
      Tone(pin_tone, trial_tone_freq, trial_tone_dur);
      behav.SendData(stream, code_cs_start, ts, cs0_trials[trial_ix]);
    }
    if (! rewarded && ts >= ts_us) {
      // Deliver reward
      rewarded = true;
      digitalWrite(trial_sol_pin, HIGH);
      behav.SendData(stream, code_us_start, ts, cs0_trials[trial_ix]);
    }
    if (ts >= ts_trial_end) {
      // End trial
      in_trial = false;
      stimmed = false;
      rewarded = false;
      trial_ix++;
      if (! image_all) digitalWrite(pin_img_stop, HIGH);
    }
  }

  // -- 2. TRACK MOVEMENT -- //

  if (ts >= next_track_ts) {
    // Check for movement
    if (track_change != 0) {
      behav.SendData(stream, code_track, ts, track_change);
      track_change = 0;
    }
    
    // Increment nextTractTS for next track stamp
    next_track_ts += track_period;
  }

  // -- 3. TRACK LICING -- //

  boolean lick_state_now = digitalRead(pin_lick);
  if (lick_state_now != lick_state) {
    // Check if change in state is onset or offset
    if (lick_state_now) behav.SendData(stream, code_lick, ts, 1);
    else behav.SendData(stream, code_lick, ts, 0);
  }
  lick_state = lick_state_now;
}
