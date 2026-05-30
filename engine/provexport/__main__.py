"""`python -m engine.provexport <cycle_id> [--findings-json ...] [--format ...]`."""

from .prov_export import main

raise SystemExit(main())
