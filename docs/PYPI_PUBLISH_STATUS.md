# PyPI Publish Status — bhgman_tool v0.1.0

> **Status (2026-05-14):** `DEFERRED` — publish blocked at credential acquisition step.
> Companion doc: `PYPI_PUBLISH.md` (protocol). This file = audit result of an actual publish attempt.

---

## TL;DR

```
publish_target  : docs_only
publish_result  : DEFERRED
package_url     : null
git_tag_created : false
reason          : no PYPI_API_TOKEN (env / ~/.pypirc / gh secret / keychain all empty)
```

Build artifacts already verified PASS on 2026-05-14 — wheel + sdist sitting in `dist/`,
`twine check` previously PASSED. The only missing piece is a valid PyPI (or TestPyPI) API
token. Creating the account + generating a token is a **user verdict gate** (per
`PYPI_PUBLISH.md §5` — "Real PyPI publish (USER VERDICT GATED)") and cannot be silently
auto-executed by an autonomous agent.

---

## 1. Credential audit (attempted sources)

| Source | Result | Notes |
|---|---|---|
| `env PYPI_API_TOKEN` | empty | `env \| grep -i pypi` → no match |
| `env TWINE_PASSWORD` | empty | no twine env vars set |
| `~/.pypirc` | absent | file does not exist |
| `~/.local/share/uv/credentials` | empty/no pypi entry | uv credential store has no pypi/testpypi token |
| GitHub secret `gj3447/bhgman_tool` | HTTP 403 | active `gh` account = `gira-airobotics`, no read perm on `gj3447` repo secrets |
| macOS keychain `pypi` / `testpypi` | not found | `security find-generic-password` returned `errSecItemNotFound` |

Conclusion: **no token available on this machine in any standard location.**

---

## 2. Existing build artifacts (verified earlier)

```
dist/bhgman_tool-0.1.0-py3-none-any.whl   141392 bytes  2026-05-14 15:50
dist/bhgman_tool-0.1.0.tar.gz             672969 bytes  2026-05-14 15:50
```

Both pass `python -m twine check` (recorded in commit `a8b622f` provenance and earlier
audit log). Build step does **not** need network or token — it is fully reproducible
locally via `uv build`.

---

## 3. Why not silently create a token?

1. PyPI account creation requires email verification + 2FA enrollment (interactive).
2. Token generation is account-bound; doing it on behalf of the user fragments
   provenance and violates the "USER VERDICT GATED" notice in `PYPI_PUBLISH.md §5`.
3. Once `0.1.0` is on real PyPI it cannot be replaced — only yanked + bumped to
   `0.1.1`. Cost-of-mistake asymmetry favors waiting for the explicit verdict.
4. TestPyPI fallback was considered, but **it also requires a TestPyPI account +
   token** (separate from PyPI). Same blocker, smaller blast radius — still gated.

This matches the `propose` / `defer` rule from
`CLAUDE.md §자율 실행 모드`: external credential absence is a specific blocker, so
defer with specific blocker (not generic "I'm not sure").

---

## 4. Resumption hooks — what unblocks publish

Pick **one** of A or B below; both leave the same final artifact on PyPI.

### A. User-supplied PyPI token (preferred for v0.1.0 — production)

```bash
# After generating token at https://pypi.org/manage/account/token/
export TWINE_USERNAME=__token__
export TWINE_PASSWORD="pypi-AgEIcHlwaS5vcmcCJ..."

cd /Users/lagyeongjun/CD/bhgman_tool
python -m twine upload dist/*
# expected: 'View at: https://pypi.org/project/bhgman_tool/0.1.0/'

git tag -a v0.1.0 -m "Release 0.1.0 — bhgman_tool first publish"
git push origin v0.1.0
gh release create v0.1.0 --title "bhgman_tool v0.1.0" \
   --notes "First publish. 17 axes external grounding + 89 Lean theorems + Goodhart safeguard."
```

After success: update `PYPI_PUBLISH_STATUS.md` with `publish_result: SUCCESS`,
`package_url: https://pypi.org/project/bhgman_tool/0.1.0/`, `git_tag_created: true`.

### B. TestPyPI dry-run first (safer if account is fresh)

```bash
# After generating test token at https://test.pypi.org/manage/account/token/
export TWINE_USERNAME=__token__
export TWINE_PASSWORD="pypi-AgEI..."   # test.pypi.org token, distinct from real PyPI

cd /Users/lagyeongjun/CD/bhgman_tool
python -m twine upload --repository testpypi dist/*
# verify at https://test.pypi.org/project/bhgman_tool/

uv venv /tmp/bhgman_testpypi --python 3.12
source /tmp/bhgman_testpypi/bin/activate
uv pip install --index-url https://test.pypi.org/simple/ \
               --extra-index-url https://pypi.org/simple/ \
               bhgman_tool
bhgman-tool --help   # smoke
```

Then proceed to A for real publish.

---

## 5. Pre-publish reminder — gh account switch

`gh` is currently active as `gira-airobotics` (SYMPOSIUM owner). For the
`v0.1.0` git tag push + GitHub Release on `gj3447/bhgman_tool`, **switch active
account** first (per `reference_gh_active_account_for_symposium_push.md` — same
pattern, opposite direction):

```bash
gh auth switch --user gj3447
git push origin v0.1.0
gh release create v0.1.0 ...

# (after publish) switch back to default
gh auth switch --user gira-airobotics
```

This is git+gh only — it does **not** affect the PyPI token, which is independent
of GitHub auth.

---

## 6. Provenance

- Build artifacts: commit `a8b622f` (wave10 pypi packaging prep)
- This status doc: created 2026-05-14 by automated publish-attempt audit
- KG hook: defer pattern follows `feedback_layer_split_symposium_vs_bhgman_tool.md`
  + `feedback_check_state_first.md` (read real env state before claiming token absence)
- Blocker class: **external credential acquisition** — same family as
  `lean-mathlib-functor-actual-build-2026-04-30` (:FutureSprint, user-decision gate)

---

## 7. One-line summary

`v0.1.0` build is publish-ready; the only thing standing between `dist/*.whl` and
`pypi.org/project/bhgman_tool/0.1.0/` is a user-supplied API token. Everything
else (version triple-sync, twine check, README rendering, wheel contents) was
verified in commit `a8b622f`.
