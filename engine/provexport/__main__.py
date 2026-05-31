"""`python -m engine.provexport <cycle_id> [--findings-json ...] [--format ...]`."""
# KG: ATOM_Skill_longinus

from .prov_export import main

raise SystemExit(main())
