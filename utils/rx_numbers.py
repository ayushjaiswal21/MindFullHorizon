"""Prescription numbers: RX{YYMM in IST}-{10 random chars}{check} (design 3.7).

Crockford alphabet (no I, L, O, U). The check character lets the desk catch typing errors before a lookup.
"""
import re
import secrets

from utils.timeutil import ist_now

ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
_NUMBER_RE = re.compile(r'RX\d{4}-[' + ALPHABET + r']{11}')


def _check(body):
    return ALPHABET[sum((i + 1) * ALPHABET.index(c) for i, c in enumerate(body)) % 32]


def new_number(now=None):
    """`now` is a naive IST wall-clock datetime (defaults to the current IST time)."""
    now = now or ist_now()
    body = ''.join(secrets.choice(ALPHABET) for _ in range(10))
    return f'RX{now:%y%m}-{body}{_check(body)}'


def normalise(value):
    return (value or '').strip().upper().replace(' ', '')


def is_valid_number(value):
    """Shape and check character. Says nothing about whether the prescription exists."""
    s = normalise(value) if isinstance(value, str) else ''
    return bool(_NUMBER_RE.fullmatch(s)) and _check(s[7:17]) == s[17]


def mask_rx(number):
    """Part of the number for administrators who are not the pharmacy desk: first 7 and last 3 characters."""
    if not number:
        return ''
    return number[:7] + '*' * 8 + number[-3:]
