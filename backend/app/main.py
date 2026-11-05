from fastapi import FastAPI

app = FastAPI(
    title="Within24 API",
    description="Track work hours across jobs against Canada's study permit work limits.",
    version="0.1.0",
)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
