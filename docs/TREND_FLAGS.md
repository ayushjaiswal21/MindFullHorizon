# Mood/sleep trend flags

Deterministic change-point detection over a patient's mood log and sleep log, surfaced to counsellors and
doctors next to the PHQ-9/GAD-7 score flags (`utils/score_flags.py`, see `docs/FOLLOWUPS.md`). Code:
`utils/trend_flags.py`, wired into `routes/provider_followups.py`'s existing context processor, displayed
with `templates/provider_followups/_flags.html` (badges) and `templates/provider_followups/_trend.html`
(sparkline + table, on the per-patient wellness report).

## Method

No machine learning and no training data: both are published statistical process-control methods.

- **CUSUM** (Page, 1954) is the method that produces the flag. It accumulates the day-by-day difference
  between each logged value and a baseline mean (estimated from the earlier half of the series), with a
  small per-step "slack" (`K_SIGMA = 0.5` of the series' own standard deviation) subtracted each step. The
  running sum resets to 0 whenever it would go positive. A flag fires only once the running sum crosses a
  fixed decision limit (`H_SIGMA = 4.0` of the series' own standard deviation) — the standard k=0.5, h=4
  tuning from Montgomery's *Introduction to Statistical Quality Control*, chosen to detect a sustained shift
  of roughly one standard deviation while keeping false alarms rare on a flat, noisy series.
- **EWMA** (Roberts, 1959), `lambda = 0.3`, is exposed as `utils.trend_flags.ewma` for a smoother chart line
  if ever used; it is not required to produce the flag itself.

A flag also requires at least `MIN_POINTS = 6` logged days and a detected run of at least `MIN_RUN = 3` days
before the crossing is accepted, so a single bad day never triggers it — the point is a sustained pattern,
not day-to-day noise. A perfectly flat or all-identical series has zero standard deviation and is defined to
never flag (nothing to detect).

Mood values are 1-10 (`MoodLog.mood_score`, averaged per IST calendar day when more than one log exists for
a day — IST day boundaries via `utils/timeutil.py`, not UTC). Sleep values are hours per night
(`SleepLog.duration_minutes / 60`, one row per IST night already). Both only ever flag a **downward** shift;
an improvement never raises a flag.

## Where it shows

- Caseload table (`provider_dashboard.html`): merged into the same `score_flags` badge list as the PHQ-9/GAD-7
  flags (`routes/provider_followups.py::_combined_flags`), with a mood or moon icon to tell them apart from a
  screening-score flag at a glance. The "With score flag" filter checkbox also matches a trend flag.
- Per-patient wellness report: a dedicated "Mood and sleep patterns" section
  (`templates/provider_followups/_trend.html`) with one sparkline and an expandable text table per signal —
  the same accessible pattern as the existing PHQ-9/GAD-7 sparklines, so a screen reader or a printed report
  has the same information as the chart.

## Honest limitation

This has **not** been clinically validated as predictive of anything. A handful of self-reported numbers
is a thin basis for any statistical claim, and no accuracy number exists for these thresholds against real
outcomes (the same caveat the AI synthesis gives for every unvalidated signal in this codebase,
`docs/research/ai/SYNTHESIS.md` section 3). The flag surfaces a pattern in logged numbers for a human
(the counsellor, who also sees the raw numbers in the same table) to look at and decide what, if anything,
to do about — nothing more. It never pages anyone, never changes a risk level, and is never shown without
the raw logged values next to it.
