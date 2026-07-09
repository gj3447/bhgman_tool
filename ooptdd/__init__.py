"""Local ``ooptdd`` package shim — adds this repo's ``ooptdd/`` dir (the ooptdd-loop
adapter lives here) onto the SAME import package as the installed ``ooptdd`` backend lib.

The installed distribution ``ooptdd`` (``…/ooptdd/src/ooptdd``) provides ``ooptdd.backends``,
``ooptdd.ontology`` etc.; this repo additionally ships ``ooptdd.adapter`` here. Without
merging the two locations, ``import ooptdd.adapter`` resolves to the installed package and
fails (ModuleNotFoundError). ``extend_path`` unions both directories under the one
``ooptdd`` package so BOTH resolve: ``ooptdd.adapter`` (here) and ``ooptdd.backends`` (lib).
"""

from __future__ import annotations

from pkgutil import extend_path

# Union this directory with every other ``ooptdd`` on sys.path (notably the installed lib),
# so the package exposes both the repo-local adapter and the library submodules.
__path__ = extend_path(__path__, __name__)

# Best-effort: also fold in the installed distribution's own __path__ entries, in case it is
# a regular (non-namespace) package whose directory extend_path did not already include.
try:  # pragma: no cover - environment-dependent
    import importlib.util as _ilu

    _spec = _ilu.find_spec("ooptdd")
    for _p in getattr(_spec, "submodule_search_locations", None) or []:
        if _p not in __path__:
            __path__.append(_p)
except Exception:  # noqa: BLE001 - never break import on a discovery miss
    pass

# Re-export the installed library's public API through the merged path. This shim file
# SHADOWS the installed distribution's __init__ (the first ``ooptdd`` on sys.path wins),
# so without these the documented public surface (``from ooptdd import evaluate`` …)
# breaks in every sibling-installed dev venv — 2026-07-09 audit: 8 receipt suites RED
# locally while CI stayed green with the sibling absent (reverse fake-green). The names
# mirror exactly what ooptdd_loop imports from the top level; submodules resolve through
# the merged __path__ above.
try:  # pragma: no cover - only bites when the sibling lib is installed
    from ooptdd.backends import get_backend  # noqa: F401
    from ooptdd.domain.ontology import Ontology  # noqa: F401
    from ooptdd.engine.gate import evaluate, evaluate_events  # noqa: F401
    from ooptdd.engine.verify import verify_trace  # noqa: F401
except ImportError:  # sibling lib absent → repo-local adapter-only mode (CI)
    pass
