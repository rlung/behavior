/*
Odor presentation

Use with Python GUI "odor-presentation.py". Handles hardware for control of
behavioral session.

Parameters for session are received via serial connection and Python GUI. 
Data from hardware is routed directly back via serial connection to Python 
GUI for recording and calculations.

Example input:
0,0,5,5000,30000,0,100,50

*/


#define IMGPINDUR 100
#define CODEEND 48
#define CODEPARAMS 68
#define CODESTART 69
#define DELIM ","         // Delimiter used for serial outputs
#define CODESTOP 48
#define CODEFORWARD 49
#define CODEBACKWARD 50
#define CODEFORWARDSTEP 51
#define CODEBACKWARDSTEP 52

// Pins
const int pin_track_a = 2;
const int pin_track_b = 3;
const int pin_forward = 4;
const int pin_backward = 5;
const int pin_img_start = 6;
const int pin_img_stop = 7;
const int pin_at_home = 9;
const int pin_at_mouse = 10;

//int railStart = true;
//int railEnd = false;

// Output codes
const int code_end = 0;
const int code_at_mouse = 3;
const int code_to_mouse = 5;
const int code_at_home = 6;
const int code_move = 7;

// Variables via serial
// unsigned long sessionDur;
unsigned long pre_session;
unsigned long post_session;
unsigned long trial_num;
unsigned long trial_duration;
unsigned long iti;
unsigned long img_all;
unsigned long img_ttl_dur;
unsigned long track_period;

// Other variables
unsigned long ts_next_trial;
volatile int track_change = 0;   // Rotations within tracking epochs


void TrackMovement() {
  // Track changes in rotary encoder via interrupt
  if (digitalRead(pin_track_b)) track_change++;
  else track_change--;
}


void EndSession(unsigned long ts) {
  // Send "end" signal
  Serial.print(code_end);
  Serial.print(DELIM);
  Serial.print(ts);
  Serial.print(DELIM);
  Serial.println("0");

  // Stop imaging
  digitalWrite(pin_img_start, LOW);
  digitalWrite(pin_img_stop, HIGH);
  delay(IMGPINDUR);
  digitalWrite(pin_img_stop, LOW);

  while (1);
}


// Retrieve parameters from serial
void GetParams() {
  const int param_num = 8;
  unsigned long parameters[param_num];

  for (int p = 0; p < param_num; p++) {
    parameters[p] = Serial.parseInt();
  }

  pre_session = parameters[0];
  post_session = parameters[1];
  trial_num = parameters[2];
  trial_duration = parameters[3];
  iti = parameters[4];
  img_all = parameters[5];
  img_ttl_dur = parameters[6];
  track_period = parameters[7];
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
          EndSession(ts);
          break;
        case CODEPARAMS:
          if (waiting_for == 1) return;   // GetParams
          break;
        case CODESTART:
          if (waiting_for == 2) return;   // Start session
          break;
        case CODEFORWARDSTEP:
          if (! digitalRead(pin_at_mouse)) {
            digitalWrite(pin_forward, HIGH);
            delay(10);
            digitalWrite(pin_forward, LOW);
          }
          break;
        case CODEBACKWARDSTEP:
          if (! digitalRead(pin_at_home)) {
            digitalWrite(pin_backward, HIGH);
            delay(10);
            digitalWrite(pin_backward, LOW);
          }
          break;
        }
    }

    if (! waiting_for) return;
  }
}


void setup() {
  Serial.begin(9600);
  randomSeed(analogRead(0));

  // Set pins
  pinMode(pin_track_a, INPUT);
  pinMode(pin_track_b, INPUT);
  pinMode(pin_forward, OUTPUT);
  pinMode(pin_backward, OUTPUT);
  pinMode(pin_img_start, OUTPUT);
  pinMode(pin_img_stop, OUTPUT);
  pinMode(pin_at_home, INPUT);
  pinMode(pin_at_mouse, INPUT);

  // Wait for parameters
  Serial.println("Conveyor\nWaiting for parameters...");
  LookForSignal(1, 0);
  GetParams();
  Serial.println("Paremeters processed");

  // Wait for start signal
  Serial.println("Waiting for start signal ('E')");
  LookForSignal(2, 0);
  Serial.println("Session started");

  // Set interrupt
  // Do not set earlier as TrackMovement() will be called before session starts.
  attachInterrupt(digitalPinToInterrupt(pin_track_a), TrackMovement, RISING);
  if (img_all) digitalWrite(pin_img_start, HIGH);
}


void loop() {

  // Variables
  static unsigned long ts_img_start;      // Timestamp pin was last on
  static unsigned long ts_img_stop;
  static unsigned long ts_next_track = track_period;  // Timer used for motion tracking and conveyor movement

  static unsigned long ts_next_trial = pre_session + iti;
  static unsigned int trial_ix;

  static boolean moving;
  static boolean in_trial;
  static boolean move_to_mouse;
  static boolean at_mouse;
  static boolean move_home;
  static unsigned long trial_start;

  // Timestamp
  static const unsigned long start = millis();  // record start of session
  unsigned long ts = millis() - start;          // current timestamp

  // Turn off events.
  if (ts >= ts_img_start + IMGPINDUR) digitalWrite(pin_img_start, LOW);
  if (ts >= ts_img_stop + IMGPINDUR) digitalWrite(pin_img_stop, LOW);


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
    }
  }

  
  // -- 1. SESSION CONTROL -- //
  if (trial_ix < trial_num && ts > ts_next_trial && ! in_trial) {
    in_trial = true;
    move_to_mouse = true;
    trial_ix++;
    if (trial_ix < trial_num) ts_next_trial += iti;

    Serial.print(code_to_mouse);
    Serial.print(DELIM);
    Serial.print(ts);
    Serial.print(DELIM);
    Serial.println("0");
  }

  // Start trial
  if (in_trial) {

    // Move conveyor toward subject
    if (move_to_mouse) {
      if (digitalRead(pin_at_mouse)) {
        digitalWrite(pin_forward, LOW);
        move_to_mouse = false;
        moving = false;
        at_mouse = true;
        trial_start = ts;

        Serial.print(code_at_mouse);
        Serial.print(DELIM);
        Serial.print(ts);
        Serial.print(DELIM);
        Serial.println("0");
      }
      else digitalWrite(pin_forward, HIGH);
    }

    // Actual trial
    else if (at_mouse) {
      // End trial
      if (ts - trial_start >= trial_duration) {
        at_mouse = false;
        move_home = true;
        moving = true;
      }
    }

    // Move conveyor back to start
    else if (move_home) {
      if (digitalRead(pin_at_home)) {
        digitalWrite(pin_backward, LOW);
        move_home = false;
        in_trial = false;

        Serial.print(code_at_home);
        Serial.print(DELIM);
        Serial.print(ts);
        Serial.print(DELIM);
        Serial.println("0");
      }
      else digitalWrite(pin_backward, HIGH);
    }
  }

  // End session
  else if (trial_ix >= trial_num && ! in_trial && ts >= ts_next_trial + post_session) {
    EndSession(ts);
  }

  // -- 2. TRACK MOVEMENT -- //

  if (ts >= ts_next_track) {
    if (track_change != 0) {
      Serial.print(code_move);
      Serial.print(DELIM);
      Serial.print(ts);
      Serial.print(DELIM);
      Serial.println(track_change);
    }
    track_change = 0;
    
    // Increment ts_next_track for next track stamp
    ts_next_track = ts_next_track + track_period;
  }
}
