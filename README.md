# FrameForge

**AI-assisted PC optimization for gamers and streamers.** A web app plus a Windows
desktop agent that measures your machine, applies documented tweaks with your
consent, and then verifies whether they actually helped.

> The repository is named `ForgeFPS`; the product is **FrameForge** and the desktop
> agent ships as `forgefps-agent.exe`. Same project — the name changed after the
> repository was created.

The distinguishing idea is measurement rather than folklore. Most "PC booster" tools
apply a fixed list of registry edits and declare victory. FrameForge runs an automated
lab: it benchmarks a baseline, toggles one tweak at a time in paired ON/OFF runs,
checks statistical significance, and rolls back anything that does not hold up. Runs
taken in non-comparable conditions — on battery, on a different game, with a frame cap
active — are rejected rather than averaged in. Results are aggregated anonymously
across similar hardware, capped per user so one enthusiast cannot outvote the fleet,
so recommendations improve as the fleet grows.

**▶ [Try the interactive demo](https://wjrko.github.io/ForgeFPS/)** — no install, no account.
Watch the lab measure a baseline, apply four tweaks one at a time, and roll back the one
that fails its significance test. Runs entirely in the browser with sample data.

---

## Features

**Measure**
- Hardware detection via the desktop agent (CPU/GPU/RAM/storage/BIOS, driver versions,
  sensor temperatures through LibreHardwareMonitor)
- Benchmark with DPC time, 4K IOPS at QD1, timer jitter and network quality, plus a
  0–100 health score; each result carries the background load it was measured under
- Live telemetry, thermal alerts, per-game session recaps
- Network quality test with bufferbloat grading

**Optimize**
- **Auto-Pilot** — applies the safe tweaks that are not active yet, measures before and
  after, and always writes a backup first
- **Performance Lab** — tests tweaks one at a time with a paired ON/OFF design: the
  tweak is toggled between runs in an ABBA sequence, so thermal drift and scene
  changes cancel out instead of ending up in the comparison. Decisions come from a
  paired t-test with a confidence interval, and the Holm correction for multiple
  testing is *applied*: a tweak that looked good on its own test but does not survive
  the correction is reverted on the machine before the final validation
- **Regression watchdog** — re-checks 48 hours later and tells you if the boost did not
  hold, so a bad tweak does not sit unnoticed
- **What changed on your PC** — cross-references configuration changes (driver updates,
  new startup programs, RAM speed, Windows builds) with your performance trend

**Advise**
- AI advisor powered by Claude, with your real hardware as context, five coach personas
  and image input
- Structured diagnostics returning prioritized, actionable steps
- Recommendations grounded in the lab's measured evidence rather than guesswork
- Build generator, upgrade analysis and FPS estimation
- Price tracker with automatic checks and drop notifications

**Everything else**
- Multi-PC support, OBS overlays, missions and milestones, Discord bot integration,
  subscription plans with a 14-day trial, bilingual UI (Italian / English)

---

## Architecture

| Layer | Stack |
|---|---|
| Backend | FastAPI 0.110, MongoDB (motor), APScheduler for background jobs |
| Frontend | React 19, Tailwind 3.4 via craco, recharts, framer-motion, i18next |
| AI | Claude via the official `anthropic` SDK (provider-pluggable, see `backend/llm/`) |
| Desktop agent | Python packaged with PyInstaller, driving a PowerShell engine |
| Integrations | Stripe (billing), Resend (email), discord.py (bot), Web Push (VAPID) |

The backend is split into routers under `backend/routers/`; domain logic that is worth
testing in isolation lives in plain modules at `backend/` (`hardware.py`,
`system_changes.py`, `watchdog.py`, `fleet_evidence.py`, `helpers.py`, `lab_stats.py`).

---

## Getting started

### Prerequisites

- Python 3.11
- Node.js 18+ with Yarn
- MongoDB 7+ (local service or container)
- An Anthropic API key for the AI features

### Configuration

Copy `.env.example` to `backend/.env` and fill it in:

```bash
cp .env.example backend/.env
```

The file must live in `backend/`, not in the repository root — `database.py` loads it
relative to its own directory. Only `MONGO_URL`, `DB_NAME`, `JWT_SECRET` and
`ANTHROPIC_API_KEY` are needed to boot; Stripe, Discord, Resend and Web Push stay
inactive until you fill their keys in. Every variable is documented inline.

### Run with Docker

```bash
docker compose up --build
```

Backend on `http://localhost:8001`, frontend on `http://localhost:3000`. MongoDB runs
in its own container and is reachable only from the backend — it is not published to
the host.

### Run natively on Windows

Useful when Docker is unavailable — for instance when hardware virtualization is
disabled in the BIOS and WSL2 cannot start.

```powershell
# once
py -3.11 -m venv backend\.venv
backend\.venv\Scripts\pip install -r backend\requirements-windows.txt
cd frontend; yarn install; cd ..
```

Then, in two terminals:

```powershell
.\start-backend.ps1     # uvicorn with --reload on :8001
.\start-frontend.ps1    # craco dev server on :3000
```

`.\stop-all.ps1` shuts both down. Use `requirements-windows.txt` rather than
`requirements.txt` on Windows: the latter pins a package that is not installable there.

Run a single backend instance, never `--workers`: APScheduler lives inside the process
and has no distributed lock.

---

## Tests

Two suites with different purposes.

**Unit** — no live backend, no database, no network. Seconds, suitable for every commit.

```bash
cd backend
python -m pytest tests_unit -q -p no:cacheprovider -c /dev/null
```

The `-c /dev/null` matters: without it the run inherits `pytest.ini`, which requires
xdist.

**Integration** — around 425 tests against a running backend. Run them serially and
against a throwaway database, never the one you develop with:

```bash
DB_NAME=forgefps_test MONGO_URL=mongodb://localhost:27017 \
  ADMIN_EMAIL=... ADMIN_PASSWORD=... \
  REACT_APP_BACKEND_URL=http://localhost:8003 \
  python -m pytest tests -q -n 0
```

The tests share a single admin account, so parallel workers collide on mission slots,
lab sessions and devices.

---

## Desktop agent

Sources in `agent-build/`. Local build:

```powershell
cd agent-build
.\build.ps1
```

Releases are produced by GitHub Actions on a version tag and signed through SignPath.
See `agent-build/SIGNING_AND_TRUST.md`, and `agent-build/VENDOR_FALSE_POSITIVE.md` for
handling antivirus false positives on PyInstaller executables.

---

## Repository layout

```
backend/            FastAPI application
  routers/          HTTP endpoints, one module per area
  tests/            integration tests (live backend required)
  tests_unit/       fast unit tests (no external dependencies)
  ps_agent.py       PowerShell engine served to the agent
frontend/           React application
agent-build/        desktop agent sources and build scripts
docs/               setup guides
memory/             changelog, roadmap, product notes
```

---

## License

Copyright (C) 2026 WjRKO (FrameForge).

Released under the [GNU Affero General Public License v3.0 or later](LICENSE).

You are free to use, study, modify and redistribute this software. If you run a
modified version as a network service, section 13 of the license requires you to offer
its users the corresponding source code of your modified version.

Releases up to and including tag `v0.8.1` were published under the MIT License and
remain available under those terms.

---

## Code signing policy

Free code signing provided by [SignPath.io](https://signpath.io), certificate by [SignPath Foundation](https://signpath.org).

- **Committers and reviewers:** [Team members](https://github.com/WjRKO/ForgeFPS/graphs/contributors)
- **Approvers:** [WjRKO](https://github.com/WjRKO)

Only members of the project team can commit code and approve signing requests.
Builds run on GitHub-hosted runners from the public source in this repository.

## Privacy policy

FrameForge Desktop Agent (`forgefps-agent.exe`) runs locally on the user's PC.
- It applies documented Windows optimizations **only with explicit user consent**, always creating a backup first, and it **never** modifies Windows Defender, Firewall or security services.
- It may send hardware specs / health metrics / benchmark results to the user's own FrameForge account **only** when the user runs the relevant action, authenticated with the user's private agent token.
- No data is collected or transmitted without the user's action. The program does not contain adware, spyware or telemetry beyond the above.
