void ClassicalConditioning() {
  static unsigned long ts_trial_start;
  static unsigned long ts_stim;
  static unsigned long ts_us;
  static unsigned long ts_trial_end;
  static unsigned int trial_ix;
  static unsigned int trial_tone_freq;    // Defines tone frequency for trial
  static unsigned int trial_tone_dur;     // Defines tone duration for trial
  static unsigned int trial_sol_pin;      // Defines solenoid to trigger for trial
  static unsigned int trial_sol_dur;      // Defines solenoid duration for trial
  static boolean in_trial;
  static boolean stimmed;
  static boolean rewarded;
  static boolean lick_state;


  // Turn off events
  if (ts >= img_start_ts + IMGPINDUR) digitalWrite(pin_img_start, LOW);
  if (ts >= img_stop_ts + IMGPINDUR) digitalWrite(pin_img_stop, LOW);
  if (ts >= ts_us + trial_sol_dur) digitalWrite(trial_sol_pin, LOW);

  // Check for trial start or session end
  if (trial_ix < trial_num && ! in_trial && ts >= next_trial_ts) {
    // Beginning of trial
    in_trial = true;

    // Determine CS/US parameters
    if (cs0_trials[trial_ix]) {
      trial_tone_freq = cs0_freq;
      trial_tone_dur = cs0_dur;
      trial_sol_pin = pin_sol_0;
      trial_sol_dur = us0_dur;
    }
    else {
      trial_tone_freq = cs1_freq;
      trial_tone_dur = cs1_dur;
      trial_sol_pin = pin_sol_1;
      trial_sol_dur = us1_dur;
    }

    // Determine timestamps for events
    ts_trial_start = ts;
    ts_stim = ts_trial_start + pre_stim;
    ts_us = ts_stim + us_delay;
    ts_trial_end = ts_trial_start + trial_dur;

    // Start imaging (if applicable)
    if (! image_all) digitalWrite(pin_img_start, HIGH);

    // Determine next trial
    if (uniform_iti) next_trial_ts += mean_iti;
    else next_trial_ts += behav.ExpDistro(mean_iti, min_iti, max_iti);

    behav.SendData(stream, code_trial_start, ts, cs0_trials[trial_ix]);
  }
  else if (trial_ix >= trial_num && ! in_trial && ts >= ts_trial_start + post_session) {
    EndSession(ts);
  }

  // Control trial events (when in trial)
  if (in_trial) {
    if (! stimmed && ts >= ts_stim) {
      // Present CS
      stimmed = true;
      Tone(pin_tone, trial_tone_freq, trial_tone_dur);
      behav.SendData(stream, code_cs_start, ts, cs0_trials[trial_ix]);
    }
    if (! rewarded && ts >= ts_us) {
      // Deliver reward
      rewarded = true;
      digitalWrite(trial_sol_pin, HIGH);
      behav.SendData(stream, code_us_start, ts, cs0_trials[trial_ix]);
    }
    if (ts >= ts_trial_end) {
      // End trial
      in_trial = false;
      stimmed = false;
      rewarded = false;
      trial_ix++;
      if (! image_all) digitalWrite(pin_img_stop, HIGH);
    }
  }
}


void GoNogo() {
  static unsigned long img_start_ts;      // Timestamp pin was last on
  static unsigned long img_stop_ts;
  static unsigned long next_track_ts = track_period;  // Timer used for motion tracking and conveyor movement

  static unsigned long ts_trial_start;
  static unsigned long ts_trial_signal;
  static unsigned long ts_stim;
  static unsigned long ts_response_window;
  static unsigned long ts_us;
  static unsigned long ts_timeout;
  static unsigned long ts_trial_end;
  static unsigned int trial_ix;
  static unsigned int trial_tone_freq;    // Defines tone frequency for trial
  static unsigned int trial_tone_dur;     // Defines tone duration for trial
  static unsigned int trial_sol_pin;      // Defines solenoid to trigger for trial
  static unsigned int trial_sol_dur;      // Defines solenoid duration for trial
  static boolean in_trial;
  static boolean signaled;
  static boolean stimmed;
  static boolean response_started;
  // static boolean response_ended;
  static boolean rewarded;
  static boolean lick_state;


  // Turn off events
  if (ts >= img_start_ts + IMGPINDUR) digitalWrite(pin_img_start, LOW);
  if (ts >= img_stop_ts + IMGPINDUR) digitalWrite(pin_img_stop, LOW);
  if (ts >= ts_trial_signal + trial_signal_dur) digitalWrite(pin_signal, LOW);
  if (ts >= ts_us + trial_sol_dur) digitalWrite(trial_sol_pin, LOW);

  // Check for trial start or session end
  if (trial_ix < trial_num && ! in_trial && ts >= next_trial_ts) {
    // Beginning of trial
    in_trial = true;

    // Determine CS/US parameters
    if (cs_trial_types[trial_ix] == 0) {
      trial_tone_freq = cs0_freq;
      trial_tone_dur = cs0_dur;
      trial_sol_pin = pin_sol_0;
      trial_sol_dur = us0_dur;
    }
    else if (cs_trial_types[trial_ix] == 1) {
      trial_tone_freq = cs1_freq;
      trial_tone_dur = cs1_dur;
      trial_sol_pin = pin_sol_1;
      trial_sol_dur = us1_dur;
    }

    // Determine timestamps for events
    ts_trial_start = ts;
    ts_trial_signal = ts_trial_start + pre_stim - trial_signal_offset;
    ts_stim = ts_trial_start + pre_stim;
    ts_response_window = ts_stim + grace_dur;
    ts_timeout = ts_response_window + response_dur;
    ts_trial_end = ts_trial_start + trial_dur;

    // Start imaging (if applicable)
    if (! image_all) digitalWrite(pin_img_start, HIGH);

    behav.SendData(stream, code_trial_start, ts, cs_trial_types[trial_ix]);
  }
  else if (trial_ix >= trial_num && ! in_trial && ts >= ts_trial_start + post_session) {
    EndSession(ts);
  }

  // Control trial events (when in trial)
  if (in_trial) {
    if (! signaled && ts >= ts_trial_signal) {
      signaled = true;
      digitalWrite(pin_signal, HIGH);
      behav.SendData(stream, code_trial_signal, ts, cs_trial_types[trial_ix]);
    }
    if (! stimmed && ts >= ts_stim) {
      // Present CS
      stimmed = true;
      tone(pin_tone, trial_tone_freq, trial_tone_dur);
      behav.SendData(stream, code_cs_start, ts, cs_trial_types[trial_ix]);
    }
    if (! rewarded && ts >= ts_response_window && ts < ts_timeout) {
      if (! response_started) {
        response_started = true;
        response_licks_base = lick_count;
      }
      else {
        // Deliver reward
        if (lick_count - response_licks_base) {
          // response_ended = true;
          rewarded = true;
          ts_us = ts;
          digitalWrite(trial_sol_pin, HIGH);
          behav.SendData(stream, code_us_start, ts, cs_trial_types[trial_ix]);
          behav.SendData(stream, code_response, ts, cs_trial_types[trial_ix] * 2 + 1);
        }
      }
    }
    if (lick_count - response_licks_base <= 0 && ts >= ts_timeout) {
      // response_ended = true;
      behav.SendData(stream, code_response, ts, cs_trial_types[trial_ix] * 2 + 0);
    }
    if (ts >= ts_trial_end) {
      // Determine next trial
      if (uniform_iti) next_trial_ts += mean_iti;
      else next_trial_ts += behav.ExpDistro(mean_iti, min_iti, max_iti);
      behav.SendData(stream, code_next_trial, next_trial_ts, cs_trial_types[trial_ix + 1]);  // Still need to correct for last trial

      // Reset trial features
      in_trial = false;
      signaled = false;
      stimmed = false;
      response_started = false;
      // response_ended = false;
      rewarded = false;
      trial_ix++;
      if (! image_all) digitalWrite(pin_img_stop, HIGH);
    }
  }
}