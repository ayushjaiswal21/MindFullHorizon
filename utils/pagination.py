"""Pagination contract for list endpoints (documented in docs/PERFORMANCE.md).

`?page=` (1-based) and `?per_page=` (default 20, max 100). Bad values clamp and never raise:
non-numbers fall back to the default, numbers are clamped into range. A page past the end is an empty list.
"""
from flask import request


def _clamp(raw, default, low, high):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


def page_args(default=20, max_per_page=100):
    """(page, per_page) from the query string. Callers whose JS has no paging UI pass a larger `default`."""
    page = _clamp(request.args.get('page'), 1, 1, 1_000_000)
    per_page = _clamp(request.args.get('per_page'), min(default, max_per_page), 1, max_per_page)
    return page, per_page


def page_meta(page, per_page, total):
    return {'page': page, 'per_page': per_page, 'total': total, 'has_next': page * per_page < total}


def paginate(query, default=20, max_per_page=100):
    """Run an already ordered query. Returns (rows, meta). One COUNT plus one LIMIT/OFFSET statement."""
    page, per_page = page_args(default, max_per_page)
    total = query.order_by(None).count()
    rows = query.limit(per_page).offset((page - 1) * per_page).all()
    return rows, page_meta(page, per_page, total)


def set_page_headers(response, meta):
    """For endpoints whose body is a bare JSON array (old clients): the meta goes in headers instead."""
    response.headers['X-Page'] = str(meta['page'])
    response.headers['X-Per-Page'] = str(meta['per_page'])
    response.headers['X-Total-Count'] = str(meta['total'])
    response.headers['X-Has-Next'] = 'true' if meta['has_next'] else 'false'
    return response
