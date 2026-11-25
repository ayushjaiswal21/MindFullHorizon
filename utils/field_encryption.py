"""Column-level encryption at rest for clinical free text (O-04, docs/TRACKER.md).

`EncryptedText`/`EncryptedJSON` are SQLAlchemy `TypeDecorator`s: Python code reads and writes plain
str/JSON as always (transparent at the ORM boundary); the DB column stores Fernet ciphertext bytes
(`LargeBinary`, works the same on SQLite and Postgres). Equality filtering on ciphertext is possible in
principle but pointless (non-deterministic nonce); there is no `LIKE`/`ILIKE`/full-text search on any
field this module encrypts today (checked on O-04) and none should be added without a different design
(e.g. a separate searchable-hash column).

Key: FIELD_ENCRYPTION_KEY, a urlsafe-base64 Fernet key (`Fernet.generate_key()`), same env-var
convention as SECRET_KEY in app.py. Missing in production is a hard error; missing in dev/test falls
back to a random per-process key with a warning (encrypted data becomes unreadable after a restart,
which is fine for a throwaway dev/test DB but never acceptable for the real database).
"""
import json
import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import LargeBinary, TypeDecorator

logger = logging.getLogger(__name__)

_cipher = None


def _get_cipher():
    global _cipher
    if _cipher is not None:
        return _cipher
    key = os.getenv('FIELD_ENCRYPTION_KEY')
    if not key:
        if os.getenv('FLASK_ENV') == 'production':
            raise RuntimeError("FIELD_ENCRYPTION_KEY must be set in production")
        logger.warning("FIELD_ENCRYPTION_KEY not set: using a random per-process key "
                        "(encrypted data unreadable after a restart)")
        key = Fernet.generate_key()
    _cipher = Fernet(key.encode('utf-8') if isinstance(key, str) else key)
    return _cipher


def reset_cipher_cache():
    """Test hook: forget the cached cipher so a changed FIELD_ENCRYPTION_KEY takes effect."""
    global _cipher
    _cipher = None


class EncryptedText(TypeDecorator):
    """Text column, encrypted at rest. Never log `value` here (CLAUDE.md: never log patient text)."""
    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _get_cipher().encrypt(value.encode('utf-8'))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return _get_cipher().decrypt(bytes(value)).decode('utf-8')
        except InvalidToken:
            logger.error("field decryption failed: wrong or rotated FIELD_ENCRYPTION_KEY")
            raise


class EncryptedJSON(EncryptedText):
    """JSON column (dict/list of free text), encrypted at rest as its JSON-serialised form."""

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return super().process_bind_param(json.dumps(value), dialect)

    def process_result_value(self, value, dialect):
        text = super().process_result_value(value, dialect)
        if text is None:
            return None
        return json.loads(text)
