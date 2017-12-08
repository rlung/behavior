// Generate trials for behavioral session

unsigned long *trials;          // Pointer to array for DMA; initialized later
boolean *csplus_trials;

unsigned long pre_session = 10000;
unsigned long post_session = 10000;
unsigned long pre_stim = 1000;
unsigned long post_stim = 1000;
boolean uniform_iti = false;
unsigned long mean_iti = 5000;
unsigned long min_iti = 2500;
unsigned long max_iti = 20000;
unsigned int csplus_num = 5;
unsigned int csminus_num = 3;
unsigned int csplus_dur = 100;
unsigned int csplus_freq = 20000;
unsigned int csminus_dur = 100;
unsigned int csminus_freq = 50000;

unsigned long session_dur;
unsigned long trial_dur = pre_stim + post_stim;
int trial_num = csplus_num + csminus_num;


void EndSession(unsigned long ts) {
  Serial.print("Session ended at ");
  Serial.println(ts);
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

void ShufflePlusMinus() {
  // Shuffle CS+ & CS- trials
  
  // Creatre boolean mask for CS+ trials (not shuffled yet)
  for (int tt = 0; tt < trial_num; tt++) {
    if (tt < csplus_num) csplus_trials[tt] = true;
    else csplus_trials[tt] = false;
  }

  // Shuffle boolean array
  // Iterate over elements in `csplus_trials` (except last one). For each 
  // element, find a new (or same) position in elements after and switch.
  boolean temp;
  int new_pos;
  
  for (int old_pos = 0; old_pos < trial_num; old_pos++) {
    new_pos = random(old_pos, trial_num - 1);
    temp = csplus_trials[old_pos];

    csplus_trials[old_pos] = csplus_trials[new_pos];
    csplus_trials[new_pos] = temp;
  }
}

void setup() {
  Serial.begin(9600);
  randomSeed(analogRead(0));

  trials = new () unsigned long[trial_num];  // Allocate memory
  GenTrials();
  session_dur = trials[trial_num - 1] + trial_dur + post_session;

  csplus_trials = new () boolean[trial_num];
  ShufflePlusMinus();

  Serial.println("Trials are:");
  for (int ii = 0; ii < trial_num; ii++) {
    if (csplus_trials[ii]) Serial.print("CS+ at ");
    else Serial.print("CS- at ");
    Serial.println(trials[ii]);
  }
  Serial.println("---");
  Serial.println("Session started");
}

void loop() {
  static const unsigned long start_time = millis();
  unsigned long ts = millis() - start_time;

  static unsigned int trial_ix;
  if (trial_ix < trial_num && ts >= trials[trial_ix]) {
    if (csplus_trials[trial_ix]) Serial.print("CS+, ");
    else Serial.print("CS-, ");
    Serial.print("Trial ");
    Serial.print(trial_ix);
    Serial.print(" at ");
    Serial.println(ts);
    trial_ix++;
  }

  if (ts >= session_dur) {
    EndSession(ts);
  }
}
