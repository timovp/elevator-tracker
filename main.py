import os
from datetime import datetime, date
from typing import Optional, List, Tuple, Dict

from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, StreamingResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import SQLModel, Field, create_engine, Session, select
from dotenv import load_dotenv

load_dotenv()
# ---------- Config ----------
ELEVATORS = [
    e.strip().upper()
    for e in os.getenv("ELEVATORS", "A,B,C,D,E,F").split(",")
    if e.strip()
]
MIN_FLOOR = int(os.getenv("MIN_FLOOR", "0"))  # <-- now default 0
MAX_FLOOR = int(os.getenv("MAX_FLOOR", "22"))
DATABASE_URL = os.getenv(
    "DATABASE_URL", "sqlite:////data/elevators.db"
)  # or "sqlite:///elevators.db" for local


# ---------- Models ----------
class ElevatorUsage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=datetime.utcnow, index=True)
    day: date = Field(default_factory=lambda: date.today(), index=True)
    elevator: str = Field(index=True)
    from_floor: int = Field(index=True)
    to_floor: int = Field(index=True)


# ---------- App / DB ----------
app = FastAPI(title="Elevator Tracker")
templates = Jinja2Templates(directory="templates")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as s:
        yield s


@app.on_event("startup")
def on_startup():
    init_db()


# ---------- Helpers ----------
def floors() -> List[int]:
    return list(range(MIN_FLOOR, MAX_FLOOR + 1))


def validate(elevator: str, frm: int, to: int):
    if elevator not in ELEVATORS:
        raise HTTPException(status_code=400, detail="Unknown elevator")
    if not (MIN_FLOOR <= frm <= MAX_FLOOR and MIN_FLOOR <= to <= MAX_FLOOR):
        raise HTTPException(
            status_code=400, detail=f"Floor out of range ({MIN_FLOOR}–{MAX_FLOOR})"
        )
    if frm == to:
        raise HTTPException(status_code=400, detail="From/To cannot be the same")


def compute_stats(rows: List[ElevatorUsage]) -> Dict:
    # Totals by elevator
    totals: Dict[str, int] = {e: 0 for e in ELEVATORS}
    # Totals by route
    route_totals: Dict[Tuple[int, int], int] = {}
    # Per-route elevator counts
    route_elev: Dict[Tuple[int, int], Dict[str, int]] = {}

    for r in rows:
        # overall totals
        totals[r.elevator] = totals.get(r.elevator, 0) + 1
        key = (r.from_floor, r.to_floor)

        # route totals
        route_totals[key] = route_totals.get(key, 0) + 1

        # route→elevator distribution
        if key not in route_elev:
            route_elev[key] = {}
        route_elev[key][r.elevator] = route_elev[key].get(r.elevator, 0) + 1

    # Top routes (limit 8)
    top_routes = sorted(route_totals.items(), key=lambda kv: kv[1], reverse=True)[:8]

    top_routes_fmt = []
    for (a, b), cnt in top_routes:
        elev_counts = route_elev.get((a, b), {})
        # sort elevator distribution desc
        ordered = sorted(elev_counts.items(), key=lambda kv: kv[1], reverse=True)
        # shape: [{"elevator":"A","count":5,"pct":62.5}, ...]
        dist = [
            {"elevator": e, "count": c, "pct": (c * 100.0 / cnt) if cnt else 0.0}
            for e, c in ordered
        ]
        top_routes_fmt.append(
            {
                "route": f"{a}→{b}",
                "from": a,
                "to": b,
                "count": cnt,
                "elevators": dist,
            }
        )

    # Top elevators (ranked list)
    top_elevators = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    top_elevators_fmt = [
        {"elevator": e, "count": c} for e, c in top_elevators[: max(6, len(ELEVATORS))]
    ]

    return {
        "totals": totals,  # dict: { "A": 12, ... }
        "top_routes": top_routes_fmt,  # list of {route,count,elevators:[{elevator,count,pct}]}
        "top_elevators": top_elevators_fmt,  # list of {elevator,count}
    }


# ---------- Routes ----------
@app.get("/", response_class=HTMLResponse)
def home(
    request: Request, session: Session = Depends(get_session), day: Optional[str] = None
):
    target_day = date.fromisoformat(day) if day else date.today()
    stmt = (
        select(ElevatorUsage)
        .where(ElevatorUsage.day == target_day)
        .order_by(ElevatorUsage.ts.desc())
    )
    recent = session.exec(stmt).all()
    stats = compute_stats(recent)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "elevators": ELEVATORS,
            "floors": floors(),
            "min_floor": MIN_FLOOR,  # <-- pass to template
            "max_floor": MAX_FLOOR,  # <-- pass to template
            "target_day": target_day,
            "recent": recent[:20],
            "stats": stats,
            "error": None,
        },
    )


@app.post("/log", response_class=HTMLResponse)
def log_usage(
    request: Request,
    elevator: str = Form(...),
    from_floor: int = Form(...),
    to_floor: int = Form(...),
    day: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    target_day = date.fromisoformat(day) if day else date.today()
    elevator = elevator.strip().upper()
    validate(elevator, from_floor, to_floor)

    usage = ElevatorUsage(
        elevator=elevator, from_floor=from_floor, to_floor=to_floor, day=target_day
    )
    session.add(usage)
    session.commit()
    session.refresh(usage)

    rows = session.exec(
        select(ElevatorUsage)
        .where(ElevatorUsage.day == target_day)
        .order_by(ElevatorUsage.ts.desc())
    ).all()
    stats = compute_stats(rows)

    return templates.TemplateResponse(
        "_oob_update.html",
        {
            "request": request,
            "target_day": target_day,
            "recent": rows[:20],
            "stats": stats,
            "error": None,
        },
    )


@app.post("/usage/{usage_id}/delete", response_class=HTMLResponse)
def delete_usage(
    request: Request,
    usage_id: int,
    day: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    target_day = date.fromisoformat(day) if day else date.today()
    row = session.get(ElevatorUsage, usage_id)
    if row:
        session.delete(row)
        session.commit()

    rows = session.exec(
        select(ElevatorUsage)
        .where(ElevatorUsage.day == target_day)
        .order_by(ElevatorUsage.ts.desc())
    ).all()
    stats = compute_stats(rows)
    return templates.TemplateResponse(
        "_oob_update.html",
        {
            "request": request,
            "target_day": target_day,
            "recent": rows[:20],
            "stats": stats,
            "error": None,
        },
    )


@app.get("/export.csv")
def export_csv(day: Optional[str] = None, session: Session = Depends(get_session)):
    target_day = date.fromisoformat(day) if day else date.today()
    rows = session.exec(
        select(ElevatorUsage)
        .where(ElevatorUsage.day == target_day)
        .order_by(ElevatorUsage.ts.asc())
    ).all()

    def gen():
        yield "Timestamp,Day,Elevator,From,To\n"
        for r in rows:
            yield f"{r.ts.isoformat()},{r.day.isoformat()},{r.elevator},{r.from_floor},{r.to_floor}\n"

    return StreamingResponse(
        gen(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="elevators_{target_day.isoformat()}.csv"'
        },
    )


@app.get("/healthz")
def healthz():
    return PlainTextResponse("ok")


app.mount("/static", StaticFiles(directory="static"), name="static")
