# PyPI Publish Protocol — bhgman_tool

> **Status (2026-05-14):** packaging audit complete, build verified, **publish step gated by user verdict**.
> KG provenance: `lesson-stale-source-citation-drift-aten-jesus-2026-04-30` (canon-propagation rule applies — bump version in `pyproject.toml`, `engine/cli/main.py:PACKAGE_VERSION`, and CHANGELOG simultaneously).

---

## 0. Pre-flight checklist

1. **Version bump.** Three call sites must agree:
   - `pyproject.toml` → `[project] version = "X.Y.Z"`
   - `engine/cli/main.py` → `PACKAGE_VERSION = "X.Y.Z"`
   - git tag `vX.Y.Z` (after publish)
2. **Tests green.**
   ```bash
   cd engine/longinus_drift_audit && uv run --with pytest pytest tests/ -q
   # expected: 77 passed
   cd ../cli && uv run --with pytest pytest tests/ -q
   # expected: green
   ```
3. **Lean still passes** (smoke, optional but recommended):
   ```bash
   cd lean && lean Longinus_ConfidenceSchema_GraphifyAbsorbed.lean   # exit 0
   ```
4. **Working tree clean.** `git status` shows nothing uncommitted under `engine/`, `skills/`, `pyproject.toml`.

---

## 1. Build artifacts (local, no network)

```bash
cd /Users/lagyeongjun/CD/bhgman_tool
rm -rf dist build *.egg-info
uv build
# or, equivalently:
# python -m build
```

Expected output:

```
Successfully built dist/bhgman_tool-X.Y.Z.tar.gz
Successfully built dist/bhgman_tool-X.Y.Z-py3-none-any.whl
```

Inspect:

```bash
ls -la dist/
unzip -l dist/bhgman_tool-X.Y.Z-py3-none-any.whl | head -30
tar tzf dist/bhgman_tool-X.Y.Z.tar.gz | head -30
```

Verify the wheel contains `engine/` (cli + gate + resolver + longinus_drift_audit + mcp_server + memory). It should **not** contain `.venv/`, `__pycache__/`, `.pytest_cache/`, `*.egg-info/`.

---

## 2. Smoke install (clean venv)

```bash
cd /tmp && rm -rf bhgman_smoke && uv venv bhgman_smoke --python 3.12
source bhgman_smoke/bin/activate
uv pip install /Users/lagyeongjun/CD/bhgman_tool/dist/bhgman_tool-X.Y.Z-py3-none-any.whl
bhgman-tool --help
bhgman-tool apt "smoke test" 2>&1 | head -3   # expects routing intent + SKILL.md path FAIL (no skills/ in venv → expected)
```

> Cohort A (`install-skills`, `verify`, `version`) **requires source repo** — wheel-only install gives `RuntimeError: bhgman_tool repo root not found`. This is documented behavior, not a packaging bug.

---

## 3. Twine check (metadata sanity)

```bash
uv pip install --upgrade twine
python -m twine check dist/*
```

Expected: `PASSED` for both `.whl` and `.tar.gz`. If `RST validation` fails, the README has Markdown PyPI cannot render — fix and rebuild.

---

## 4. TestPyPI dry-run (recommended before real publish)

1. Create TestPyPI account: https://test.pypi.org/account/register/
2. Generate API token at https://test.pypi.org/manage/account/token/ (scope: entire account or `bhgman_tool`).
3. Export token (do **not** commit):
   ```bash
   export TWINE_USERNAME=__token__
   export TWINE_PASSWORD="pypi-AgEIcHlwaS5vcmcCJ...your-test-token..."
   ```
4. Upload to TestPyPI:
   ```bash
   python -m twine upload --repository testpypi dist/*
   # or with uv:
   # uv publish --publish-url https://test.pypi.org/legacy/ --token "$TWINE_PASSWORD"
   ```
5. Verify installable from TestPyPI:
   ```bash
   uv venv /tmp/bhgman_testpypi --python 3.12 && source /tmp/bhgman_testpypi/bin/activate
   uv pip install --index-url https://test.pypi.org/simple/ \
                  --extra-index-url https://pypi.org/simple/ \
                  bhgman_tool
   bhgman-tool --help
   ```

---

## 5. Real PyPI publish (USER VERDICT GATED)

> **STOP.** This step requires explicit user verdict — once a version is published to PyPI it cannot be replaced (only yanked + re-released as X.Y.Z+1). Do not skip TestPyPI dry-run.

1. Create PyPI account: https://pypi.org/account/register/
2. Generate API token at https://pypi.org/manage/account/token/ (scope: `bhgman_tool` once first upload exists, or "entire account" for first upload).
3. Store token in `~/.pypirc` (mode 600) or use env var:
   ```ini
   # ~/.pypirc
   [pypi]
     username = __token__
     password = pypi-AgEIcHlwaS5vcmcCJ...
   ```
   or:
   ```bash
   export TWINE_USERNAME=__token__
   export TWINE_PASSWORD="pypi-..."
   ```
4. Upload:
   ```bash
   python -m twine upload dist/*
   # or with uv:
   # uv publish --token "$TWINE_PASSWORD"
   ```
5. Verify on PyPI: https://pypi.org/project/bhgman_tool/
6. Verify installable:
   ```bash
   uv venv /tmp/bhgman_real --python 3.12 && source /tmp/bhgman_real/bin/activate
   uv pip install bhgman_tool
   bhgman-tool --help
   ```

---

## 6. Post-publish

1. **Tag the release**:
   ```bash
   git tag -a vX.Y.Z -m "Release X.Y.Z"
   git push origin vX.Y.Z
   ```
2. **GitHub Release** (optional but recommended):
   ```bash
   gh release create vX.Y.Z dist/bhgman_tool-X.Y.Z-py3-none-any.whl dist/bhgman_tool-X.Y.Z.tar.gz \
      --title "bhgman_tool X.Y.Z" --notes "See CHANGELOG and commit history."
   ```
   Active gh account must be `gira-airobotics` if pushing to org repo; otherwise `gj3447` works for the personal mirror. See memory `reference_gh_active_account_for_symposium_push.md`.
3. **Bump `version` to next dev** in `pyproject.toml` + `engine/cli/main.py` to avoid accidental re-publish of the same number.

---

## 7. Trusted Publishing (future, optional)

GitHub Actions can publish without a long-lived token via OIDC. Configure at https://pypi.org/manage/account/publishing/ and add `.github/workflows/publish.yml` with `pypa/gh-action-pypi-publish@release/v1`. **Not enabled yet** — current protocol is manual twine + user verdict.

---

## 8. Rollback / yank

If a release ships broken metadata or wrong files:

```bash
# yank (hides from new installs but keeps it for existing pins)
twine yank bhgman_tool X.Y.Z
# or via PyPI web UI: Project → Manage → Releases → Yank
```

You **cannot** re-upload `X.Y.Z` after yanking. Bump to `X.Y.(Z+1)` and re-publish.

---

## Honest scope (Goodhart safeguard)

- This doc covers **packaging + publish protocol** only. It does not certify content correctness — that's the job of pytest (`engine/`) + Lean (`lean/`) + Naesengmoon skill (`tlb`).
- "All 298 pytest PASS" claim is a **smoke**-level guarantee, not a coverage report. See `engine/longinus_drift_audit/README.md` for honest limitations.
- The wheel's `engine.cli` cohort A subcommands (`install-skills`, `verify`, `version`) are **not** usable from a pip-installed wheel alone — they require the source repo. This is documented in `engine/cli/main.py` module docstring (lines 33-41).

# KG: ad-bhgman-pypi-publish-protocol-2026-05-14 (:Documentation:PublishProtocol)
# KG: lesson-stale-source-citation-drift-aten-jesus-2026-04-30 (canon-propagation rule: 3 call sites must agree on version)
