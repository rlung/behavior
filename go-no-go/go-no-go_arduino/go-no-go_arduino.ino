/*
Go/no-go task

Handles hardware for control of behavioral session.
Use with Python GUI "go-no-go.py".

Paradigm
Pinto et al. 2013, Guo et al. 2014, 
For each trial, a light cue signals start (250 ms?). At the 1-s mark, the 
discriminatory auditory cue is presented along with a 500-ms grace period where
resposnses are ignored. Mice were able to respond (or not) within the next 1.5 
s. A lick ceased the auditory tone. ITI is 3 s unless a reward was given, extra 
2 s given. Punishment also induced a timeout period of 8 s(?).

Parameters for session are received via serial connection from Python GUI.  Data
from hardware is routed directly back via serial connection to Python GUI for 
recording and calculations.

Outputs are coded as [type of information, timestamp, data]. Many of the trial 
data has `data` encoded as the CS type. Response is coded with CS type and lick 
or not (CS is second bit, lick is first bit, eg, 3 is CS 1, lick; 2 is CS 1 no 
lick).

Example inputs:
0+3000+3000+3+1 + 0+60000+17000+360000+5000+10000 + 500+1000+100+500+500+5000+100+500 + 500+100+0+2000+2000+8000 + 0+100+50
0+3000+3000+3+1 + 0+45000+3000+120000+1000+1000 + 500+1000+100+500+500+5000+100+500 + 500+100+0+2000+2000+8000 + 0+100+50


TODO
switch bw classical conditioning and go no go
*/


#include <Behavior.h>

#define LICK_THRESHOLD 100
#define IMGPINDUR 100     // Length of imaging signal pulse
#define CODEEND 48
#define STARTCODE 69
#define DELIM ","         // Delimiter used for serial communication
#define DEBUG 1


// Pins
const int pin_track_a = 2;
const int pin_track_b = 4;

const int pin_lick = 3;
const int pin_sol_0 = 5;
const int pin_sol_1 = 6;

const int pin_signal = 8;
const int pin_tone = 7;

const int pin_img_start = 9;
const int pin_img_stop  = 10;


// Output codes
const int code_end = 0;
const int code_lick = 1;
const int code_track = 2;
const int code_trial_start = 3;
const int code_trial_signal = 4;
const int code_cs_start = 5;
const int code_us_start = 6;
const int code_response = 7;
const int code_next_trial = 8;

// Variables via serial
unsigned int session_type;
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

unsigned long cs0_dur;
unsigned long cs0_freq;
unsigned long us0_delay;
unsigned long us0_dur;
unsigned long cs1_dur;
unsigned long cs1_freq;
unsigned long us1_delay;
unsigned long us1_dur;

unsigned long trial_signal_offset;
unsigned long trial_signal_dur;
unsigned long trial_signal_freq;
unsigned long grace_dur;
unsigned long response_dur;
unsigned long timeout_dur;

boolean image_all;
unsigned int image_ttl_dur;
unsigned int track_period;

unsigned long us_delay;

// Other variables
int *cs_trial_types;
unsigned long next_trial_ts;
unsigned long trial_num;
unsigned long trial_dur;
volatile int track_change = 0;   // Rotations within tracking epochs

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
  const int paramNum = 28;
  unsigned long parameters[paramNum];

  for (int p = 0; p < paramNum; p++) {
    parameters[p] = Serial.parseInt();
  }

  session_type = parameters[0];
  pre_session = parameters[1];
  post_session = parameters[2];
  cs0_num = parameters[3];
  cs1_num = parameters[4];

  uniform_iti = parameters[5];
  mean_iti = parameters[6];
  min_iti = parameters[7];
  max_iti = parameters[8];
  pre_stim = parameters[9];
  post_stim = parameters[10];

  cs0_dur = parameters[11];
  cs0_freq = parameters[12];
  us0_delay = parameters[13];
  us0_dur = parameters[14];
  cs1_dur = parameters[15];
  cs1_freq = parameters[16];
  us1_delay = parameters[17];
  us1_dur = parameters[18];

  trial_signal_offset = parameters[19];
  trial_signal_dur = parameters[20];
  trial_signal_freq = parameters[21];
  grace_dur = parameters[22];
  response_dur = parameters[23];
  timeout_dur = parameters[24];

  image_all = parameters[25];
  image_ttl_dur = parameters[26];
  track_period = parameters[27];

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


void setup() {
  Serial.begin(9600);
  randomSeed(analogRead(0));

  // Set pins
  pinMode(pin_track_a, INPUT);
  pinMode(pin_track_b, INPUT);

  // pinMode(pin_lick, INPUT);
  pinMode(pin_sol_0, OUTPUT);
  pinMode(pin_sol_1, OUTPUT);

  pinMode(pin_signal, OUTPUT);

  pinMode(pin_img_start, OUTPUT);
  pinMode(pin_img_stop, OUTPUT);

  // Wait for parameters from serial
  Serial.println(
    "Go/no-go task\n"
    "Waiting for parameters..."
  );
  while (Serial.available() <= 0);
  GetParams();
  Serial.println("Parameters processed");

  // First trial
  if (uniform_iti) {
    next_trial_ts = pre_session + mean_iti;
  }
  else {
    // Create ITIs from an exponential distribution
    if (min_iti < trial_dur) min_iti = trial_dur;   // Make sure min_iti is valid
    next_trial_ts = (unsigned long) pre_session + behav.ExpDistro(mean_iti, min_iti, max_iti);  // Casting unnecessary?
  }

  // Shuffle trials
  cs_trial_types = new () int[trial_num];
  for (int tt = 0; tt < trial_num; tt++) {
    // Assign appropriate number of CS+ trials
    if (tt < cs0_num) cs_trial_types[tt] = 0;
    else cs_trial_types[tt] = 1;
  }
  behav.Shuffle(cs_trial_types, trial_num);

  // Wait for start signal
  Serial.println("Waiting for start signal ('E')");
  WaitForStart();

  // Set interrupt
  // Do not set earlier; `Track` will be called before session starts.
  attachInterrupt(digitalPinToInterrupt(pin_track_a), Track, RISING);

  if (image_all) digitalWrite(pin_img_start, HIGH);
  Serial.println("Session started\n");
  behav.SendData(stream, code_next_trial, next_trial_ts, cs_trial_types[0]);
}


void loop() {

  // Variables
  static unsigned long img_start_ts;      // Timestamp pin was last on
  static unsigned long img_stop_ts;
  static unsigned long next_track_ts = track_period;  // Timer used for motion tracking and conveyor movement

  static unsigned int response_licks;
  static unsigned long ts_trial_start;
  static unsigned long ts_trial_signal;
  static unsigned long ts_stim;
  static unsigned long ts_response_window;
  static unsigned long ts_us;
  static unsigned long ts_timeout;
  static unsigned long ts_trial_end;
  static unsigned int trial_ix;
  static unsigned int trial_tone_freq;    // Defines tone frequency for trial
  static unsigned int trial_tone_dur;     // Defines tone duration for trial
  static unsigned int trial_sol_pin;      // Defines solenoid to trigger for trial
  static unsigned int trial_sol_dur;      // Defines solenoid duration for trial
  static boolean in_trial;
  static boolean signaled;
  static boolean stimmed;
  static boolean response_started;
  // static boolean response_ended;
  static boolean rewarded;
  static boolean lick_state;
  static boolean reward_signal;           // Indicates if criterion for reward met (eg, lick on Go)

  // Timestamp
  static const unsigned long start = millis();  // record start of session
  unsigned long ts = millis() - start;          // current timestamp

  // Turn off events
  if (ts >= img_start_ts + IMGPINDUR) digitalWrite(pin_img_start, LOW);
  if (ts >= img_stop_ts + IMGPINDUR) digitalWrite(pin_img_stop, LOW);
  if (ts >= ts_trial_signal + trial_signal_dur) digitalWrite(pin_signal, LOW);
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
      break;
    }
  }

  // -- 1. TRIAL CONTROL -- //

  // Check for trial start or session end
  if (trial_ix < trial_num && ! in_trial && ts >= next_trial_ts) {
    // Beginning of trial
    in_trial = true;

    // Determine CS/US parameters
    if (cs_trial_types[trial_ix] == 0) {
      trial_tone_freq = cs0_freq;
      trial_tone_dur = cs0_dur;
      trial_sol_pin = pin_sol_0;
      trial_sol_dur = us0_dur;
    }
    else if (cs_trial_types[trial_ix] == 1) {
      trial_tone_freq = cs1_freq;
      trial_tone_dur = cs1_dur;
      trial_sol_pin = pin_sol_1;
      trial_sol_dur = us1_dur;
    }

    // Determine timestamps for events
    ts_trial_start = ts;
    ts_trial_signal = ts_trial_start + pre_stim - trial_signal_offset;
    ts_stim = ts_trial_start + pre_stim;
    ts_response_window = ts_stim + grace_dur;
    ts_timeout = ts_response_window + response_dur;
    ts_trial_end = ts_trial_start + trial_dur;

    // Start imaging (if applicable)
    if (! image_all) digitalWrite(pin_img_start, HIGH);

    behav.SendData(stream, code_trial_start, ts, cs_trial_types[trial_ix]);
  }
  else if (trial_ix >= trial_num && ! in_trial && ts >= ts_trial_start + post_session) {
    EndSession(ts);
  }

  // Control trial events (when in trial)
  if (in_trial) {
    if (! signaled && ts >= ts_trial_signal) {
      signaled = true;
      digitalWrite(pin_signal, HIGH);
      behav.SendData(stream, code_trial_signal, ts, cs_trial_types[trial_ix]);
    }
    if (! stimmed && ts >= ts_stim) {
      // Present CS
      stimmed = true;
      tone(pin_tone, trial_tone_freq, trial_tone_dur);
      behav.SendData(stream, code_cs_start, ts, cs_trial_types[trial_ix]);
    }
    if (! rewarded && ts >= ts_response_window && ts < ts_timeout) {
      if (! response_started) {
        response_started = true;
        response_licks = 0;
      }
      else {
        // Deliver reward
        if (response_licks) {
          // response_ended = true;
          rewarded = true;
          ts_us = ts;
          digitalWrite(trial_sol_pin, HIGH);
          behav.SendData(stream, code_us_start, ts, cs_trial_types[trial_ix]);
          behav.SendData(stream, code_response, ts, cs_trial_types[trial_ix] * 2 + 1);
        }
      }
    }
    if (! response_licks && ts >= ts_timeout) {
      // response_ended = true;
      behav.SendData(stream, code_response, ts, cs_trial_types[trial_ix] * 2 + 0);
    }
    if (ts >= ts_trial_end) {
      // Determine next trial
      if (uniform_iti) next_trial_ts += mean_iti;
      else next_trial_ts += behav.ExpDistro(mean_iti, min_iti, max_iti);
      behav.SendData(stream, code_next_trial, next_trial_ts, cs_trial_types[trial_ix + 1]);  // Still need to correct for last trial

      // Reset trial features
      in_trial = false;
      signaled = false;
      stimmed = false;
      response_started = false;
      // response_ended = false;
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

  // Get lick state
  boolean lick_state_now;
  // lick_state_now = digitalRead(pin_lick);
  int lick_reading = analogRead(pin_lick);
  if (lick_reading < LICK_THRESHOLD) lick_state_now = true;
  else lick_state_now = false;

  // Determine if state changed
  if (lick_state_now != lick_state) {
    // Check if change in state is onset or offset
    if (lick_state_now) {
      response_licks++;
      behav.SendData(stream, code_lick, ts, 1);
    }
    else {
      behav.SendData(stream, code_lick, ts, 0);
    }
  }
  lick_state = lick_state_now;
}
