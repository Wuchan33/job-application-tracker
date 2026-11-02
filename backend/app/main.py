from fastapi import FastAPI

from app.routers import applications, stats, sync

app = FastAPI(title="Job application tracker")
app.include_router(sync.router)
app.include_router(applications.router)
app.include_router(stats.router)


@app.get("/api/health")
def get_health() -> dict[str, str]:
    return {"status": "ok"}
