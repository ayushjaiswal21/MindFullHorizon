"""voice tone/emotion label removed from the app (no schema change)

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-25

The voice-log "emotion/tone" label was measured invalid (docs/research/ai/SYNTHESIS.md section 1.1 and
section 3(c) item c1: pitch thresholds mostly detect voice pitch/sex not mood, no within-person baseline,
EU AI Act recital 44 bans emotion inference in education, and Kintsugi - the best-funded commercial
attempt - shut down). The app no longer computes or writes `voice_logs.emotion`, nor the raw
mean_pitch/mean_energy/mean_zcr/mean_spectral_centroid numbers in `voice_logs.audio_features`
(speaker-identifying and useless once the label is gone). New rows store only `audio_features.duration`.

This migration is intentionally a no-op: `voice_logs.emotion` and `voice_logs.audio_features` are left in
place (already nullable) rather than dropped, so old rows and any in-flight work by other agents are not
disrupted. See docs/research/ai/decisions/voice-tone-removed.md.
"""
revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
