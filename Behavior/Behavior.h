/*
  Morse.h - Library for flashing Morse code.
  Created by David A. Mellis, November 2, 2007.
  Released into the public domain.
*/


#ifndef Behavior_h
#define Behavior_h

#include "Arduino.h"

#define DELIM ","

class Behavior {
  public:
    Behavior();
    unsigned long ExpDistro(unsigned long mean_val, unsigned long min_val, unsigned long max_val);
    void Shuffle(int *arr, int n_elements);
    void SendData(Stream &stream, unsigned int code, unsigned long ts, long data);
  private:
    int _pin;
};

#endif
