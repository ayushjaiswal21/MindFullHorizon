"""The review-packet exporter (scripts/export_review_packet.py): runs end to end into a temp dir, writes non-empty files,
never writes a secret. No network, no Gemini."""
import csv
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "export_review_packet.py")
EXPECTED = ["crisis_phrases.csv", "crisis_test_cases.csv", "safety_flow.md", "assessment_bands.csv",
            "ai_prompt_snapshot.md", "helplines.csv", "tabletop_scenarios.csv", "MANIFEST.md"]
KEY_PATTERNS = [r"AIza[0-9A-Za-z_\-]{20,}", r"\bsk-[A-Za-z0-9_\-]{20,}", r"GOCSPX-[0-9A-Za-z_\-]{10,}",
                r"\bgh[pousr]_[A-Za-z0-9]{20,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"\bCNRY-[0-9a-f]{8,}"]


def _run(out):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, SCRIPT, "--out", str(out), "--timestamp", "2026-01-01T00:00:00Z"],
                          capture_output=True, text=True, timeout=300, env=env, cwd=ROOT)


def _secret_values():
    """Values of secret-looking env vars and .env entries: none may appear in any output."""
    vals = {v for k, v in os.environ.items() if re.search(r"KEY|SECRET|TOKEN|PASSWORD", k) and len(v) >= 12}
    env_file = os.path.join(ROOT, ".env")
    if os.path.isfile(env_file):
        with open(env_file, encoding="utf-8", errors="ignore") as f:
            for line in f:
                k, _, v = line.strip().partition("=")
                if re.search(r"KEY|SECRET|TOKEN|PASSWORD", k) and len(v.strip("'\"")) >= 12:
                    vals.add(v.strip("'\""))
    return vals


def test_exporter_writes_nonempty_files_without_secrets(tmp_path):
    r = _run(tmp_path)
    assert r.returncode == 0, r.stderr[-500:]
    secrets = _secret_values()
    for name in EXPECTED:
        p = tmp_path / name
        assert p.is_file() and p.stat().st_size > 0, name
        text = p.read_text(encoding="utf-8-sig")
        assert text.strip(), name
        for pat in KEY_PATTERNS:
            assert not re.search(pat, text), (name, pat)
        for v in secrets:
            assert v not in text, name


def test_csv_files_parse_and_have_clinician_columns(tmp_path):
    assert _run(tmp_path).returncode == 0
    for name, col in (("crisis_phrases.csv", "clinician_verdict"), ("crisis_test_cases.csv", "clinician_verdict"),
                      ("assessment_bands.csv", "clinician_verdict"), ("tabletop_scenarios.csv", "clinician_judgement")):
        with open(tmp_path / name, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows and col in rows[0], name
        assert all(not r[col] for r in rows), f"{name}: clinician column must start blank"


def test_exporter_is_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    assert _run(a).returncode == 0 and _run(b).returncode == 0
    for name in EXPECTED:
        assert (a / name).read_bytes() == (b / name).read_bytes(), name


def test_manifest_records_commit_and_fingerprints(tmp_path):
    assert _run(tmp_path).returncode == 0
    text = (tmp_path / "MANIFEST.md").read_text(encoding="utf-8")
    assert "Git commit:" in text and "Generated at (UTC): 2026-01-01T00:00:00Z" in text and "ai/severity.py" in text
