"""Back up the PostgreSQL database with pg_dump (custom format). NOT TESTED against a live database.

    python scripts/backup_db.py D:\\backups\\mindfull          # reads DATABASE_URL from the environment
    python scripts/backup_db.py ~/backups/mindfull --allow-pooler

Writes <dir>/mindfull-<UTC timestamp>.dump. Use the Neon DIRECT connection string (host without -pooler): pg_dump
needs session features the pooler lacks. Refuses to write inside this repository (backups hold student data and
must never be committed) unless --allow-in-repo. The URL is never printed and never put on the command line:
it is split into PG* environment variables for the pg_dump child process.
Needs the `pg_dump` program (PostgreSQL client tools) on PATH, version >= the server's major version.
Restore instructions: docs/DEPLOY.md section 7.
"""
import argparse
import datetime
import os
import shutil
import subprocess
import sys
from urllib.parse import parse_qs, unquote, urlsplit

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pg_env(url, base_env=None):
    """Split a postgres URL into PG* variables. Returns (env, host). Raises ValueError on a non-postgres URL."""
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    parts = urlsplit(url)
    if parts.scheme.split('+')[0] != 'postgresql' or not parts.hostname:
        raise ValueError('DATABASE_URL must be a postgresql:// URL with a host')
    env = dict(os.environ if base_env is None else base_env)
    env.update(PGHOST=parts.hostname, PGPORT=str(parts.port or 5432), PGDATABASE=unquote(parts.path.lstrip('/')))
    if parts.username:
        env['PGUSER'] = unquote(parts.username)
    if parts.password:
        env['PGPASSWORD'] = unquote(parts.password)
    query = parse_qs(parts.query)
    env['PGSSLMODE'] = (query.get('sslmode') or ['require'])[0]
    if query.get('channel_binding'):
        env['PGCHANNELBINDING'] = query['channel_binding'][0]
    return env, parts.hostname


def inside_repo(path):
    path, repo = os.path.realpath(path), os.path.realpath(REPO)
    try:
        return os.path.commonpath([path, repo]) == repo
    except ValueError:  # different drive on Windows
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description='pg_dump wrapper (custom format, timestamped file)')
    ap.add_argument('out_dir', help='directory for the dump file (outside the repository)')
    ap.add_argument('--allow-pooler', action='store_true', help='do not refuse a -pooler host')
    ap.add_argument('--allow-in-repo', action='store_true', help='allow writing inside the repository (do not)')
    args = ap.parse_args(argv)

    url = os.environ.get('DATABASE_URL', '').strip()
    if not url:
        print('DATABASE_URL is not set', file=sys.stderr)
        return 2
    try:
        env, host = pg_env(url)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if '-pooler' in host and not args.allow_pooler:
        print('The host is a Neon pooled endpoint. Use the DIRECT connection string (remove -pooler) or pass --allow-pooler.', file=sys.stderr)
        return 2
    if inside_repo(args.out_dir) and not args.allow_in_repo:
        print(f'Refusing to write inside the repository ({REPO}). Choose another directory.', file=sys.stderr)
        return 2
    if not shutil.which('pg_dump'):
        print('pg_dump not found on PATH. Install the PostgreSQL client tools (same major version as the server).', file=sys.stderr)
        return 2

    os.makedirs(args.out_dir, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target = os.path.join(args.out_dir, f'mindfull-{stamp}.dump')
    cmd = ['pg_dump', '--format=custom', '--no-owner', '--no-acl', '--file', target]
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        if os.path.exists(target):
            os.remove(target)  # never leave a truncated dump that looks like a backup
        print(f'pg_dump failed (exit {result.returncode}); no file kept', file=sys.stderr)
        return 1
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    print(f'Wrote {target} ({os.path.getsize(target)} bytes). Keep it private: it contains student data.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
