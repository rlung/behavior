/* 
conveyor_motor_slave

For use with the Adafruit Motor Shield v2 
---->  http://www.adafruit.com/products/1438
*/


#include <Wire.h>
#include <Adafruit_MotorShield.h>

const int pin_forward = 2;
const int pin_backward = 3;

// Create the motor shield object with the default I2C address
Adafruit_MotorShield AFMS = Adafruit_MotorShield();

// Set stepper motor with 200 steps per revolution to motor port #2 (M3 and M4)
Adafruit_StepperMotor *myMotor = AFMS.getStepper(200, 2);


void setup() {
  pinMode(pin_forward, INPUT);
  pinMode(pin_backward, INPUT);
  Serial.begin(9600);
  AFMS.begin();
  myMotor -> setSpeed(50);
  
  Serial.println("Motor slave");
  Serial.println("  pin 2: move forward");
  Serial.println("  pin 3: move backward");
}


void loop() {
  if (digitalRead(pin_forward)) {
    myMotor -> step(5, FORWARD, DOUBLE);
  }
  else if (digitalRead(pin_backward)) {
    myMotor -> step(5, BACKWARD, DOUBLE);
  }
}
