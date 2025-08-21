# Elevator Tracker

Fast, tap-friendly **FastAPI + HTMX** web app to log which **elevator (A–F by default)** was used between floors **(0–22 by default)**—designed for phone and quick one-tap entry.

## Features

* **One-tap logging:** pick *From*/*To* via a **popup keypad**, then tap an elevator button.
* **Recent log:** last 20 entries with “Undo”.
* **Stats:** totals per elevator, **most-used elevators**, and **top routes** with **per-route elevator distribution**.
* **Day filter:** browse any day via `?day=YYYY-MM-DD`.
* **CSV export:** `GET /export.csv?day=YYYY-MM-DD`.
* **SQLite** by default (Docker volume-friendly).
* **Zero build frontend:** Tailwind via CDN, HTMX for snappy no-reload updates.

---

## Tech Stack

* **Backend:** FastAPI, SQLModel (SQLite)
* **Frontend:** HTMX, Tailwind (CDN)
* **Runtime:** Python 3.11+, Uvicorn
* **Container:** uv (Astral) base image; non-root user; healthcheck

---

## Quick Start (Docker)

```bash
# 1) Copy and edit env (optional)
cp .env.example .env

# 2) Start
docker compose up --build

# 3) Open
# http://localhost:1992
```

### `docker-compose.yml` (included)

* Maps `./data` → `/data` for **persistent SQLite** (`/data/elevators.db`).
* Exposes port **1992**.

---

## Quick Start (uv)

Use [uv](https://github.com/astral-sh/uv) to manage the virtualenv and run the app—no manual pip juggling.

### 1) Install uv (one time)

**macOS/Linux**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# then restart your shell or: source ~/.profile
```

**Windows (PowerShell)**

```powershell
iwr https://astral.sh/uv/install.ps1 -UseBasicParsing | iex
```

### 2) Sync deps

In the repo root:

```bash
uv sync          # creates .venv and installs from pyproject / uv.lock
# (optional) if you want to pin a lockfile:
# uv lock
# uv sync --locked
```

### 3) Configure a local DB path (recommended)

For local runs (not Docker), point SQLite to a file in the project directory by setting a environment variable or using a `.env` file:

**macOS/Linux**

```bash
export DATABASE_URL="sqlite:///elevators.db"
```

**Windows (PowerShell)**

```powershell
$env:DATABASE_URL = "sqlite:///elevators.db"
```

> Optional envs you can set similarly:
>
> * `ELEVATORS="A,B,C,D,E,F"`
> * `MIN_FLOOR=0`
> * `MAX_FLOOR=22`

### 4) Run the dev server

```bash
uv run uvicorn main:app --reload --port 1992
```

Open: [http://localhost:1992](http://localhost:1992)

That’s it—uv handles the venv automatically (no manual activation needed).

---

## Configuration

All via environment variables (see `.env.example`):

| Variable       | Default                        | Notes                                   |
| -------------- | ------------------------------ | --------------------------------------- |
| `ELEVATORS`    | `A,B,C,D,E,F`                  | Comma-separated labels                  |
| `MIN_FLOOR`    | `0`                            | Inclusive                               |
| `MAX_FLOOR`    | `22`                           | Inclusive                               |
| `DATABASE_URL` | `sqlite:////data/elevators.db` | Use **absolute** path for Docker volume |

**Examples**

```dotenv
# .env
ELEVATORS=A,B,C,D,E,F
MIN_FLOOR=0
MAX_FLOOR=22
DATABASE_URL=sqlite:////data/elevators.db
```

---

## Endpoints

* `GET /` — main UI (optional `?day=YYYY-MM-DD`)
* `POST /log` — create usage (form: `elevator`, `from_floor`, `to_floor`, `day?`)
* `POST /usage/{id}/delete` — delete one usage (Undo)
* `GET /export.csv` — CSV for a day (`?day=YYYY-MM-DD`)
* `GET /healthz` — healthcheck (HTTP 200)

---

## Data Model

`ElevatorUsage`

* `id` (int, PK)
* `ts` (UTC timestamp)
* `day` (date)
* `elevator` (str)
* `from_floor` (int)
* `to_floor` (int)

---

## Persistence

* Docker maps `./data` → `/data` (bind mount) so your SQLite file survives updates.
* On some hosts you may need to adjust permissions (container uses a non-root user). If you run into write errors:

  * `chown -R 10001:10001 ./data` on the host, **or**
  * set `user: "99:100"` in compose to match host defaults.

---

## Project Structure

```
.
├─ main.py
├─ templates/
│  ├─ base.html
│  ├─ index.html
│  ├─ _recent.html
│  ├─ _stats.html
│  └─ _oob_update.html
├─ static/
├─ pyproject.toml
├─ Dockerfile
├─ docker-compose.yml
└─ .env.example
```

---

## Development Notes

* The *From*/*To* fields use a **custom keypad modal** (mobile-friendly).
* Stats show:

  * **Totals by elevator**
  * **Most used elevators**
  * **Top routes** with **per-route elevator distribution** (counts & %)

---

## Security

* No authentication included by default

---

## License

```
MIT License
```

---

## Contributing

PRs and issues welcome!

1. Fork, branch, and make changes.
2. `docker compose up --build` to test.
3. Open a Pull Request.

---

## Troubleshooting

* **`sqlite3.OperationalError: unable to open database file`**
  Ensure `DATABASE_URL` uses an **absolute** path in Docker (`sqlite:////data/elevators.db`) and the host `./data` dir is writable by the container user.

* **Proxy shows HTTP instead of HTTPS**
  Confirm proxy forwards `X-Forwarded-Proto: https` and Uvicorn runs with `--proxy-headers`.

---

Happy logging! ⬆️🛗

