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

Example input: 3000+3000+3+1+1+3000+3000+60000+500+1000+500+100+0+500+500+1000+0+500+0+100
*/


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
const int code_lick_onset = 1;
const int code_lick_offset = 2;
const int code_trial_start = 3;
const int code_track = 7;

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

unsigned int us_delay;
unsigned int track_period = 50;

// Other variables
unsigned long *trials;           // Pointer to array for DMA; initialized later
boolean *cs0_trials;
unsigned long trial_num;
unsigned long trial_dur;
unsigned long session_dur;
volatile int track_change = 0;   // Rotations within tracking epochs
volatile int lick_on = 0;        // Lick onset counter (shouldn't really exceed 1)
volatile int lick_off = 0;       // Lick offest counter (shouldn't really exceed 1)


void Track() {
  // Track changes in rotary encoder via interrupt
  if (digitalRead(pin_track_b)) track_change++;
  else track_change--;
}

// void Lick() {
//   if (digitalRead(pin_lick)) lick_on++;
//   else lick_off++;
// }

// End session
void EndSession(unsigned long ts) {
  // Send "end" signal
  Serial.print(code_end);
  Serial.print(DELIM);
  Serial.println(ts);
  digitalWrite(pin_img_stop, HIGH);

  // Reset pins
  digitalWrite(pin_img_start, LOW);
  delay(IMGPINDUR);
  digitalWrite(pin_img_stop, LOW);

  Serial.print("Session ended after ");
  Serial.print(ts);
  Serial.println(" ms");

  while (1);
}

int ExpDistro(unsigned int mean_val, unsigned int min_val, unsigned int max_val) {
  float u;                                        // Random number from uniform distribution
  float max_factor = (float)max_val / mean_val;   // How many times greater is max from mean?
  float min_factor = (float)min_val / mean_val;   // How many times smaller is min from mean?
  float rand_factor;                              // Multiply with `mean_val` to get ITI

  // Transform uniform distribution to exponential
  u = (float) random(0, 10000) / 10000;
  float rand_factor1 = 1 - exp(-(float)max_factor);   // Casting unnecessary?
  float rand_factor2 = -log(1 - rand_factor1 * u);
  rand_factor = rand_factor2 + min_factor;

  return mean_val * rand_factor;
}

void GenTrials() {
  // Generate trial start times. 
  // ITIs can be created uniformly or from an exponential distribution. Set by 
  // variable `uniform_iti`.
  
  // Timestamp of last trial during trial list creation. Initially defined as
  // delay to first trial (pre_session).
  unsigned long last_trial = pre_session;
  
  if (uniform_iti) {
    // Create trials with same ITIs.
    // ITIs defined by `mean_iti`.
    for (int tt = 0; tt < trial_num; tt++) {
      trials[tt] = last_trial + mean_iti;
      last_trial = trials[tt];
    }
  }
  else {
    // Create ITIs from an exponential distribution
    unsigned long iti;

    for (int tt = 0; tt < trial_num; tt++) {
      // Make sure `min_iti` is valid
      if (min_iti < trial_dur) {
        min_iti = trial_dur;
      }
      
      iti = ExpDistro(mean_iti, min_iti, max_iti);
      trials[tt] = (unsigned long) last_trial + iti;  // Casting unnecessary?
      last_trial = trials[tt];
    }
  }
}

void ShuffleTrials() {
  // Shuffle CS0 & CS1 trials
  
  // Create boolean mask for CS+ trials (not shuffled yet)
  for (int tt = 0; tt < trial_num; tt++) {
    if (tt < cs0_num) cs0_trials[tt] = true;
    else cs0_trials[tt] = false;
  }

  // Shuffle boolean array
  // Iterate over elements in `cs0_trials` (except last one). For each 
  // element, find a new (or same) position in elements after and switch.
  boolean temp;
  int new_pos;
  
  for (int old_pos = 0; old_pos < trial_num - 1; old_pos++) {
    new_pos = random(old_pos, trial_num - 1);
    temp = cs0_trials[old_pos];

    cs0_trials[old_pos] = cs0_trials[new_pos];
    cs0_trials[new_pos] = temp;
  }
}

void GetParams() {
  // Retrieve parameters from serial
  const int paramNum = 20;
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

void ShutdownTones() {
  // Turn off all tones to ensure next one will play
  noTone(pin_tone);
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
    "Go/no-go task\n"
    "Waiting for parameters..."
  );
  while (Serial.available() <= 0);
  GetParams();
  Serial.println("Paremeters processed");

  // Create trials
  trials = new () unsigned long[trial_num];  // Allocate memory
  GenTrials();
  session_dur = trials[trial_num-1] + trial_dur + post_session;
  // Print trial times
  for (int ii = 0; ii < trial_num; ii++) {
    Serial.print(trials[ii]);
    Serial.print(" ");
  }
  Serial.println("");
  Serial.print("Session end at ");
  Serial.println(session_dur);

  // Shuffle trials
  cs0_trials = new () boolean[trial_num];
  ShuffleTrials();

  // Wait for start signal
  Serial.println("Waiting for start signal ('E')");
  WaitForStart();

  // Set interrupt
  // Do not set earlier; `Track` will be called before session starts.
  attachInterrupt(digitalPinToInterrupt(pin_track_a), Track, RISING);
  // attachInterrupt(digitalPinToInterrupt(pin_lick), Lick, CHANGE);
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
  static boolean reward_signal;           // Indicates if criterion for reward met (eg, lick on Go)

  // Timestamp
  static const unsigned long start = millis();  // record start of session
  unsigned long ts = millis() - start;          // current timestamp

  // Turn off events.
  if (ts >= img_start_ts + IMGPINDUR) digitalWrite(pin_img_start, LOW);
  if (ts >= img_stop_ts + IMGPINDUR) digitalWrite(pin_img_stop, LOW);
  if (ts >= ts_us + trial_sol_dur) {
    // if (digitalRead(trial_sol_pin)) Serial.println("Close solenoid");
    digitalWrite(trial_sol_pin, LOW);
  }


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

  // Control trials and session end
  if (trial_ix < trial_num && ! in_trial && ts >= trials[trial_ix]) {
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

    Serial.print("Trial start at ");
    Serial.print(ts);
    Serial.print(" | stim at ");
    Serial.print(ts_stim);
    Serial.print(" | reward at ");
    Serial.print(ts_us);
    Serial.print(" | stop at ");
    Serial.println(ts_trial_end);
  }
  else if (! in_trial && ts >= session_dur) {
    EndSession(ts);
  }

  if (in_trial) {
    if (! stimmed && ts >= ts_stim) {
      // Present CS
      stimmed = true;
      ShutdownTones();
      tone(pin_tone, trial_tone_freq, trial_tone_dur);

      Serial.print("CS presented at ");
      Serial.println(ts);
    }
    if (! rewarded && ts >= ts_us) {
      // Deliver reward
      rewarded = true;
      digitalWrite(trial_sol_pin, HIGH);

      Serial.print("Reward delivered on pin ");
      Serial.print(trial_sol_pin);
      Serial.print(" at ");
      Serial.println(ts);
    }
    if (ts >= ts_trial_end) {
      // End trial
      in_trial = false;
      stimmed = false;
      rewarded = false;
      trial_ix++;
      if (! image_all) digitalWrite(pin_img_stop, HIGH);

      Serial.print("Trial ended at ");
      Serial.println(ts);
    }
  }

  // -- 2. TRACK MOVEMENT -- //

  if (ts >= next_track_ts) {
    int track_out_val = track_change;
    track_change = 0;
    
    if (track_out_val != 0) {
      Serial.print(code_track);
      Serial.print(DELIM);
      Serial.print(ts);
      Serial.print(DELIM);
      Serial.println(track_out_val);
    }
    
    // Increment nextTractTS for next track stamp
    next_track_ts = next_track_ts + track_period;
  }

  // -- 3. TRACK LICING -- //

  boolean lick_state_now = digitalRead(pin_lick);
  if (lick_state_now != lick_state) {
    if (lick_state_now) {
      Serial.print(code_lick_onset);
      Serial.print(DELIM);
      Serial.println(ts);
    }
    else {
      Serial.print(code_lick_offset);
      Serial.print(DELIM);
      Serial.println(ts);
    }
  }
  lick_state = lick_state_now;
  // if (lick_on > 0) {
  //   Serial.print(code_lick_onset);
  //   Serial.print(DELIM);
  //   Serial.print(ts);
  //   Serial.print(DELIM);
  //   Serial.println(lick_on);
  //   lick_on = 0;
  // }
  // if (lick_off > 0) {
  //   Serial.print(code_lick_offset);
  //   Serial.print(DELIM);
  //   Serial.print(ts);
  //   Serial.print(DELIM);
  //   Serial.println(lick_off);
  //   lick_off = 0;
  // }
}
