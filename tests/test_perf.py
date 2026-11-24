"""Performance guards: lazy imports, pool config, query counts, pagination, caching, compression, memory.

Run all: `pytest tests/test_perf.py -q`. Skip the slower memory loop: `-k "not memory_growth"`.
"""
import gzip
import json
import logging
import os
import re
import subprocess
import sys
import time
import tracemalloc
import warnings
from datetime import date, datetime, timedelta

import pytest
from cachelib import SimpleCache
from flask import Flask
from sqlalchemy import event, text

from extensions import cache, db
from models import (Appointment, Assessment, BlogComment, BlogLike, BlogPost, ClinicalNote, DigitalDetoxLog,
                    JournalEntry, MoodLog, Notification, ProviderPatient, VoiceLog)
from utils.database_utils import engine_options, normalize_db_url
from utils.pagination import page_args

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


def _count_queries(app, fn):
    with app.app_context():
        with QueryCounter() as q:
            fn()
        return q.n


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
            from models import User
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


# ---------- 1. lazy imports ----------

def test_import_app_does_not_load_heavy_libraries(tmp_path):
    code = ("import sys, app; heavy = sorted(m for m in ('nltk', 'librosa', 'numpy', 'textblob', 'scipy', 'sklearn')"
            " if m in sys.modules); print('HEAVY:' + ','.join(heavy))")
    env = dict(os.environ, DATABASE_URL='sqlite:///' + str(tmp_path / 'lazy.db').replace('\\', '/'),
               SECRET_KEY='x', FLASK_ENV='testing', GEMINI_API_KEY='')
    out = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-500:]
    assert 'HEAVY:' in out.stdout and out.stdout.strip().endswith('HEAVY:'), out.stdout[-300:]


def test_sentiment_helper_is_lazy_and_works():
    from utils import sentiment
    assert isinstance(sentiment.TEXTBLOB_AVAILABLE, bool)
    if sentiment.TEXTBLOB_AVAILABLE:
        assert sentiment.TextBlob('I feel good today').sentiment.polarity > 0


# ---------- 2. DB pooling and pragmas ----------

def test_engine_options_per_dialect():
    sqlite = engine_options('sqlite:///x.db')
    assert sqlite == {'connect_args': {'check_same_thread': False}}  # no pool arguments
    pg = engine_options('postgresql://u:p@h/db', env={})
    assert pg['pool_size'] == 5 and pg['max_overflow'] == 5 and pg['pool_timeout'] == 10
    assert pg['pool_recycle'] == 300 and pg['pool_pre_ping'] is True  # Neon suspends idle compute after 5 minutes
    assert 'statement_timeout=10000' in pg['connect_args']['options']
    tuned = engine_options('postgresql://h/db', env={'DB_POOL_SIZE': '8', 'DB_MAX_OVERFLOW': 'x', 'DB_POOL_TIMEOUT': '3'})
    assert tuned['pool_size'] == 8 and tuned['max_overflow'] == 5 and tuned['pool_timeout'] == 3  # bad value -> default


def test_postgres_scheme_is_normalised():
    assert normalize_db_url('postgres://u:p@h/db') == 'postgresql://u:p@h/db'
    assert normalize_db_url('postgresql://u:p@h/db') == 'postgresql://u:p@h/db'
    assert normalize_db_url(None) is None


def test_app_uses_dialect_options(app):
    assert app.config['SQLALCHEMY_ENGINE_OPTIONS'] == engine_options(app.config['SQLALCHEMY_DATABASE_URI'])


def test_sqlite_pragmas_set_on_connect(app):
    with app.app_context():
        get = lambda p: db.session.execute(text(f'PRAGMA {p}')).scalar()
        assert str(get('journal_mode')).lower() == 'wal'
        assert get('synchronous') == 1  # NORMAL
        assert get('busy_timeout') == 5000
        assert get('foreign_keys') == 1  # the pre-existing listener still runs


# ---------- query counts ----------

def test_provider_dashboard_query_count_is_flat(app, make_user, provider_client):
    c, pid = provider_client
    _seed_caseload(app, pid, 3)
    few = _count_queries(app, lambda: c.get('/provider/dashboard'))
    _seed_caseload(app, pid, 30)
    many = _count_queries(app, lambda: c.get('/provider/dashboard'))
    assert many <= 25, many
    assert many <= few + 2, (few, many)  # 11x the patients must not add queries


def _seed_appointments(app, pid):
    with app.app_context():
        have = db.session.query(Appointment).filter_by(provider_id=pid).count()
        for n, (uid,) in enumerate(db.session.query(ProviderPatient.patient_id).filter_by(provider_id=pid).all(), start=have):
            db.session.add(Appointment(user_id=uid, provider_id=pid, date=date.today(), time=f'{n // 60:02d}:{n % 60:02d}',
                                       appointment_type='video', status='pending'))
        db.session.commit()


def test_provider_analytics_and_appointments_query_counts_are_flat(app, provider_client):
    c, pid = provider_client
    _seed_caseload(app, pid, 6)  # at least K=5 people, so the aggregate branches all run
    _seed_appointments(app, pid)
    few_a = _count_queries(app, lambda: c.get('/provider/analytics'))
    few_p = _count_queries(app, lambda: c.get('/provider/appointments'))
    _seed_caseload(app, pid, 30)
    _seed_appointments(app, pid)
    assert _count_queries(app, lambda: c.get('/provider/analytics')) <= few_a + 1
    assert _count_queries(app, lambda: c.get('/provider/appointments')) <= few_p + 1


def test_blog_list_query_count_is_flat(app, make_user, client):
    author = make_user('provider')
    with app.app_context():
        for i in range(3):
            db.session.add(BlogPost(title=f'p{i}', content='c', author_id=author, is_published=True))
        db.session.commit()
    few = _count_queries(app, lambda: client.get('/blog/'))
    with app.app_context():
        for i in range(30):
            p = BlogPost(title=f'q{i}', content='c', author_id=author, is_published=True)
            db.session.add(p)
            db.session.flush()
            db.session.add_all([BlogLike(user_id=author, post_id=p.id), BlogComment(user_id=author, post_id=p.id, content='x')]) if i < 1 else None
        db.session.commit()
    many = _count_queries(app, lambda: client.get('/blog/'))
    assert many <= few + 1 and many <= 8, (few, many)


def test_blog_list_shows_counts(app, make_user, client):
    author = make_user('provider')
    with app.app_context():
        p = BlogPost(title='Counted', content='c', author_id=author, is_published=True)
        db.session.add(p)
        db.session.flush()
        db.session.add_all([BlogLike(user_id=author, post_id=p.id), BlogComment(user_id=author, post_id=p.id, content='x'),
                            BlogComment(user_id=author, post_id=p.id, content='y')])
        db.session.commit()
    html = client.get('/blog/').get_data(as_text=True)
    assert '1 like<' in html and '2 comments<' in html


def test_chat_messages_query_count_is_flat(app, patient_client, make_user):
    c, uid = patient_client
    sender = make_user('provider')
    with app.app_context():
        db.session.add_all([Notification(sender_id=sender, recipient_id=uid, message=f'm{i}') for i in range(60)])
        db.session.commit()
    assert _count_queries(app, lambda: c.get(f'/api/chats/{uid}/messages?per_page=50')) <= 6


# ---------- pagination contract ----------

def test_page_args_clamp(app):
    cases = [('', 1, 20), ('page=abc&per_page=zzz', 1, 20), ('page=0&per_page=0', 1, 1), ('page=-4&per_page=-9', 1, 1),
             ('page=3&per_page=1000', 3, 100), ('page=2&per_page=7', 2, 7), ('page=9999999999&per_page=5', 1_000_000, 5)]
    for qs, page, per in cases:
        with app.test_request_context('/?' + qs):
            assert page_args() == (page, per), qs
    with app.test_request_context('/?per_page=500'):
        assert page_args(default=100) == (1, 100)


@pytest.mark.parametrize('qs', ['', '?page=abc&per_page=-1', '?page=0&per_page=100000', '?page=99999&per_page=3'])
def test_paginated_endpoints_never_500(app, patient_client, make_user, qs):
    c, uid = patient_client
    with app.app_context():
        db.session.add_all([MoodLog(user_id=uid, mood_score=5) for _ in range(5)])
        db.session.add_all([JournalEntry(user_id=uid, title='t', content='c') for _ in range(3)])
        db.session.add_all([VoiceLog(user_id=uid, filename='f.wav') for _ in range(3)])
        db.session.commit()
    for url in ('/api/mood', '/patient/api/progress', '/patient/api/digital-detox-data', f'/api/chats/{uid}/messages',
                '/patient/api/goals', '/patient/journal', '/patient/voice-logs', '/blog/'):
        assert c.get(url + qs).status_code == 200, url + qs


def test_mood_pagination_shape_and_order(app, patient_client):
    c, uid = patient_client
    with app.app_context():
        for i in range(25):
            db.session.add(MoodLog(user_id=uid, mood_score=1 + i % 10, created_at=datetime(2026, 1, 1) + timedelta(hours=i)))
        db.session.commit()
    body = c.get('/api/mood').get_json()
    assert body['ok'] is True and len(body['moods']) == 20  # legacy key kept
    assert body['meta'] == {'page': 1, 'per_page': 20, 'total': 25, 'has_next': True}
    stamps = [m['created_at'] for m in body['moods']]
    assert stamps == sorted(stamps) and stamps[-1].startswith('2026-01-02T0')  # newest page, oldest-to-newest
    p2 = c.get('/api/mood?page=2&per_page=20').get_json()
    assert len(p2['moods']) == 5 and p2['meta']['has_next'] is False
    assert c.get('/api/mood?per_page=1000').get_json()['meta']['per_page'] == 100


def test_chat_messages_stay_a_bare_array_with_headers(app, patient_client, make_user):
    c, uid = patient_client
    sender = make_user('provider')
    with app.app_context():
        db.session.add_all([Notification(sender_id=sender, recipient_id=uid, message=f'm{i}') for i in range(30)])
        db.session.commit()
    r = c.get(f'/api/chats/{uid}/messages')
    assert isinstance(r.get_json(), list) and len(r.get_json()) == 20
    assert r.headers['X-Total-Count'] == '30' and r.headers['X-Has-Next'] == 'true' and r.headers['X-Per-Page'] == '20'
    assert [m['text'] for m in r.get_json()][-1] == 'm29'


def test_provider_appointments_meta_default_100(app, provider_client):
    c, pid = provider_client
    body = c.get('/provider/appointments').get_json()
    assert body['success'] is True and body['appointments'] == []
    assert body['meta'] == {'page': 1, 'per_page': 100, 'total': 0, 'has_next': False}


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


# ---------- CSP switch ----------

def test_csp_enforce_switch(app, client):
    assert 'Content-Security-Policy-Report-Only' in client.get('/login').headers
    app.config['CSP_ENFORCE'] = True
    try:
        h = client.get('/login').headers
        assert 'Content-Security-Policy' in h and 'Content-Security-Policy-Report-Only' not in h
    finally:
        app.config['CSP_ENFORCE'] = False


def test_report_inline_handlers_and_scripts_without_nonce():
    """Report only (never fails): what must be gone before CSP_ENFORCE=1 can be flipped."""
    handler = re.compile(r'<[a-zA-Z][^>]*\son[a-z]+\s*=', re.S)
    script = re.compile(r'<script\b(?![^>]*\bsrc=)(?![^>]*\bnonce=)(?![^>]*type=["\']application/(?:ld\+)?json)[^>]*>', re.S)
    findings = []
    tdir = os.path.join(ROOT, 'templates')
    for dirpath, _, files in os.walk(tdir):
        for f in files:
            if f.endswith('.html'):
                src = open(os.path.join(dirpath, f), encoding='utf-8').read()
                h, s = len(handler.findall(src)), len(script.findall(src))
                if h or s:
                    findings.append(f'{os.path.relpath(os.path.join(dirpath, f), ROOT)}: {h} inline on*= attributes, {s} inline scripts without nonce')
    if findings:
        warnings.warn('CSP_ENFORCE blockers:\n  ' + '\n  '.join(findings), stacklevel=1)
    print(f'CSP blockers in {len(findings)} templates')


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
