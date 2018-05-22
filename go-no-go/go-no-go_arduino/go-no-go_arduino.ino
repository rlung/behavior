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
(need to update with running variables) 0, 60000, 60000, 20, 20, 0, 1, 60000, 40000, 80000, 7000, 13000, 2000, 3000, 0, 50, 3000, 2000, 6000, 0, 50, 3000, 2000, 12000, 0, 50, 3000, 8000, 100, 2000, 1000, 0, 2000, 2000, 8000, 0, 100, 50
(free_licking_run) 3,5000,5000,60000, 0,0,0, 0,0,0,0, 0,0, 0,0,0,50,5000,0, 50,0, 0,0,0,0,0,0, 0,0, 0,0,0,0,0,0, 0,0, 500,0,0, 0,0,0, 0,0,0, 0,0,50
unsigned int session_type;
unsigned long pre_session;
unsigned long post_session;
unsigned long session_dur;
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
unsigned long cs0_pulse_dur;
unsigned long cr0_min;
unsigned long cr0_max;
unsigned long cr0_dur;
unsigned long us0_dur;
unsigned long us0_delay;
unsigned long cs1_dur;
unsigned long cs1_freq;
unsigned long cs1_pulse_dur;
unsigned long cr1_min;
unsigned long cr1_max;
unsigned long cr1_dur;
unsigned long us1_dur;
unsigned long us1_delay;
unsigned long cs2_dur;
unsigned long cs2_freq;
unsigned long cs2_pulse_dur;
unsigned long cr2_min;
unsigned long cr2_max;
unsigned long cr2_dur;
unsigned long us2_dur;
unsigned long us2_delay;
unsigned long response_period;
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

*/


#include <Behavior.h>

#define LICK_REC_THRESHOLD 900  // Threshold to start recording "lick waveform"
#define LICK_THRESHOLD 511      // Threshold to classify lick
#define IMGPINDUR 100           // Length of imaging signal pulse
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
#define CODECS0 61
#define CODECS1 62
#define CODECS2 63
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
const int code_lick_form = 9;
const int code_track = 2;
const int code_trial_start = 3;
const int code_trial_signal = 4;
const int code_cs_start = 5;
const int code_us_start = 6;
const int code_response = 7;
const int code_next_trial = 8;

// Trial codes
const int code_free_licking = 2;
const int code_classical_conditioning = 0;
const int code_go_nogo = 1;
const int code_free_licking_run = 3;
const int code_go_nogo_run = 4;

// Variables via serial
unsigned int session_type;
unsigned long pre_session;
unsigned long post_session;
unsigned long session_dur;
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
unsigned long cs0_pulse_dur;
unsigned long cr0_min;
unsigned long cr0_max;
unsigned long cr0_dur;
unsigned long us0_dur;
unsigned long us0_delay;
unsigned long cs1_dur;
unsigned long cs1_freq;
unsigned long cs1_pulse_dur;
unsigned long cr1_min;
unsigned long cr1_max;
unsigned long cr1_dur;
unsigned long us1_dur;
unsigned long us1_delay;
unsigned long cs2_dur;
unsigned long cs2_freq;
unsigned long cs2_pulse_dur;
unsigned long cr2_min;
unsigned long cr2_max;
unsigned long cr2_dur;
unsigned long us2_dur;
unsigned long us2_delay;
unsigned long response_period;
unsigned int response_percent;
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
  digitalWrite(pin_vac, LOW);
  digitalWrite(pin_sol_0, LOW);
  digitalWrite(pin_sol_1, LOW);
  digitalWrite(pin_sol_2, LOW);
  digitalWrite(pin_img_start, LOW);
  digitalWrite(pin_img_stop, HIGH);
  delay(IMGPINDUR);
  digitalWrite(pin_img_stop, LOW);

  while (1);
}


void LookForSignal(int waiting_for, unsigned long ts) {
  // `waiting_for` indicates signal to look for before return.
  //    0: don't wait for any signal, escape after one iteration
  //    1: wait for parameters
  //    2: wait for start signal
  byte reading;

  while (1) {
    if (Serial.available()) {
      reading = Serial.read();
      switch(reading) {
        case CODEEND:
          Serial.println("End by serial command");
          EndSession(ts);
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
        case CODECS0:
          if (cs0_dur) {
            tone(pin_tone, cs0_freq, cs0_dur);
            if (cs0_pulse_dur) {
              unsigned long pulsed_cs_start = millis();
              while (millis() < (pulsed_cs_start + cs0_dur)) {
                if ((millis() - pulsed_cs_start) % (cs0_pulse_dur * 2) < cs0_pulse_dur) tone(pin_tone, cs0_freq);
                else noTone(pin_tone);
              }
              noTone(pin_tone);
            }
          }
          break;
        case CODECS1:
          if (cs1_dur) {
            tone(pin_tone, cs1_freq, cs1_dur);
            if (cs1_pulse_dur) {
              unsigned long pulsed_cs_start = millis();
              while (millis() < (pulsed_cs_start + cs1_dur)) {
                if ((millis() - pulsed_cs_start) % (cs1_pulse_dur * 2) < cs1_pulse_dur) tone(pin_tone, cs1_freq);
                else noTone(pin_tone);
              }
              noTone(pin_tone);
            }
          }
          break;
        case CODECS2:
          if (cs2_dur) {
            tone(pin_tone, cs2_freq, cs2_dur);
            if (cs2_pulse_dur) {
              unsigned long pulsed_cs_start = millis();
              while (millis() < (pulsed_cs_start + cs2_dur)) {
                if ((millis() - pulsed_cs_start) % (cs2_pulse_dur * 2) < cs2_pulse_dur) tone(pin_tone, cs2_freq);
                else noTone(pin_tone);
              }
              noTone(pin_tone);
            }
          }
          break;
        case CODEPARAMS:
          if (waiting_for == 1) return;   // GetParams
          break;
        case CODESTART:
          if (waiting_for == 2) return;   // Start session
          break;
      }
    }

    if (! waiting_for) return;
  }
}


void GetParams() {
  // Retrieve parameters from serial
  const int paramNum = 50;
  unsigned long parameters[paramNum];

  for (int p = 0; p < paramNum; p++) {
    parameters[p] = Serial.parseInt();
  }

  session_type = parameters[0];
  pre_session = parameters[1];
  post_session = parameters[2];
  session_dur = parameters[3];
  cs0_num = parameters[4];
  cs1_num = parameters[5];
  cs2_num = parameters[6];
  iti_distro = parameters[7];
  mean_iti = parameters[8];
  min_iti = parameters[9];
  max_iti = parameters[10];
  pre_stim = parameters[11];
  post_stim = parameters[12];
  cs0_dur = parameters[13];
  cs0_freq = parameters[14];
  cs0_pulse_dur = parameters[15];
  cr0_min = parameters[16];
  cr0_max = parameters[17];
  cr0_dur = parameters[18];
  us0_dur = parameters[19];
  us0_delay = parameters[20];
  cs1_dur = parameters[21];
  cs1_freq = parameters[22];
  cs1_pulse_dur = parameters[23];
  cr1_min = parameters[24];
  cr1_max = parameters[25];
  cr1_dur = parameters[26];
  us1_dur = parameters[27];
  us1_delay = parameters[28];
  cs2_dur = parameters[29];
  cs2_freq = parameters[30];
  cs2_pulse_dur = parameters[31];
  cr2_min = parameters[32];
  cr2_max = parameters[33];
  cr2_dur = parameters[34];
  us2_dur = parameters[35];
  us2_delay = parameters[36];
  response_period = parameters[37];
  response_percent = parameters[38];
  consumption_dur = parameters[39];
  vac_dur = parameters[40];
  trial_signal_offset = parameters[41];
  trial_signal_dur = parameters[42];
  trial_signal_freq = parameters[43];
  grace_dur = parameters[44];
  response_dur = parameters[45];
  timeout_dur = parameters[46];
  image_all = parameters[47];
  image_ttl_dur = parameters[48];
  track_period = parameters[49];

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
  LookForSignal(1, 0);
  
  GetParams();
  Serial.println("Parameters processed");

  if (session_type == code_classical_conditioning || session_type == code_go_nogo) {
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
    }

    // Shuffle trials
    cs_trial_types = new () int[trial_num];
    for (int tt = 0; tt < trial_num; tt++) {
      // Assign appropriate number of CS+ trials
      if (tt < cs0_num) cs_trial_types[tt] = 0;
      else if (tt < cs0_num + cs1_num) cs_trial_types[tt] = 1;
      else cs_trial_types[tt] = 2;
    }
    behav.Shuffle(cs_trial_types, trial_num);
  }

  // Wait for start signal
  Serial.println("Waiting for start signal ('E')");
  LookForSignal(2, 0);

  // Set interrupt
  // Do not set earlier; `Track` will be called before session starts.
  attachInterrupt(digitalPinToInterrupt(pin_track_a), Track, RISING);

  if (image_all) digitalWrite(pin_img_start, HIGH);
  Serial.println("Session started\n");
  if (session_type == code_classical_conditioning || session_type == code_go_nogo) {
    behav.SendData(stream, code_next_trial, next_trial_ts, cs_trial_types[0]);
  }
}


void loop() {
  static unsigned long next_track_ts = track_period;  // Timer used for motion tracking and conveyor movement
  static long cumul_dist = 0;
  static unsigned int lick_count = 0;
  static boolean lick_state = false;

  static const unsigned long start = millis();  // record start of session
  unsigned long ts = millis() - start;          // current timestamp

  // -- 0. SERIAL SCAN -- //
  // Read from computer
  LookForSignal(0, ts);

  // -- 1. TRIAL CONTROL -- //
  switch (session_type) {
    case code_classical_conditioning:
      ClassicalConditioning(ts, lick_count);
      break;
    case code_go_nogo:
      GoNogo(ts, lick_count);
      break;
    case code_free_licking:
      FreeLicking(ts, lick_count);
      break;
    case code_free_licking_run:
      FreeLickingRun(ts, cumul_dist);
      break;
    case code_go_nogo_run:
      GoNogoRun(ts, cumul_dist);
      break;
  }

  // -- 2. TRACK MOVEMENT -- //
  if (ts >= next_track_ts) {
    // Check for movement
    if (track_change != 0) {
      behav.SendData(stream, code_track, ts, track_change);
      cumul_dist = cumul_dist + track_change;
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
  if (lick_reading < LICK_REC_THRESHOLD) behav.SendData(stream, code_lick_form, ts, lick_reading);
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

