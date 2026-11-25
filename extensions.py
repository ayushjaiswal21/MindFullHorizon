"""Backward-compat shim: real implementation moved to core/extensions.py.

Kept so the many existing ``from extensions import ...`` / ``import extensions``
call sites across routes/, services/, utils/ and tests/ keep working unchanged.
"""
from core.extensions import (  # noqa: F401
    db, migrate, compress, csrf, cache, limiter,
    COMPRESS_TYPES, cache_config, init_extensions,
)
