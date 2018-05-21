void FreeLickingRun(unsigned long ts, unsigned int cumul_dist) {
  static unsigned long ts_check_response = response_period;
  static unsigned long ts_us;
  static long response_base = cumul_dist;


  // Turn off events
  if (ts >= ts_us + us0_dur) digitalWrite(pin_sol_0, LOW);

  // Check if in session
  if (ts >= pre_session && ts < pre_session + session_dur) {
    // Periodically check if response is made
    if (ts >= ts_check_response) {
      unsigned long response = cumul_dist - response_base;

      // Check if correct response was made
      if (response >= cr0_min && response < cr0_max){
        digitalWrite(pin_sol_0, HIGH);
        behav.SendData(stream, code_us_start, ts, 0);
      }

      // Reset baseline for response tracking
      response_base = cumul_dist;
      while (ts >= ts_check_response) {
        ts_check_response = ts_check_response + response_period;
      }
    }
  }
  else if (ts >= pre_session + session_dur + post_session) {
    EndSession(ts);
  }
}
