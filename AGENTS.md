# Trailblazing Turtle — Agent Instructions

## Overview
Django 5.2 web portal for HPC/OpenStack cluster usage visualization. Modular architecture — each feature is a Django app that can be enabled/disabled.

## Key Commands

```bash
# Lint (CI uses max-line-length 200, excludes settings/)
flake8 --max-line-length 200 --extend-exclude 'userportal/settings/,example/' .

# Run tests (requires running database, see Testing section)
python manage.py test

# Run a single app's tests
python manage.py test jobstats

# Build docs
mkdocs build --strict

# Production static files
python manage.py collectstatic --noinput
python manage.py compilemessages
```

## Settings — Critical Gotcha
Settings are **split across files** in `userportal/settings/`. The `userportal/settings.py` loader glob-imports all `*.py` files in that directory, **executing them in alphabetical order**. Local overrides go in `*-local.py` (gitignored).

Production deploys copy `99-local.py` at runtime via `run-django-production.sh`.

Flake8 on CI **excludes** `userportal/settings/` entirely.

## Multi-Database Architecture
Three databases configured in `userportal/settings/20-databases.py`:
- `default` — MySQL (Django internals)
- `slurm` — MySQL/SacctManager (Slurm accounting, read-only)
- `ldap` — LDAP via django-ldapdb

Routing is handled by `database_routers.dbrouters.DbRouter`. Tests that touch the slurm database must declare `databases = '__all__'` (see `tests/tests.py`).

## Testing Quirks
- Custom test runner (`userportal.testrunner.CustomTestRunner`) **skips creating a test DB** for the `slurm` alias. Tests run against the real slurm database.
- Base test utilities live in `tests/tests.py` (`CustomTestCase` provides logged-in user/admin clients). All module tests inherit from it.
- Each Django app has its own `tests.py` file (14 modules total).
- The `90-tests.py` settings file defines test fixtures (`TESTS_USER`, `TESTS_JOBSTATS`, etc.).
- Tests cannot run without a live MySQL database for the slurm backend.

## Patches Applied at Build Time
The `Containerfile` applies two patches to installed packages:
- `ldapdb.patch` — disables LDAP paged results (breaks pagination cookie loop)
- `dbcheck.patch` — disables Django DB version check (MariaDB on EL8 compatibility)

These patches are required for the container image to function. Local dev may need them too.

## Module Structure
Each feature module (`jobstats`, `top`, `nodes`, `accountstats`, etc.) is a self-contained Django app with:
- `models.py`, `views.py`, `urls.py`, `tests.py`, `serializers.py`
- Optional `migrations/`, `templates/`, `static/`

URLs are registered conditionally in `userportal/urls.py` based on `INSTALLED_APPS`. Adding a new module requires: enabling in settings, registering URLs, and adding to `mkdocs.yml` nav.

## i18n
- French translations in `locale/fr/LC_MESSAGES/`
- Run `python manage.py compilemessages` after updating `.po` files
- Codespell CI skips the French `.po` files and `mii-parser.py`
