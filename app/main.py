from fastapi import FastAPI

app = FastAPI(title="Clearance")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
