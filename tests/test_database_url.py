from utils.database_utils import normalize_db_url


def test_postgres_scheme_is_normalised():
    # Pinned to the psycopg2 driver explicitly: SQLAlchemy 2.1's own default dialect order picks psycopg
    # (v3) for a bare postgresql:// URL, which requirements.txt does not install (only psycopg2-binary),
    # crashing at startup the first time the app meets a real Postgres database (found 2026-11-25 against Neon).
    assert normalize_db_url('postgres://u:p@h/db') == 'postgresql+psycopg2://u:p@h/db'
    assert normalize_db_url('postgresql://u:p@h/db') == 'postgresql+psycopg2://u:p@h/db'
    assert normalize_db_url('postgresql+psycopg://u:p@h/db') == 'postgresql+psycopg://u:p@h/db'  # driver already named: left alone
    assert normalize_db_url(None) is None
