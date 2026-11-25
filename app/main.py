from collections.abc import Iterator
from contextlib import asynccontextmanager
import sqlite3

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from app.db import connect, db_path, init_db
from app.errors import ClearanceError
from app.services import cases


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
    return _run(lambda: cases.get_case(conn, case_id))


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
