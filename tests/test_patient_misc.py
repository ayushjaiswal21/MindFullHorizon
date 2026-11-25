import glob


def test_shared_data_not_used():
    files = ["app.py"] + glob.glob("routes/patient/*.py")
    for f in files:
        assert "shared_data" not in open(f, encoding="utf-8").read(), f
