const int pin_sol = 5;


void setup() {
  Serial.begin(9600);
  pinMode(pin_sol, OUTPUT);
}

void loop() {
  int dur;

  if (Serial.available()) {
    delay(5);   // Just make sure all data is transmitted
    
    dur = Serial.parseInt();
    digitalWrite(pin_sol, HIGH);
    delay(dur);
    digitalWrite(pin_sol, LOW);
  }
}