/*
Free licking

Opens solenoid with every lick. Data is not recorded.

 */

const int lick_pin = 3;
const int sol_pin = 13;

const int sol_dur = 20;  // Duration solenoid is open
unsigned long ts_sol_on;

void setup() {
  Serial.begin(9600);
  pinMode(lick_pin, INPUT);
  pinMode(sol_pin, OUTPUT);

  Serial.println("Waiting for signal...");
  while (Serial.available() <= 0);
  Serial.println("Start!");
}

void loop() {
  static const unsigned long start_time = millis();
  static boolean lick_state_prev;

  unsigned long ts = millis() - start;
  if (ts >= ts_sol_on + sol_dur) digitalWrite(sol_pin, LOW);
  
  boolean lick_state_now = digitalRead(lick_pin);
  if ((lick_state_now & lick_state_now != lick_state_prev) | (Serial.read() >= 0)) {
    Serial.println(ts);
    digitalWrite(sol_pin, HIGH);
    ts_sol_on = ts;
  }

  lick_state_prev = lick_state_now;
}
