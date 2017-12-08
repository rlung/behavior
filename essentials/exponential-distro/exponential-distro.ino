// Generate values from an exponential distribution
// 
// Exponential distribution from uniform is determined by inverse of CDF.
// 
//   -log(u) * mean_val
// 
// However, maximum and minimum values often constrain realistic values. The 
// modified function becomes:
// 
//   -log(1 - u*( 1 - exp(-max_val/mean_val) )) * mean_val + min_val
// 
// Integral [0, 1] equals approximately 1 for large max_val/mean_val and small 
// min_val/mean_val. If max:mean is 3:1, actual mean is ~0.84 of `mean_val`.
// 


int Sample(unsigned int mean_val, unsigned int min_val, unsigned int max_val) {
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

void setup() {
  Serial.begin(9600);
  randomSeed(analogRead(0));
}

void loop() {
  Serial.println(Sample(1000, 10, 10000));
  delay(100);
}