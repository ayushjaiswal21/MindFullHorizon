# Gamification: rules and design

Small on purpose. The aim is a gentle reason to come back each day, not a game.

## Rules (also asserted by `tests/test_gamification_ux.py`)

1. Points, streaks, levels and badges are never tied to assessment or mood scores. Completing a screening or saving a mood entry awards nothing. `utils/gamification.py` keeps `NO_POINTS = {'assessment', 'mood'}`, and `utils/gamification_card.py` imports no assessment or mood model.
2. No leaderboards, no comparison with other people, no loss or shame wording, no countdowns, no popups, no confetti.
3. Copy is calm and factual. A broken streak says "Welcome back. A new streak starts today." Nothing says "you lost", "you failed" or "do not break".
4. Every number on screen comes from the database. Badges are computed from rows that exist; there is no badge table.

## Awards

| Activity | Points | Reference key (idempotent) | Cap |
|----------|--------|----------------------------|-----|
| Daily visit (first patient page load of the IST day) | 5 | `visit:<yyyy-mm-dd>` | once per day |
| Medication logged | 10 | `medlog:<id>` | 3 per day |
| Breathing session | 20 | `breathing:<id>` | 3 per day |
| Yoga session | 20 | `yoga:<id>` | 3 per day |
| Digital detox log | 15 | `detox:<id>` | 3 per day (one log a day anyway) |
| Journal entry | 15 | `journal:<id>` | 3 per day |
| Voice log | 20 | `voice:<id>` | 3 per day |
| Goal progress (current value changed, or goal completed) | 10 | `goal:<id>:<yyyy-mm-dd>` | once per goal per day, 3 per day |
| Assessment, mood | 0 | none | never |

Voice log points reward the act of recording and reflecting, not any measurement of the recording: the voice-log
tone/emotion label was removed 2026-11-25 as measured invalid (see `docs/research/ai/decisions/voice-tone-removed.md`),
but the student still showed up and journaled by voice, so `voice_log` stays in `ACTIVITY_TYPES`.

Music sessions are not an award because the app has no route that records a music session yet. Add one with `award_points` when it exists.

`award_points` writes a `PointsLedger` row first. `UNIQUE(user_id, ref)` makes a replay a no-op. The daily cap is 3 paid awards per activity type per IST day; past the cap a row with 0 points is written. The IST day is the day boundary everywhere (`utils/timeutil.py`).

The daily visit is awarded by a `before_request` hook on the patient blueprint (`routes/patient_gamification.py`): GET only, patients only, not `/patient/api/*`. The session remembers the day so later requests do no query.

## Streak

A streak is the number of consecutive IST days with a visit award, computed from the ledger (`streak_from_days`). One missed day per ISO week (Monday to Sunday) is forgiven: it does not break the run and is not counted. Two misses in a row, or a second miss in the same week, end the streak. The card says "One missed day a week is forgiven." If the streak restarts after a break it says "Welcome back. A new streak starts today."

`Gamification.streak` (updated by any award) is a separate, older counter that has no forgiveness. It is only used by the provider engagement summary. The patient card shows the computed streak.

## Levels

Neutral names by total points: Starting out (0), Settling in (50), Finding a rhythm (150), Steady (350), Established (700). A level never goes down because points never go down.

## Badges (with the date earned)

First journal entry, first breathing session, first goal completed, 3, 7 and 30 day streak. Dates are IST. Streak badge dates are the day the streak first reached that length, replayed from the visit days.

## Where it shows

One compact card (`templates/partials/gamification_card.html`): points, level, streak, a Monday to Sunday dots row, badges earned, the next badge, and the line "Points never depend on your mood or screening scores." It is on the patient dashboard and the profile page. Data comes from `utils/gamification_card.py::card_context`, reached through the `gam_card()` template function.

## Why scores are excluded

Rewarding a lower PHQ-9 or GAD-7 score, or a higher mood, pushes people to under-report symptoms, which defeats screening and can hide a crisis. Rewarding the act of completing a screening would push repeated, rushed answers. So screening and mood carry no points at all (see `docs/SAFETY_RESEARCH.md`).

## Research note

The evidence that points, streaks and badges improve mental-health outcomes is weak and mixed. Reviews of gamified mental-health apps report small, short-lived effects on engagement and little on symptoms, and streak mechanics can create guilt when broken. That is why this stays gentle: small points, a forgiven day each week, no loss language and no social comparison. Treat it as a light nudge toward helpful habits and measure real use before adding more.
