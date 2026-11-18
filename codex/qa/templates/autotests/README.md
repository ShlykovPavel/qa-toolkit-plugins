# Autotest Framework Template

A **forkable** Python test automation framework for AI-assisted test writing:
- **Backend API tests** (pytest + requests + Allure)
<!-- слой: frontend -->
- **Frontend / Web tests** (Selenium or Playwright — one library per project)
<!-- /слой -->
<!-- слой: mobile -->
- **Mobile tests** (Appium, native UiAutomator2/XCUITest — covers native
  Android/iOS and Flutter apps via `Semantics.identifier`)
<!-- /слой -->

The template is intentionally abstract: the core infrastructure (HTTP client,
DB helpers, driver factories, fixtures) is real and reusable, while everything
named `example_*` is a canonical sample showing how the code should look.
Fork the repo, adapt the examples to your project, and write tests on top —
with AI agents or by hand.

---

## Quick Start

```bash
# 1. Copy environment config
cp .env.example .env
# Fill in your URLs, credentials, and DB connection strings in .env

# 2. Create a venv and install dependencies
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Verify the test collection (works even without .env)
.venv/bin/python -m pytest --collect-only

# 4. Run tests (after adapting examples to your project)
make smoke
make report
```

### Verification without a live stand

The template itself is not wired to any real service. The maximum feedback
loop available here (for humans and AI agents alike):

```bash
make verify
# = python3 -m compileall (syntax) + .venv/bin/python -m pytest --collect-only (imports + fixtures)
```

Note: dependencies live in `.venv` — bare `pytest` is not on PATH.
Runtime pass/fail requires a fork connected to a real stand.

### Forking with Claude Code

The recommended path from fork to first real tests:

1. **Fork the repo** and clone it.
2. **Prepare the environment** — steps 1–3 of the Quick Start above
   (`.env` from the example, venv, `make verify` must be green).
3. **Run `/setup-fork`** in Claude Code — an interview-driven setup that
   generates `src/auth.py` for your auth scheme, adapts `Tests/conftest.py`,
   adds the new keys to `.env.example` and writes the project passport
   `docs/project-profile.md` — the persistent memory all other skills read
   instead of re-asking you.
4. **Fill in the secrets** in `.env` yourself (the agent never asks for
   password values in chat) and let the setup verify a live login.
5. **Start covering**: `/api-tests <resource>` for a single resource,
   `/api-suite` for the whole spec, `/frontend-tests` / `/mobile-tests`
   for UI layers. Every skill refuses to guess: no passport — no tests.

How to talk to the skills, what to prepare for each layer and where your
confirmations are needed: [docs/articles/ai-skills-guide.md](docs/articles/ai-skills-guide.md)
(in Russian, like all docs in `docs/`).

---

## Project Structure

```
.
├── config.py                      # Reads all settings from env vars
├── logger.py                      # Request/response logger
├── pytest.ini                     # Pytest configuration (markers)
├── Makefile                       # verify / smoke / regression / UI layers / report targets
├── .env.example                   # Environment variable template (copy to .env)
│
├── scripts/
│   └── check_no_sleep.py          # make verify gate: no blind sleeps in the test layer (+ test)
│
├── .claude/rules/                 # Path-scoped conventions, loaded per layer
│
├── docs/                          # How-to recipes (linked from CLAUDE.md)
│   ├── api-layer.md               # Add a new API domain (checklist + conventions)
│   ├── tests.md                   # Smoke/regression rules + test matrix
│   ├── fixtures.md                # Fixture map and conftest patterns
│   ├── db.md                      # DB checks in tests (sessions, helpers, async waits)
<!-- слой: frontend -->
│   ├── frontend.md                # Page objects, locator ladder, DOM dumps
<!-- /слой -->
<!-- слой: mobile -->
│   ├── mobile.md                  # Mobile layers, locator ladder, UI dump recipes
<!-- /слой -->
<!-- слой: ui -->
│   ├── locator-conventions.md     # Stable-id contract with app developers (+ AI prompt)
<!-- /слой -->
│   └── articles/                  # Standalone articles for testers (tool reviews etc.)
│
├── src/                           # Shared API clients and helpers
│   ├── http_methods.py            # Central HTTP client (auto-injects tokens, Allure steps)
│   ├── example_auth.py            # EXAMPLE: login + token storage pattern — adapt per project
│   ├── db_config.py               # Lazy engines + session context managers
│   ├── db_functions.py            # DB query helpers (get_value_where, update_record, etc.)
│   ├── data_generators.py         # Unique test data generators (id, email, phone, name)
│   ├── deep_merge_json.py         # Deep-merge dicts (for partial body overrides in tests)
│   ├── custom_decorators.py       # @deprecated / @deprecated_test markers
│   ├── wait_utils.py              # wait_until() polling helper
│   └── example_resource/          # EXAMPLE: COPY THIS for each new domain resource
│       └── example_resource.py    # CRUD pattern: create/get/update/patch/delete
│
├── Tests/
│   ├── conftest.py                # Session fixtures: auth bootstrap (adapt per fork)
│   ├── Smoke_tests/
│   │   └── ExampleFeature/        # EXAMPLE: independent happy-path checks
│   │       ├── conftest.py
│   │       └── test_example_smoke.py
│   ├── Regression_tests/
│   │   ├── example_resource/      # EXAMPLE: full CRUD + negative tests
│   │   │   ├── conftest.py
│   │   │   └── test_example_resource.py
│   │   └── example_flow/          # EXAMPLE: multi-step scenario + DB checks
│   │       ├── conftest.py
│   │       └── test_example_flow.py
<!-- слой: frontend -->
│   ├── Frontend_tests/            # EXAMPLE: one directory per page (+ conftest)
<!-- /слой -->
<!-- слой: mobile -->
│   └── Mobile_tests/
│       ├── conftest.py            # Appium server, driver, emulator fixtures + failure diagnostics
│       └── test_mobile_example.py
<!-- /слой -->
│
<!-- слой: mobile -->
├── Appium/                        # Mobile automation infrastructure
│   ├── driver_func.py             # Appium driver factory (UiAutomator2 / XCUITest)
│   ├── Appium_launcher/           # Appium server start/stop
│   ├── Simulator/                 # Android emulator control + screen recording
│   ├── localization/              # App string localisation (example JSON)
│   ├── app_keys/                  # Mobile locators by stable id
│   │   ├── screen_actions.py      # Base class: find/click/type/scroll helpers
│   │   ├── base_elements_buttons.py     # Shared elements (submit, close modal)
│   │   └── example_feature_buttons.py   # EXAMPLE: COPY for each new screen
│   └── Modules/                   # Feature interaction modules
│       └── example_module.py      # EXAMPLE: COPY for each new feature
<!-- /слой -->
<!-- слой: selenium -->
│
└── frontend/                      # Web / Selenium page objects
    └── front_keys/
        ├── element_finder.py      # Base class: find_element_by_* helpers with waits
        └── example_service/
            └── example_admin_page_keys.py  # EXAMPLE: COPY for each page
<!-- /слой -->
<!-- слой: playwright -->
│
└── frontend/                      # Web / Playwright page objects
    └── pw_keys/
        └── example_service/
            └── example_admin_page_pw.py    # EXAMPLE: COPY for each page
<!-- /слой -->
```

---

## Adding a New Domain Resource

1. **Copy the API client:**
   ```bash
   cp -r src/example_resource src/my_feature
   # Rename the class and URL paths inside
   ```

2. **Add a conftest:**
   ```bash
   mkdir -p Tests/Regression_tests/my_feature
   cp Tests/Regression_tests/example_resource/conftest.py Tests/Regression_tests/my_feature/
   # Adapt fixtures to use MyFeature class
   ```

3. **Copy the test file:**
   ```bash
   cp Tests/Regression_tests/example_resource/test_example_resource.py \
      Tests/Regression_tests/my_feature/test_my_feature.py
   ```

<!-- слой: mobile -->
---

## Adding a New Mobile Screen

1. **Add app_keys:**
   ```bash
   cp Appium/app_keys/example_feature_buttons.py Appium/app_keys/my_screen_buttons.py
   # Map stable identifiers (resource-id / accessibilityIdentifier) to properties
   # (discover real ids via dump_ui_tree.py of the qa-auto plugin — see docs/mobile.md)
   ```

2. **Add a module:**
   ```bash
   cp Appium/Modules/example_module.py Appium/Modules/my_screen.py
   # Implement open_feature() and interactions
   ```

3. **Write tests in `Tests/Mobile_tests/test_my_screen.py`**
<!-- /слой -->

---

## Running Tests

| Command | Description |
|---|---|
| `make smoke` | Run smoke tests |
| `make regression` | Run regression tests |
<!-- слой: mobile -->
| `make mobile` | Run mobile Appium tests |
<!-- /слой -->
<!-- слой: frontend -->
| `make frontend` | Run frontend tests |
<!-- /слой -->
| `make report` | Generate and open Allure report |
| `./run_big_smoke_tests.sh` | CI smoke run with Allure report |
| `./run_tests_docker_compose.sh` | Docker-based regression run |

Parallel run: `pytest -n auto` (pytest-xdist) — tests are designed to be
order-independent; use unique generated data everywhere.

---

## Environment Variables

`.env.example` holds only the stand addresses and DB connections; every variable the
code reads is in `config.py` and in the docs of each UI layer.

Key variables:

| Variable | Description |
|---|---|
| `BASE_URL` | Base URL of the service under test |
| `DB_PRIMARY` | Primary DB SQLAlchemy connection string |
| `DB_SECONDARY` | (optional) Secondary DB connection string |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Test admin credentials |
| `REQUEST_TIMEOUT` | HTTP request timeout in seconds |
<!-- слой: mobile -->
| `PLATFORM` | `android` or `iOS` (mobile tests) |
<!-- /слой -->

---

## Token Management

Auth tokens are stored in `HttpClient.access_folder` (a class-level dict) under
**project-defined names** — there is no fixed role list. The auth fixture logs
in and stores the token; clients then pass `access="<name>"`:

```python
HttpClient.access_folder['admin'] = auth["accessToken"]   # in the auth fixture
HttpClient.get(url, access="admin")                       # in API clients
```

See `src/example_auth.py` for the full pattern, including notes for
cookie-based and api-key-based auth schemes.

---

## CI/CD

The template ships a GitLab CI blueprint — `.gitlab-ci.yml` with four stages:

| Stage | When it runs | What it does |
|---|---|---|
| `verify` | always (green in the template too) | `make verify` — syntax, imports, fixture collection |
| `smoke` | on MR, fork only | calls `./run_big_smoke_tests.sh` — the single source of truth for the smoke run and its single-file Allure report |
| `regression` | on schedule, fork only | `pytest -m regression` with Allure results |
| `report` | after regression | builds the Allure report artifact |

Everything that needs a live stand is gated behind the CI variable
`STAND_AVAILABLE == "true"` — set it in your fork (Settings → CI/CD →
Variables) together with the secrets named in `config.py` (`BASE_URL`,
`DB_PRIMARY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, ...). Values live in CI
variables, never in the repo. The smoke/regression image must provide
Java + Allure CLI (extend the image or `before_script` in the fork).

Nightly smoke run and the failure auto-triage recipe:
[docs/tests.md](docs/tests.md), section «Ночной прогон».
