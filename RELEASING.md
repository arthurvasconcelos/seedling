# Releasing

Steps to cut a release for any phase (0.x or 1.0).

## Pre-release checklist

1. **CI green on `main`** — ruff, mypy, and the full pytest matrix (PostgreSQL +
   SQLite + MariaDB) must all pass.
2. **CHANGELOG updated** — move `## [Unreleased]` content under a dated heading
   (`## [0.X.0] - YYYY-MM-DD`) and add a fresh empty `## [Unreleased]` above it.
3. **Version bumped** — set `version = "0.X.0"` in `pyproject.toml`.
4. **Commit + PR + merge** the changelog and version bump to `main`.

## Tagging & publishing

```bash
git tag -a v0.X.0 -m "Release 0.X.0"
git push origin v0.X.0
```

The `publish.yml` workflow triggers on tag pushes and publishes to PyPI
automatically. Verify the upload at <https://pypi.org/project/sqlalchemy-seedling/>.

After the tag is live:

- Create a **GitHub Release** from the tag; paste the changelog excerpt as the
  release notes.
- Install in a clean venv to confirm: `pip install sqlalchemy-seedling==0.X.0`.
- Rebuild the docs site if it is version-pinned.

## If something goes wrong

Do **not** yank the release unless it is actively harmful to users. Yanking is
a strong signal that causes confusion. Prefer shipping a `0.X.1` patch instead.

## 1.0 RC process

1. Bump `pyproject.toml` to `1.0.0rc1` and add a `## [1.0.0rc1]` CHANGELOG entry.
2. Tag `v1.0.0rc1` and push — PyPI auto-recognises `rc` versions as pre-releases
   (users need `pip install sqlalchemy-seedling==1.0.0rc1` or `--pre`).
3. Add an RC banner to the README and docs site.
4. Open a pinned GitHub issue titled "1.0 release feedback thread" — explain what
   RC means, link the migration guide and changelog, ask for specific feedback.
5. **RC window: 2–4 weeks.** Triage incoming issues into *blocker*, *1.1 candidate*,
   or *won't fix*. Reply to everything.
6. If only minor feedback → tag `v1.0.0`. If real bugs or API issues → fix, ship
   `rc2`, restart a shorter clock.
7. On `1.0.0`: remove the RC banner, add a "Stable since YYYY-MM-DD" badge, announce
   in the same channels used for the RC.
