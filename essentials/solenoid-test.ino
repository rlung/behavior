const int pin_sol = 5;


void setup() {
  Serial.begin(9600);
  pinMode(pin_sol, OUTPUT);
}

void loop() {
  if Serial.available() {
    delay(5);   // Just make sure all data is transmitted
    
    int dur = Serial.parseInt();
    digitalWrite(pin_sol, HIGH);
    delay(dur);
    digitalWrite(pin_sol, LOW);
  }
}