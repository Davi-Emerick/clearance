from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
import sqlite3

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent.loop import RunFailed, read_run, run_case
from app.db import connect, db_path, init_db
from app.errors import ClearanceError
from app.providers.base import Model, model_for_request
from app.services import book, cases, clearance


@asynccontextmanager
async def lifespan(_app: FastAPI):
    conn = connect(db_path())
    try:
        init_db(conn)
    finally:
        conn.close()
    yield


app = FastAPI(title="Clearance", lifespan=lifespan)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
DOSSIER_DIR = Path(__file__).resolve().parent.parent / "evals" / "dossiers"


class DocumentIn(BaseModel):
    name: str
    body_text: str


class FactIn(BaseModel):
    name: str
    value: str
    document_id: str = ""
    quote: str = ""


class CloseIn(BaseModel):
    note: str = ""


def get_conn() -> Iterator[sqlite3.Connection]:
    conn = connect(db_path())
    try:
        init_db(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_model() -> Model:
    try:
        return model_for_request()
    except ClearanceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


def _run(action):
    try:
        return action()
    except ClearanceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.get("/", include_in_schema=False)
def desk_page():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/runs/{run_id}")
def get_run(run_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return _run(lambda: read_run(conn, run_id))


@app.post("/cases", status_code=201)
def post_case(conn: sqlite3.Connection = Depends(get_conn)):
    return _run(lambda: cases.create_case(conn))


@app.get("/cases/{case_id}")
def get_case(case_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return _run(lambda: clearance.present(conn, case_id))


@app.post("/cases/{case_id}/facts", status_code=201)
def post_facts(
    case_id: str,
    facts: list[FactIn],
    today: date | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
):
    clock = today or date.today()
    submitted = [item.model_dump() for item in facts]
    return _run(lambda: clearance.record_facts(conn, case_id, submitted, clock))


@app.post("/cases/{case_id}/run")
def post_run(
    case_id: str,
    today: date | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
    model: Model = Depends(get_model),
):
    clock = today or date.today()
    try:
        return _run(lambda: run_case(conn, case_id, model, clock))
    except RunFailed as exc:
        return JSONResponse(status_code=500, content={"run_id": exc.run_id})


@app.post("/cases/{case_id}/evaluate")
def post_evaluate(
    case_id: str,
    today: date | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
):
    clock = today or date.today()
    return _run(lambda: clearance.evaluate(conn, case_id, clock))


@app.post("/cases/{case_id}/bind")
def post_bind(
    case_id: str,
    today: date | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
):
    clock = today or date.today()
    return _run(lambda: book.bind_case(conn, case_id, clock))


@app.post("/cases/{case_id}/close")
def post_close(
    case_id: str,
    body: CloseIn,
    conn: sqlite3.Connection = Depends(get_conn),
):
    return _run(lambda: book.close_case(conn, case_id, body.note))


@app.post("/cases/{case_id}/documents", status_code=201)
def post_document(
    case_id: str,
    body: DocumentIn,
    conn: sqlite3.Connection = Depends(get_conn),
):
    return _run(lambda: cases.add_document(conn, case_id, body.name, body.body_text))


@app.get("/cases/{case_id}/documents/{document_id}")
def get_document(
    case_id: str,
    document_id: str,
    conn: sqlite3.Connection = Depends(get_conn),
):
    return _run(lambda: cases.get_document(conn, case_id, document_id))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/dossiers", StaticFiles(directory=DOSSIER_DIR), name="dossiers")
