import db.models
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from db.session import engine 
from audit.log import configure_logging
from repositories.application_repo import ConcurrentModificationError
from web.middleware import BankingSecurityAuditMiddleware
from web.views import router as web_router

templates = Jinja2Templates(directory="templates")
templates.env.autoescape = True
configure_logging()
logger = logging.getLogger("onboarding.app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles the transactional ledger generation and engages Write-Ahead Logging."""
    db.models.Base.metadata.create_all(bind=engine)
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL;")
        connection.exec_driver_sql("PRAGMA synchronous=NORMAL;")
    logger.info("database_ready", extra={"component": "database", "outcome": "wal_enabled"})
    yield
    logger.info("database_disposed", extra={"component": "database", "outcome": "shutdown"})
    engine.dispose()

app = FastAPI(
    title="Bank Onboarding Application",
    lifespan=lifespan
)

app.add_middleware(BankingSecurityAuditMiddleware)

@app.exception_handler(ConcurrentModificationError)
async def concurrent_modification_exception_handler(request: Request, exc: ConcurrentModificationError):
    """Gracefully intercepts double-submission collisions at the UI boundary."""
    return templates.TemplateResponse(
        request,
        "step.html",
        {
            "error_message": "State conflict detected. It appears you have updated this session in another window.",
            "application_id": request.path_params.get("application_id", ""),
            "country": request.query_params.get("country", "SWEDEN"),
            "type": request.query_params.get("type", "private"),
            "version": int(request.query_params.get("version", 1)),
            "step": None
        },
        status_code=409
    )

app.include_router(web_router)

@app.get("/health")
def health_check():
    return {"status": "healthy"}
