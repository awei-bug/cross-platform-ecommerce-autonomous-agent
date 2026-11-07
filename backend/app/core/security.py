"""Deprecated identity shims kept for import compatibility.

Identity now comes exclusively from a verified 云购 session
(see :mod:`app.core.identity`). ``require_demo_user`` remains here as an alias
of the real identity dependency so existing imports and
``app.dependency_overrides`` call sites keep resolving to the same function
object; it no longer accepts a fixed demo token on its own.
"""

from app.core.identity import DEMO_ACCESS_TOKEN, require_session

# Alias, not a second implementation: overriding one overrides the other.
require_demo_user = require_session

__all__ = ["DEMO_ACCESS_TOKEN", "require_demo_user"]
