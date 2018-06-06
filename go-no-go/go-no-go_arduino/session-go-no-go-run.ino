/*
Go/no-go task with running as response

Response window is divided into bins determined by `response_period`. Certain 
proportion of bins need to have response met (determined by `trial_cr_min` and 
`trial_cr_max`) 
*/

void GoNogoRun(unsigned long ts, unsigned int cumul_dist) {
  static unsigned long img_start_ts;      // Timestamp pin was last on
  static unsigned long img_stop_ts;

  static unsigned long ts_trial_start;
  static unsigned long ts_trial_signal;
  static unsigned long ts_stim;
  static unsigned long ts_response_window_start;
  static unsigned long ts_response_window_end;
  static unsigned long ts_us;
  static unsigned long ts_trial_end;
  static unsigned int trial_ix;
  static unsigned int trial_tone_freq;    // Defines tone frequency for trial
  static unsigned int trial_tone_dur;     // Defines tone duration for trial
  static unsigned int trial_tone_pulse_dur;
  static unsigned long cs_start;
  static unsigned int trial_sol_pin;      // Defines solenoid to trigger for trial
  static unsigned long trial_us_dur;      // Defines solenoid duration for trial
  static unsigned long trial_us_delay;
  static unsigned int trial_cr_min;
  static unsigned int trial_cr_max;
  static boolean in_trial;
  static boolean signaled;
  static boolean stimmed;
  static boolean response_started;
  static boolean response_ended;
  static boolean responded;
  static boolean rewarded;
  static unsigned long ts_check_response; // Timestamp to periodically check if response is being met
  static unsigned int response_base;      // Cumulative distance at beginning of response-check window
  static unsigned int response_sum;       // Number of 'epochs' during response window that response is met
  static unsigned int response_epoch_num; // Number of 'epochs' within response window


  // Turn off events
  if (ts >= img_start_ts + IMGPINDUR) digitalWrite(pin_img_start, LOW);
  if (ts >= img_stop_ts + IMGPINDUR) digitalWrite(pin_img_stop, LOW);
  if (ts >= ts_trial_signal + trial_signal_dur) digitalWrite(pin_signal, LOW);
  if (ts >= ts_us + trial_us_dur) digitalWrite(trial_sol_pin, LOW);
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
      trial_us_dur = us0_dur;
      trial_us_delay = us0_delay;
      trial_cr_min = cr0_min;
      trial_cr_max = cr0_max;
    }
    else if (cs_trial_types[trial_ix] == 1) {
      trial_tone_freq = cs1_freq;
      trial_tone_dur = cs1_dur;
      trial_tone_pulse_dur = cs1_pulse_dur;
      trial_sol_pin = pin_sol_1;
      trial_us_dur = us1_dur;
      trial_us_delay = us1_delay;
      trial_cr_min = cr1_min;
      trial_cr_max = cr1_max;
    }

    // Determine timestamps for events
    ts_trial_start = ts;
    ts_trial_signal = ts_trial_start + pre_stim - trial_signal_offset;
    ts_stim = ts_trial_start + pre_stim;
    ts_response_window_start = ts_stim + grace_dur;
    ts_response_window_end = ts_response_window_start + response_dur;
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
    // Signal trial start
    if (trial_signal_dur > 0 && ! signaled && ts >= ts_trial_signal) {
      signaled = true;
      digitalWrite(pin_signal, HIGH);
      behav.SendData(stream, code_trial_signal, ts, cs_trial_types[trial_ix]);
    }

    // Deliver CS
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
        if ((ts - ts_stim) % (trial_tone_pulse_dur * 2) < trial_tone_pulse_dur) {
          tone(pin_tone, trial_tone_freq);
        }
        else {
          noTone(pin_tone);
        }
      }
      else if (ts > (ts_stim + trial_tone_dur)) {
        // End pulse train
        noTone(pin_tone);
      }
    }

    // -Deliver US (if responded)-
    // Track response
    if (ts >= ts_response_window_start && ts < ts_response_window_end) {
      // Start of response window
      if (! response_started) {
        response_started = true;
        response_sum = 0;
        response_epoch_num = 0;
        ts_check_response = ts + response_period;
        response_base = cumul_dist;
      }

      // Periodically check if response is being met
      // Periodicity of bins is determined by `response_period` and condition 
      // to be met is deteremined by trial_cr_min and trial_cr_max.
      if (ts >= ts_check_response) {
        unsigned long response = cumul_dist - response_base;
        response_epoch_num++;

        // Check if correct response was made
        // Increment `response_sum` if response met.
        if (response >= trial_cr_min && response < trial_cr_max) {
          response_sum++;
        }

        // Reset baseline for response tracking
        response_base = cumul_dist;
        while (ts >= ts_check_response) {
          ts_check_response += response_period;
        }
      }
    }

    // Determine if response criteria met
    // Response needs to be met in `response_percent` of bins
    if (! response_ended && ts >= ts_response_window_end) {
      response_ended = true;
      Serial.print("trial bins: ");
      Serial.print(response_sum);
      Serial.print(" out of ");
      Serial.println(response_epoch_num);
      if (response_sum > response_percent * response_epoch_num / 100) {
        responded = true;
        ts_us = ts_response_window_end + trial_us_delay;
      }
      behav.SendData(stream, code_response, ts, cs_trial_types[trial_ix] * 2 + responded);
    }

    if (responded && ! rewarded && ts >= ts_us) {
      rewarded = true;
      digitalWrite(trial_sol_pin, HIGH);
      behav.SendData(stream, code_us_start, ts, cs_trial_types[trial_ix]);
    }

    // End trial
    if (ts >= ts_trial_end) {
      // Determine next trial
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

      // Reset trial features
      in_trial = false;
      signaled = false;
      stimmed = false;
      response_started = false;
      response_ended = false;
      responded = false;
      rewarded = false;
      trial_ix++;
      if (! image_all) digitalWrite(pin_img_stop, HIGH);
    }
  }
}
