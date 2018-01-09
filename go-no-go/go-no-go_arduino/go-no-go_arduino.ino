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
const int pin_vac = 4;

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

boolean iti_distro;
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
unsigned long consumption_dur;
unsigned long us0_vac_dur;
unsigned long us1_vac_dur;

boolean image_all;
unsigned int image_ttl_dur;
unsigned int track_period;

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
  const int paramNum = 31;
  unsigned long parameters[paramNum];

  for (int p = 0; p < paramNum; p++) {
    parameters[p] = Serial.parseInt();
  }

  session_type = parameters[0];
  pre_session = parameters[1];
  post_session = parameters[2];
  cs0_num = parameters[3];
  cs1_num = parameters[4];

  iti_distro = parameters[5];
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
  consumption_dur = parameters[25];
  us0_vac_dur = parameters[26];
  us1_vac_dur = parameters[27];

  image_all = parameters[28];
  image_ttl_dur = parameters[29];
  track_period = parameters[30];

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
  pinMode(pin_vac, OUTPUT);

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
  switch (iti_distro) {
    case 0:
      next_trial_ts = pre_session + mean_iti;
      break;
    case 1:
      next_trial_ts = pre_session + behav.UniDistro(min_iti, max_iti);
      break;
    case 2:
      next_trial_ts = pre_session + behav.ExpDistro(mean_iti, min_iti, max_iti);
      break;
    break;
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
  static unsigned long next_track_ts = track_period;  // Timer used for motion tracking and conveyor movement
  static unsigned int lick_count = 0;
  static boolean lick_state;

  static const unsigned long start = millis();  // record start of session
  unsigned long ts = millis() - start;          // current timestamp

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
  switch (session_type) {
    case 0:
      ClassicalConditioning(ts, lick_count);
      break;
    case 1:
      GoNogo(ts, lick_count);
      break;
    break;
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
      lick_count++;
      behav.SendData(stream, code_lick, ts, 1);
    }
    else {
      behav.SendData(stream, code_lick, ts, 0);
    }
  }
  lick_state = lick_state_now;
}
