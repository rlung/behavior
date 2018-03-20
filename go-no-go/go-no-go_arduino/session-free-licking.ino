void FreeLicking(unsigned long ts, unsigned int lick_count) {
  static unsigned int prev_lick_count = lick_count;
  static unsigned long ts_us;

  if (ts >= ts_us + us0_dur) digitalWrite(pin_sol_0, LOW);

  if (ts >= pre_session && ts < pre_session + session_dur) {
    if (lick_count > prev_lick_count) {
      prev_lick_count = lick_count;
      ts_us = ts;
      digitalWrite(pin_sol_0, HIGH);
      behav.SendData(stream, code_us_start, ts, 0);
    }
  }
  else if (ts >= pre_session + session_dur + post_session) {
    EndSession(ts);
  }
}
