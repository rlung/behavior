/*
  Morse.cpp - Library for flashing Morse code.
  Created by David A. Mellis, November 2, 2007.
  Released into the public domain.
*/


#include "Arduino.h"
#include "Behavior.h"


Behavior::Behavior() {}


unsigned long Behavior::UniDistro(unsigned long min_val, unsigned long max_val) {
  // Generate a random number from a uniform distribution between `min_val` and `max_val`.

  float u = (float) random(0, 10000) / 10000;

  return u * (max_val - min_val) + min_val;
}


unsigned long Behavior::ExpDistro(unsigned long mean_val, unsigned long min_val, unsigned long max_val) {
  // Generate a random number `u` from a uniform distribution [0, 1) and 
  // transform into an exponential distribution:
  //
  //   -log(u) * mean_val
  // 
  // The new value is also constrained by `mean_val`, `min_val` and `max_val`:
  // 
  //   -log(1 - u*( 1 - exp(-max_val/mean_val) )) * mean_val + min_val
  // 
  // Integral [0, 1] equals approximately 1 for large max_val/mean_val and small 
  // min_val/mean_val. If max:mean is 3:1, actual mean is ~0.84 of `mean_val`.

  float max_factor = (float)max_val / mean_val;   // How many times greater is max from mean?
  float min_factor = (float)min_val / mean_val;   // How many times smaller is min from mean?

  // Transform uniform distribution to exponential
  float u = (float) random(0, 10000) / 10000;
  float rand_factor1 = 1 - exp(-(float)max_factor);   // Casting unnecessary?
  float rand_factor2 = -log(1 - rand_factor1 * u);
  float rand_factor = rand_factor2 + min_factor * (1 - u);

  return mean_val * rand_factor;
}


void Behavior::Shuffle(int *arr, int n_elements) {
  // Shuffle array
  // Iterate over elements in `arr` (except last one), and find a new (or same) 
  // position to swap with. Use to shuffle CS+ and CS- trials for instance.

  for (int old_pos = 0; old_pos < n_elements - 1; old_pos++) {
    int new_pos = random(old_pos, n_elements);

    // Swap if new position is different
    if (new_pos != old_pos) {
      boolean temp = arr[old_pos];
      arr[old_pos] = arr[new_pos];
      arr[new_pos] = temp;
    }
  }
}


void Behavior::SendData(Stream &stream, unsigned int code, unsigned long ts, long data) {
  stream.print(code);
  stream.print(DELIM);
  stream.print(ts);
  stream.print(DELIM);
  stream.println(data);
}
