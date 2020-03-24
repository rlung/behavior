/*
Odor presentation

Use with Python GUI "odor-presentation.py". Handles hardware for control of
behavioral session.

Parameters for session are received via serial connection and Python GUI. 
Data from hardware is routed directly back via serial connection to Python 
GUI for recording and calculations.

Example input:
D0,0,5,5000,30000,0,100,50

*/


#define CODEEND 48
#define CODEPARAMSEND 271828
#define CODEPARAMS 68
#define CODESTART 69
#define DELIM ","         // Delimiter used for serial outputs

// Pins
const int pin_track_a = 2;
const int pin_track_b = 3;

// Output codes
const int code_end = 0;
const int code_move = 7;

// Variables via serial
// unsigned long sessionDur;
unsigned long session_dur;
unsigned long track_period;

// Other variables
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

  while (1);
}


// Retrieve parameters from serial
int GetParams() {
  const int param_num = 3;
  unsigned long parameters[param_num];
  int last_num;

  for (int p = 0; p < param_num; p++) {
    parameters[p] = Serial.parseInt();
  }

  session_dur = parameters[0];
  track_period = parameters[1];
  last_num = parameters[2];
  
  if (last_num != CODEPARAMSEND) return 1;
  else return 0;
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
        }
    }

    if (! waiting_for) return;            // Not sure why this is needed actually
  }
}


void setup() {
  Serial.begin(9600);
  randomSeed(analogRead(0));

  // Set pins
  pinMode(pin_track_a, INPUT);
  pinMode(pin_track_b, INPUT);

  // Wait for parameters
  int exit_code;
  while (1) {
    Serial.println("Waiting for parameters...");
    LookForSignal(1, 0);
    exit_code = GetParams();
    if (! exit_code) {
      break;
    }
    else {
      Serial.print("Error parsing parameters. Exit code ");
      Serial.println(exit_code);
    }
  }
  Serial.println("Paremeters processed");

  // Wait for start signal
  Serial.println("Waiting for start signal ('E')");
  LookForSignal(2, 0);
  Serial.println("Session started");

  // Set interrupt
  // Do not set earlier as TrackMovement() will be called before session starts.
  attachInterrupt(digitalPinToInterrupt(pin_track_a), TrackMovement, RISING);
}


void loop() {

  // Variables
  static unsigned long ts_next_track = track_period;  // Timer used for motion tracking and conveyor movement

  // Timestamp
  static const unsigned long start = millis();        // Record start of session
  unsigned long ts = millis() - start;                // Update current timestamp


  // -- 0. SERIAL SCAN -- //
  // Read from serial
  if (Serial.available() > 0) {
    byte reading = Serial.read();
    switch(reading) {
      case CODEEND:
        EndSession(ts);
        break;
    }
  }

  // -- 1. SESSION CONTROL -- //
  if (ts >= session_dur) {
    EndSession(ts);
  }

  // -- 2. TRACK MOVEMENT -- //
  if (ts >= ts_next_track) {
    // if (track_change != 0) {
    //   Serial.print(code_move);
    //   Serial.print(DELIM);
    //   Serial.print(ts);
    //   Serial.print(DELIM);
    //   Serial.println(track_change);
    // }
    long r = random(100);
    if (r < 10) {
      long t = random(1,11);
      Serial.print(code_move);
      Serial.print(DELIM);
      Serial.print(ts);
      Serial.print(DELIM);
      Serial.println(t);
    }
    track_change = 0;
    
    // Increment ts_next_track for next track stamp
    ts_next_track = ts_next_track + track_period;
  }
}
