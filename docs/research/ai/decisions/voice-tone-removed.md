# Decision: voice-log tone/emotion label removed (2026-11-25)

## What was removed
- `utils/voice_features.py::classify_emotion` (the heuristic pitch/energy/ZCR -> emotion mapping).
- `ai/service.py::analyze_voice_emotion` (the Gemini-based tone/insight call, a `personal=True` site).
- `app.py::get_ai_voice_emotion_analysis` and the emotion wiring in `/api/upload-voice`.
- Computation and storage of `mean_pitch`, `pitch_std`, `mean_energy`, `mean_zcr`, `mean_spectral_centroid`
  in `utils/voice_features.py::extract_features`.
- The tone label, pitch and loudness detail rows, and the "rough label for tone" copy in
  `templates/patient_voice_logs.html`.

## Evidence (owner decision, UPDATES 4)
Three-way convergence per `docs/research/ai/SYNTHESIS.md` section 1.1 (first row) and section 3(c) item c1:
`speech.md`, `voice-product.md` and `evidence-safety-eval.md` independently concluded that pitch/energy/ZCR
threshold labels mostly detect voice pitch and sex, not mood, with no within-person baseline; the EU AI Act
recital 44 bans emotion inference in education; and Kintsugi, the best-funded commercial attempt at this,
shut down. SYNTHESIS.md calls this "the single strongest piece of negative evidence in the whole research
set" and this is "measured to not do what it claims," not merely unproven — so it is removed, not caveated.

Per the synthesis's own privacy-minimisation reasoning, the raw acoustic numbers that fed only this label
(pitch, energy, ZCR, spectral centroid) are speaker-identifying and have no remaining purpose once the label
is gone, so they are no longer computed or stored either.

## What remains
- `utils/voice_features.py::extract_features` now returns only `{'duration': seconds}`.
- `VoiceLog.audio_features` stores `{'duration': ...}` for new rows; no tone/emotion analysis, no transcript.
- The voice-log page is honest: audio is analysed for duration only and discarded; no pitch, tone or emotion
  analysis is performed; nothing about mood is inferred from the voice.
- `voice_log` stays in `utils/gamification.py::ACTIVITY_TYPES` (see `docs/GAMIFICATION.md`): the reasoning in
  the research reports is specific to the invalid *label*, not to voice journaling as an activity, so the
  points for showing up and recording a reflection are kept.

## Schema
Migration `0010_voice_tone_removed` (revision `0010`, down_revision `0009`) is a documentation-only no-op:
`voice_logs.emotion` and `voice_logs.audio_features` are left in place (already nullable), not dropped, so
old rows and other agents' in-flight work are not disrupted. `emotion` is simply never written by new code.
