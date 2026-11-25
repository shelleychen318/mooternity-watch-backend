"""HTTP API layer: routers and request-scoped dependencies.

Routers live in their own modules (e.g. :mod:`app.api.snapshots`) and are
mounted onto the app in :func:`app.main.create_app`. Shared dependencies — most
importantly device authentication — live in :mod:`app.api.deps`.
"""

from __future__ import annotations
