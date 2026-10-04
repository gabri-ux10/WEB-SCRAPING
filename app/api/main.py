from fastapi import FastAPI

from app.api.routes.companies import router as companies_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.sources import router as sources_router

app = FastAPI(
    title="TechJobs Aggregator",
    version="0.1.0",
    description="Public tech-job ingestion API. Source attribution links are preserved.",
)
app.include_router(jobs_router)
app.include_router(companies_router)
app.include_router(sources_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
