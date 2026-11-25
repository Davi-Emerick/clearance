from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import date
import sqlite3

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.agent.loop import RunFailed, run_case
from app.db import connect, db_path, init_db
from app.errors import ClearanceError
from app.providers.base import Model, open_model
from app.services import cases, clearance


@asynccontextmanager
async def lifespan(_app: FastAPI):
    conn = connect(db_path())
    try:
        init_db(conn)
    finally:
        conn.close()
    yield


app = FastAPI(title="Clearance", lifespan=lifespan)


class DocumentIn(BaseModel):
    name: str
    body_text: str


class FactIn(BaseModel):
    name: str
    value: str
    document_id: str = ""
    quote: str = ""


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
    return open_model("live")


def _run(action):
    try:
        return action()
    except ClearanceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
