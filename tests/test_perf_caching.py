"""Performance guards: caching, compression, sessions/logs, memory growth. Split out of test_perf.py
(300-line rule); lazy imports, pool config, query counts and pagination are in test_perf_db.py.

Run all: `pytest tests/test_perf_caching.py -q`. Skip the slower memory loop: `-k "not memory_growth"`.
"""
import gzip
import json
import logging
import os
import tracemalloc
from datetime import date, datetime, timedelta

import pytest
from cachelib import SimpleCache
from sqlalchemy import event

from core.extensions import cache, db
from models import ClinicalNote, DigitalDetoxLog, MoodLog, ProviderPatient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------- helpers ----------

class QueryCounter:
    def __init__(self):
        self.n = 0

    def __enter__(self):
        event.listen(db.engine, 'before_cursor_execute', self._hit)
        return self

    def __exit__(self, *exc):
        event.remove(db.engine, 'before_cursor_execute', self._hit)

    def _hit(self, *args):
        self.n += 1


@pytest.fixture
def real_cache(app):
    """The suite runs with NullCache (so tests cannot leak aggregates into each other); swap in a real one here."""
    with app.app_context():
        holder = app.extensions['cache']
        old = holder[cache]
        holder[cache] = SimpleCache(threshold=500, default_timeout=60)
    yield
    holder[cache] = old


def _seed_caseload(app, provider_id, n, institution='Test University'):
    """n assigned patients, each with an assessment, a detox log, a clinical note and a mood."""
    with app.app_context():
        for i in range(n):
            from models import Assessment, User
            # a fixed hash: scrypt costs ~0.3 s per user, which would dominate a 30-patient seed
            u = User(email=f'perf{i}_{n}_{provider_id}@t.l', name=f'Perf Patient {i}', role='patient', institution=institution,
                     password_hash='scrypt:32768:8:1$x$00')
            db.session.add(u)
            db.session.flush()
            db.session.add_all([
                ProviderPatient(provider_id=provider_id, patient_id=u.id, source='manual'),
                Assessment(user_id=u.id, assessment_type='PHQ-9', score=5 + i % 20),
                Assessment(user_id=u.id, assessment_type='GAD-7', score=3 + i % 15),
                DigitalDetoxLog(user_id=u.id, date=date.today(), screen_time_hours=3 + i % 6, ai_score='Good'),
                ClinicalNote(provider_id=provider_id, patient_id=u.id, session_date=datetime.utcnow()),
                MoodLog(user_id=u.id, mood_score=1 + i % 10),
            ])
        db.session.commit()


# ---------- caching ----------

def _add_patients(app, n, institution):
    import uuid
    from models import User
    with app.app_context():
        for _ in range(n):
            db.session.add(User(email=f'{uuid.uuid4().hex}@t.l', name='P', role='patient', institution=institution,
                                password_hash='scrypt:32768:8:1$x$00'))
        db.session.commit()


def _summary(app, institution):
    from routes.provider import institution_summary
    with app.test_request_context('/'):
        from flask import session
        session['user_institution'] = institution  # the aggregate scope comes from the session, as in the route
        with QueryCounter() as q:
            out = institution_summary(institution)
        return out, q.n


def test_institution_summary_cached_per_institution_and_invalidated_on_write(app, real_cache):
    _add_patients(app, 6, 'Alpha College')
    first, n_first = _summary(app, 'Alpha College')
    assert first['total_users'] == 6 and n_first > 0
    assert _summary(app, 'Beta College')[0]['total_users'] is None  # Beta has no one: its own entry, not Alpha's
    again, n_again = _summary(app, 'Alpha College')
    assert again == first and n_again == 0  # served from the cache, no SQL
    _add_patients(app, 1, 'Alpha College')  # a commit touching User bumps the generation
    assert _summary(app, 'Alpha College')[0]['total_users'] == 7


def test_cache_key_contains_institution_and_generation(app, real_cache):
    from utils.cache_utils import key
    with app.app_context():
        assert key('inst', 'summary', 'alpha').startswith('inst:summary:alpha:g')
        assert key('inst', 'summary', 'alpha') != key('inst', 'summary', 'beta')


def test_private_json_is_not_shared_between_users(app, make_user, login, client, real_cache):
    a, b = make_user('patient'), make_user('patient')
    with app.app_context():
        db.session.add(MoodLog(user_id=a, mood_score=9))
        db.session.commit()
    login(a)
    assert len(client.get('/api/mood').get_json()['moods']) == 1
    other = app.test_client()
    from tests.conftest import _login_as
    _login_as(other, app, b)
    assert other.get('/api/mood').get_json()['moods'] == []


def test_wellness_cache_is_null_in_tests(app):
    assert app.config['CACHE_TYPE'] == 'NullCache'


def test_cache_headers(app, client, patient_client):
    html = client.get('/login')
    assert html.headers['Cache-Control'] == 'no-cache' and 'Cookie' in html.headers.get('Vary', '')
    c, uid = patient_client
    assert c.get('/patient/dashboard').headers['Cache-Control'] == 'private, no-cache'
    assert c.get('/api/mood').headers['Cache-Control'] == 'no-store'
    gen = client.get('/static/gen/packed.css?abc')
    if gen.status_code == 200:
        assert gen.headers['Cache-Control'] == 'public, max-age=31536000, immutable'
    plain = client.get('/static/css/site.css')
    assert plain.status_code == 200 and 'immutable' not in plain.headers.get('Cache-Control', '')
    assert plain.headers.get('ETag')
    versioned = client.get('/static/css/site.css?v=123')
    assert versioned.headers['Cache-Control'] == 'public, max-age=31536000, immutable'
    assert client.get('/static/css/site.css', headers={'If-None-Match': plain.headers['ETag']}).status_code == 304


def test_route_set_cache_control_is_kept(app):
    from flask import jsonify
    with app.test_request_context('/api/anything'):
        r = jsonify(a=1)
        r.headers['Cache-Control'] = 'public, max-age=60'
        assert app.process_response(r).headers['Cache-Control'] == 'public, max-age=60'


# ---------- compression ----------

def test_json_and_html_are_compressed(app, patient_client, client):
    c, uid = patient_client
    with app.app_context():
        db.session.add_all([MoodLog(user_id=uid, mood_score=5) for _ in range(60)])
        db.session.commit()
    big = c.get('/api/mood?per_page=60', headers={'Accept-Encoding': 'gzip'})
    assert big.headers.get('Content-Encoding') == 'gzip' and 'Accept-Encoding' in big.headers.get('Vary', '')
    assert json.loads(gzip.decompress(big.data))['meta']['total'] == 60
    br = c.get('/api/mood?per_page=60', headers={'Accept-Encoding': 'br, gzip'})
    assert br.headers.get('Content-Encoding') == 'br'
    page = client.get('/login', headers={'Accept-Encoding': 'gzip'})
    assert page.headers.get('Content-Encoding') == 'gzip'
    assert 'Content-Encoding' not in c.get('/api/mood?per_page=60').headers  # client did not ask


def test_small_responses_are_not_compressed(client):
    r = client.get('/health', headers={'Accept-Encoding': 'gzip'})
    assert r.status_code == 200 and 'Content-Encoding' not in r.headers


@pytest.mark.parametrize('path', ['static/css/site.css', 'static/js/scripts.js', 'static/img/icons.svg', 'static/favicon.svg'])
def test_static_text_assets_are_compressed(client, path):
    if not os.path.exists(os.path.join(ROOT, path)) or os.path.getsize(os.path.join(ROOT, path)) < 600:
        pytest.skip('no large asset of this type')
    # static files are streamed, and Flask-Compress streams only br/zstd/deflate (gzip is for dynamic responses)
    assert client.get('/' + path, headers={'Accept-Encoding': 'br'}).headers.get('Content-Encoding') == 'br', path
    assert client.get('/' + path, headers={'Accept-Encoding': 'gzip, deflate'}).headers.get('Content-Encoding') == 'deflate', path


def test_compress_config(app):
    assert app.config['COMPRESS_MIN_SIZE'] == 500
    assert {'text/html', 'application/json', 'text/css', 'application/javascript', 'image/svg+xml', 'application/xml'} <= set(app.config['COMPRESS_MIMETYPES'])
    assert app.config['COMPRESS_ALGORITHM'][0] == 'br'


def test_socketio_polling_is_not_touched_by_compression(client):
    r = client.get('/socket.io/?EIO=4&transport=polling', headers={'Accept-Encoding': 'gzip, br'})
    assert r.status_code == 200 and 'Content-Encoding' not in r.headers


# ---------- sessions and logs ----------

def test_session_config(app):
    assert 'SESSION_FILE_DIR' not in app.config  # signed cookie sessions, no server-side files (docs/DEPLOY.md item 1)
    assert timedelta(hours=1) <= app.config['PERMANENT_SESSION_LIFETIME'] <= timedelta(days=2)


def test_log_file_is_rotated():
    import logging.handlers
    handlers = [h for h in logging.getLogger('app').handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
    assert handlers and handlers[0].maxBytes > 0 and handlers[0].backupCount >= 1


def test_templates_do_not_autoreload_outside_debug(app):
    assert app.config['TEMPLATES_AUTO_RELOAD'] is False
    assert app.jinja_env.bytecode_cache is not None


# CSP header and inline-code checks live in tests/test_csp.py

# ---------- memory ----------

def test_memory_growth_over_300_requests(app, patient_client, provider_client, client):
    """tracemalloc loop over key endpoints: allocations must plateau after warm-up (skip with -k 'not memory_growth')."""
    pc, uid = patient_client
    vc, pid = provider_client
    _seed_caseload(app, pid, 5)
    with app.app_context():
        db.session.add_all([MoodLog(user_id=uid, mood_score=5) for _ in range(20)])
        db.session.commit()
    hits = [(client, '/'), (client, '/login'), (client, '/blog/'), (client, '/health'), (pc, '/api/mood'),
            (pc, '/patient/dashboard'), (pc, '/patient/api/progress'), (vc, '/provider/dashboard'), (vc, '/provider/analytics')]

    def run(n):
        for i in range(n):
            c, url = hits[i % len(hits)]
            assert c.get(url).status_code in (200, 302)

    run(60)  # warm-up: template compilation, route caches, pooled connections
    tracemalloc.start(1)
    try:
        run(18)
        before = tracemalloc.take_snapshot()
        run(300)
        after = tracemalloc.take_snapshot()
    finally:
        tracemalloc.stop()
    growth = sum(s.size_diff for s in after.compare_to(before, 'filename'))
    top = after.compare_to(before, 'lineno')[:5]
    print(f'tracemalloc net growth over 300 requests: {growth / 1024:.0f} KiB')
    assert growth < 4 * 1024 * 1024, f'{growth / 1e6:.1f} MB growth over 300 requests; top: {[str(t) for t in top]}'
