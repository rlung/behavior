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

#define LICK_REC_THRESHOLD 900  // Threshold to start recording "lick waveform"
#define LICK_THRESHOLD 511      // Threshold to classify lick
#define IMGPINDUR 100           // Length of imaging signal pulse
#define CODEEND 48

#define STARTCODE 69

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
unsigned long us0_dur;
unsigned long us0_delay;
unsigned long cs1_dur;
unsigned long cs1_freq;
unsigned long cs1_pulse_dur;
unsigned long us1_dur;
unsigned long us1_delay;
unsigned long cs2_dur;
unsigned long cs2_freq;
unsigned long cs2_pulse_dur;
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
  const int paramNum = 39;
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
  us0_dur = parameters[16];
  us0_delay = parameters[17];
  cs1_dur = parameters[18];
  cs1_freq = parameters[19];
  cs1_pulse_dur = parameters[20];
  us1_dur = parameters[21];
  us1_delay = parameters[22];
  cs2_dur = parameters[23];
  cs2_freq = parameters[24];
  cs2_pulse_dur = parameters[25];
  us2_dur = parameters[26];
  us2_delay = parameters[27];
  consumption_dur = parameters[28];
  vac_dur = parameters[29];
  trial_signal_offset = parameters[30];
  trial_signal_dur = parameters[31];
  trial_signal_freq = parameters[32];
  grace_dur = parameters[33];
  response_dur = parameters[34];
  timeout_dur = parameters[35];
  image_all = parameters[36];
  image_ttl_dur = parameters[37];
  track_period = parameters[38];

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

  // pinMode(pin_lick, INPUT);
  pinMode(pin_sol_0, OUTPUT);
  pinMode(pin_sol_1, OUTPUT);

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
      lick_count++;
      behav.SendData(stream, code_lick, ts, 1);
    }
    else {
      behav.SendData(stream, code_lick, ts, 0);
    }
  }
  lick_state = lick_state_now;
}

