void ClassicalConditioning(unsigned long ts, unsigned int lick_count) {
  static unsigned long img_start_ts;      // Timestamp pin was last on
  static unsigned long img_stop_ts;

  static unsigned long ts_trial_start;
  static unsigned long ts_stim;
  static unsigned long ts_us;
  static unsigned long ts_trial_end;
  static unsigned int trial_ix;
  static unsigned long trial_tone_freq;    // Defines tone frequency for trial
  static unsigned long trial_tone_dur;     // Defines tone duration for trial
  static unsigned long trial_tone_pulse_dur;
  static unsigned int trial_sol_pin;      // Defines solenoid to trigger for trial
  static unsigned int trial_sol_dur;      // Defines solenoid duration for trial
  static unsigned int trial_us_delay;
  static boolean in_trial;
  static boolean stimmed;
  static boolean rewarded;


  // Turn off events
  if (ts >= img_start_ts + IMGPINDUR) digitalWrite(pin_img_start, LOW);
  if (ts >= img_stop_ts + IMGPINDUR) digitalWrite(pin_img_stop, LOW);
  if (ts >= ts_us + trial_sol_dur) digitalWrite(trial_sol_pin, LOW);
  if (consumption_dur && ts_us) {
    // Only check if time limit set for consumption & delivery has happened
    if (ts >= ts_us + consumption_dur) digitalWrite(pin_vac, HIGH);
    if (ts >= ts_us + consumption_dur + vac_dur) digitalWrite(pin_vac, LOW);
  }

  // Check for trial start or session end
  if (trial_ix < trial_num && ! in_trial && ts >= next_trial_ts) {
    // Beginning of trial
    in_trial = true;

    // Determine CS/US parameters
    if (cs_trial_types[trial_ix] == 0) {
      trial_tone_freq = cs0_freq;
      trial_tone_dur = cs0_dur;
      trial_tone_pulse_dur = cs0_pulse_dur;
      trial_sol_pin = pin_sol_0;
      trial_sol_dur = us0_dur;
      trial_us_delay = us0_delay;
    }
    else if (cs_trial_types[trial_ix] == 1) {
      trial_tone_freq = cs1_freq;
      trial_tone_dur = cs1_dur;
      trial_tone_pulse_dur = cs1_pulse_dur;
      trial_sol_pin = pin_sol_1;
      trial_sol_dur = us1_dur;
      trial_us_delay = us1_delay;
    }
    else if (cs_trial_types[trial_ix] == 2) {
      trial_tone_freq = cs2_freq;
      trial_tone_dur = cs2_dur;
      trial_tone_pulse_dur = cs2_pulse_dur;
      trial_sol_pin = pin_sol_2;
      trial_sol_dur = us2_dur;
      trial_us_delay = us2_delay;
    }

    // Determine timestamps for events
    ts_trial_start = ts;
    ts_stim = ts_trial_start + pre_stim;
    ts_us = ts_stim + trial_us_delay;
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

    // Present CS
    if (! stimmed && ts >= ts_stim) {
      stimmed = true;
      if (trial_tone_dur) {
        tone(pin_tone, trial_tone_freq, trial_tone_dur);
      }
      behav.SendData(stream, code_cs_start, ts, cs_trial_types[trial_ix]);
    }

    // Pulsed cue
    if (stimmed && trial_tone_pulse_dur) {
      if (ts < (ts_stim + trial_tone_dur)) {
        // Pulse train
        if ((ts - ts_stim) % (trial_tone_pulse_dur * 2) < trial_tone_pulse_dur) tone(pin_tone, trial_tone_freq);
        else noTone(pin_tone);
      }
      else if (ts > (ts_stim + trial_tone_dur)) {
        // End pulse train
        noTone(pin_tone);
      }
    }

    // Present US
    if (! rewarded && ts >= ts_us) {
      // Deliver reward
      rewarded = true;
      digitalWrite(trial_sol_pin, HIGH);
      behav.SendData(stream, code_us_start, ts, cs_trial_types[trial_ix]);
    }

    if (ts >= ts_trial_end) {
      switch (iti_distro) {
        case 0:
          next_trial_ts += mean_iti;
          break;
        case 1:
          next_trial_ts += behav.UniDistro(min_iti, max_iti);
          break;
        case 2:
          next_trial_ts += behav.ExpDistro(mean_iti, min_iti, max_iti);
          break;
      }
      behav.SendData(stream, code_next_trial, next_trial_ts, cs_trial_types[trial_ix + 1]);  // Still need to correct for last trial

      // End trial
      in_trial = false;
      stimmed = false;
      rewarded = false;
      trial_ix++;
      if (! image_all) digitalWrite(pin_img_stop, HIGH);
    }
  }
}
