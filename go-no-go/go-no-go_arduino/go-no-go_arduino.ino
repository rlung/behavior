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

Example input:
0, 0, 0, 3, 4, 5, 0, 22000, 25000, 180000, 7000, 13000, 2000, 1000, 50, 3000, 2000, 5000, 50, 3000, 2000, 10000, 50, 3000, 8000, 50, 2000, 1000, 0, 2000, 2000, 8000, 0, 100, 50

*/


#include <Behavior.h>

#define LICK_THRESHOLD 511
#define IMGPINDUR 100     // Length of imaging signal pulse
#define CODEEND 48
#define CODEVACON 49
#define CODEVACOFF 50
#define CODEVACTRIGGER 51
#define CODESOL0ON 52
#define CODESOL0OFF 53
#define CODESOL0TRIGGER 54
#define CODESOL1ON 55
#define CODESOL1OFF 56
#define CODESOL1TRIGGER 57
#define CODESOL2ON 58
#define CODESOL2OFF 59
#define CODESOL2TRIGGER 60
#define CODEPARAMS 68
#define CODESTART 69
#define DELIM ","         // Delimiter used for serial communication
#define DEBUG 1


// Pins
const int pin_track_a = 2;
const int pin_track_b = 3;
const int pin_lick = 3;
const int pin_vac = 4;
const int pin_sol_0 = 5;
const int pin_sol_1 = 6;
const int pin_sol_2 = 7;
const int pin_signal = 8;
const int pin_tone = 9;
const int pin_img_start = 10;
const int pin_img_stop  = 11;

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
int cs2_num;
boolean iti_distro;
unsigned long mean_iti;
unsigned long min_iti;
unsigned long max_iti;
unsigned long pre_stim;
unsigned long post_stim;
unsigned long cs0_dur;
unsigned long cs0_freq;
unsigned long us0_dur;
unsigned long us0_delay;
unsigned long cs1_dur;
unsigned long cs1_freq;
unsigned long us1_dur;
unsigned long us1_delay;
unsigned long cs2_dur;
unsigned long cs2_freq;
unsigned long us2_dur;
unsigned long us2_delay;
unsigned long consumption_dur;
unsigned long vac_dur;
unsigned long trial_signal_offset;
unsigned long trial_signal_dur;
unsigned long trial_signal_freq;
unsigned long grace_dur;
unsigned long response_dur;
unsigned long timeout_dur;
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


void WaitForSignal(int waiting_for) {
  byte reading;

  while (1) {
    if (Serial.available()) {
      reading = Serial.read();
      switch(reading) {
        case CODEEND:
          EndSession(0);
          break;
        case CODEVACON:
          digitalWrite(pin_vac, HIGH);
          break;
        case CODEVACOFF:
          digitalWrite(pin_vac, LOW);
          break;
        case CODEVACTRIGGER:
          digitalWrite(pin_vac, HIGH);
          delay(vac_dur);
          digitalWrite(pin_vac, LOW);
          break;
        case CODESOL0ON:
          digitalWrite(pin_sol_0, HIGH);
          break;
        case CODESOL0OFF:
          digitalWrite(pin_sol_0, LOW);
          break;
        case CODESOL0TRIGGER:
          digitalWrite(pin_sol_0, HIGH);
          delay(us0_dur);
          digitalWrite(pin_sol_0, LOW);
          break;
        case CODESOL1ON:
          digitalWrite(pin_sol_1, HIGH);
          break;
        case CODESOL1OFF:
          digitalWrite(pin_sol_1, LOW);
          break;
        case CODESOL1TRIGGER:
          digitalWrite(pin_sol_1, HIGH);
          delay(us1_dur);
          digitalWrite(pin_sol_1, LOW);
          break;
        case CODESOL2ON:
          digitalWrite(pin_sol_2, HIGH);
          break;
        case CODESOL2OFF:
          digitalWrite(pin_sol_2, LOW);
          break;
        case CODESOL2TRIGGER:
          digitalWrite(pin_sol_2, HIGH);
          delay(us2_dur);
          digitalWrite(pin_sol_2, LOW);
          break;
        case CODEPARAMS:
          if (waiting_for == 0) return;   // GetParams
          break;
        case CODESTART:
          if (waiting_for == 1) return;   // Start session
          break;
        break;
      }
    }
  }
}


void GetParams() {
  // Retrieve parameters from serial
  const int paramNum = 35;
  unsigned long parameters[paramNum];

  for (int p = 0; p < paramNum; p++) {
    parameters[p] = Serial.parseInt();
  }

  session_type = parameters[0];
  pre_session = parameters[1];
  post_session = parameters[2];
  cs0_num = parameters[3];
  cs1_num = parameters[4];
  cs2_num = parameters[5];
  iti_distro = parameters[6];
  mean_iti = parameters[7];
  min_iti = parameters[8];
  max_iti = parameters[9];
  pre_stim = parameters[10];
  post_stim = parameters[11];
  cs0_dur = parameters[12];
  cs0_freq = parameters[13];
  us0_dur = parameters[14];
  us0_delay = parameters[15];
  cs1_dur = parameters[16];
  cs1_freq = parameters[17];
  us1_dur = parameters[18];
  us1_delay = parameters[19];
  cs2_dur = parameters[20];
  cs2_freq = parameters[21];
  us2_dur = parameters[22];
  us2_delay = parameters[23];
  consumption_dur = parameters[24];
  vac_dur = parameters[25];
  trial_signal_offset = parameters[26];
  trial_signal_dur = parameters[27];
  trial_signal_freq = parameters[28];
  grace_dur = parameters[29];
  response_dur = parameters[30];
  timeout_dur = parameters[31];
  image_all = parameters[32];
  image_ttl_dur = parameters[33];
  track_period = parameters[34];

  if (session_type == 0) {
    trial_num = cs0_num + cs1_num + cs2_num;
  } else if (session_type == 1) {
    trial_num = cs0_num + cs1_num;
  }
  trial_dur = pre_stim + post_stim;
}

void setup() {
  Serial.begin(9600);
  randomSeed(analogRead(0));

  // Set pins
  pinMode(pin_track_a, INPUT);
  pinMode(pin_track_b, INPUT);
  pinMode(pin_vac, OUTPUT);
  pinMode(pin_sol_0, OUTPUT);
  pinMode(pin_sol_1, OUTPUT);
  pinMode(pin_sol_2, OUTPUT);
  pinMode(pin_signal, OUTPUT);
  pinMode(pin_img_start, OUTPUT);
  pinMode(pin_img_stop, OUTPUT);

  // Wait for parameters from serial
  Serial.println(
    "Go/no-go & Classical conditioning tasks\n"
    "Waiting for parameters..."
  );
  WaitForSignal(0);
  
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
    else if (tt < cs1_num) cs_trial_types[tt] = 1;
    else cs_trial_types[tt] = 2;
  }
  behav.Shuffle(cs_trial_types, trial_num);

  // Wait for start signal
  Serial.println("Waiting for start signal ('E')");
  WaitForSignal(1);

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
