# Matchmaking integration review — 2026-10-24

Both refreshed `origin/feature/matchmaking` branches descend directly from their
respective `origin/main` branches. Git's merge simulation reported no conflicts.
The original features had runtime and privacy blockers. The fixes below were
validated on `codex/matchmaking-integration`, then organized as separate commits
on `feature/matchmaking` and included in the local `main` integration. Remote
branches were left unchanged; no push was performed.

| Repository | Main reviewed | Feature reviewed |
| --- | --- | --- |
| Backend | `4b04fc5` | `87ad955` |
| Frontend | `ad68254` | `501b0d1` |

## Fixes

- Demand matchmaking follows the existing demand visibility policy. Private,
  inaccessible and inactive-owner demands do not leak existence or category.
- Startup recommendations require the correct active role and omit every demand
  with a previous proposal from that startup, including withdrawn proposals.
- Sector comparison uses exact normalized slug/name equivalence, including
  accented and legacy names, without substring false positives. Signup, profile
  editing and `/me/` now preserve the sector throughout the frontend/API flow.
- Rankings use completed, reviewed deliveries and deterministic tie breakers.
  Invalid, nonfinite and out-of-range `min_score` values return HTTP 400.
- Recommendation actions open the actual proposal form. Submitted opportunities
  disappear immediately. Clients can open startup rankings for their demands.
- Account, tab and request guards prevent delayed responses from restoring private
  recommendations or demand context after logout. Error states discard stale data.
- Worker shell v9 updates the new assets through the existing explicit update
  prompt. Private matchmaking endpoints never enter the service-worker cache.
- PostgreSQL and shared Redis defaults were restored. The feature's silent SQLite
  and local-memory fallbacks weakened the established deployment assumptions.
- UI terminology describes client reviews and estimated impact rather than
  claiming independent audits or measured financial savings. The broad public
  directory includes unreviewed startups; it is not an investment certification.
- OpenAPI was regenerated and validated with the actual response serializers,
  optional registration category and bounded `min_score` query parameter.

## Database

No new model migration is necessary: `StartupProfile.category` already exists in
`profiles.0001_initial`. `makemigrations --check --dry-run` reports no changes.
All existing migrations applied successfully to a fresh isolated PostgreSQL 16.15
cluster. `migrate --check` confirms no pending migrations there. The test suite
also exercises historical profile imports and rollback, plus concurrent proposal
acceptance and review creation using separate PostgreSQL connections.

Database creation and migration were performed only in the disposable review
cluster under `/tmp/starup-review-postgres`; no existing application or production
database was updated. The temporary preview servers and PostgreSQL cluster were
stopped after verification; the disposable files remain under `/tmp`.
For an application deployment, use the environment in
[development.md](development.md) and run `python manage.py migrate` against that
explicitly configured database.

The implementation follows Django's [migration workflow](https://docs.djangoproject.com/en/5.2/topics/migrations/).
PostgreSQL remains the supported runtime because SQLite does not implement the
[row locking used by the write services](https://docs.djangoproject.com/en/5.2/ref/databases/#sqlite-notes).
Redis preserves shared throttles across workers; Django's
[local-memory cache is per process](https://docs.djangoproject.com/en/5.2/topics/cache/#local-memory-caching).

## Validation results

| Check | Result |
| --- | --- |
| Complete backend suite, Python 3.12.14 / Django 5.2.18 / PostgreSQL 16.15 | 203 passed |
| Matchmaking backend regression tests | 49 passed |
| Matchmaking module and API view coverage | 141 statements, 100% |
| Frontend behavioral tests plus service-worker tests | 21 passed |
| JavaScript syntax (`app.js`, `service-worker.js`) | Passed |
| Ruff and Black for configured API apps, config and tests | Passed, 95 Python files checked by Black |
| Django system checks, including production settings `check --deploy` | No issues |
| Missing and pending migration checks | No changes / none pending |
| OpenAPI generation with validation and fail-on-warning | Passed |
| Whitespace/diff checks in both repositories | Passed |
| Independent final code review | No remaining actionable blockers found |

The new session integration regression uses actual CSRF-protected registration
and login, the seeded category taxonomy, sector editing, recommendation ordering,
proposal submission, acceptance, execution, delivery, review, traction filtering,
role permissions, privacy and logout. Ranking query counts are constant as the
fixture size grows: demand matches 2, recommendations 2, showcase 1.

Browser verification used synthetic accounts in the disposable database, served
by Django from the sibling frontend repository on the same origin:

1. Startup login showed logistics ahead of finance; the recommendation button
   opened the real form and posted a proposal.
2. Sector selection saved and returned through the profile endpoint.
3. Client demand rankings and received proposals displayed the matched startup.
4. The client accepted; the startup started execution and recorded delivery; the
   client confirmed with five stars. The public score rose from 52.5 to 80.9,
   with one completed test and the “Entrega bem avaliada” badge.
5. A second proposal disappeared immediately from recommendations, leaving the
   correct empty state instead of a duplicate-submit action.
6. Investor login displayed “Leitura privada” and read-only ranking controls.
7. An existing older PWA shell offered an explicit update; activating it loaded
   matchmaking. The final preview had no browser console errors or warnings.
8. Visual inspection caught missing tab classes; the controls now reuse the
   existing selected-tab styles and have a labeled accessible group.

Reproduce automated checks after configuring a dedicated PostgreSQL test account:

```bash
# Backend
.venv/bin/python -m pytest -q --tb=short
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py migrate --check
.venv/bin/python manage.py spectacular --file openapi.yaml --validate --fail-on-warn

# Frontend (Node.js on PATH)
node --check app.js
node --check service-worker.js
node --test tests/*.test.cjs
```

The Compose stack was not run: this environment has no Docker/Podman runtime.
Its configured PostgreSQL 17 image, real Redis multiworker operation, production
infrastructure and real Web Push delivery were not independently exercised in
this review. Push transport remains covered by the existing simulated tests.
Passing tests establish the checked behavior at these revisions; production
readiness still depends on the documented deployment configuration.
