import uuid
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import db.models
from web.dependencies import get_onboarding_service, get_application_repository
from services.onboarding_service import OnboardingService, StateTransitionError
from repositories.application_repo import SQLAlchemyApplicationRepository
from web.forms import FormValidationError, validate_step_payload
from domain.flow_registry import FlowRegistryError, flow_registry
from services.resume_service import ResumeService, ResumeApplicationError

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _progress_context(flow, step_id: str) -> dict:
    step_ids = [step.step_id for step in flow.steps]
    current_index = step_ids.index(step_id) if step_id in step_ids else 0
    total_steps = len(step_ids)
    current_step_number = current_index + 1
    return {
        "current_step_number": current_step_number,
        "total_steps": total_steps,
        "progress_percent": int((current_step_number / total_steps) * 100) if total_steps else 0,
    }


def _assert_step_can_be_rendered(flow, repository: SQLAlchemyApplicationRepository, application_id: str, step_id: str) -> None:
    step_ids = [step.step_id for step in flow.steps]
    requested_index = step_ids.index(step_id)
    first_incomplete_index = len(step_ids)

    for index, step in enumerate(flow.steps):
        if not repository.get_step_response(application_id, step.step_id):
            first_incomplete_index = index
            break

    if requested_index > first_incomplete_index:
        raise HTTPException(status_code=403, detail="Complete the previous onboarding steps before opening this step.")

@router.get("/", response_class=HTMLResponse)
async def index_view(request: Request):
    return templates.TemplateResponse(request, "start.html")

@router.get("/resume", response_class=HTMLResponse)
async def render_resume_hub(request: Request):
    return templates.TemplateResponse(request, "resume.html")

@router.post("/application/start", response_class=RedirectResponse)
async def start_application_view(
    request: Request,
    country: str = Form(...),
    account_type: str = Form(...),
    service: OnboardingService = Depends(get_onboarding_service)
):
    application_id = str(uuid.uuid4())
    # Correctly retrieve from middleware state
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    
    try:
        flow = flow_registry.get_flow(country, account_type)
    except FlowRegistryError:
        return templates.TemplateResponse(
            request,
            "start.html",
            {"error_message": "Unsupported onboarding flow. Choose one of the listed country and account type combinations."},
            status_code=400,
        )

    service.repository.create_application(
        application_id=application_id,
        country=country,
        account_type=account_type,
        request_id=request_id
    )

    first_step_id = flow.steps[0].step_id
    
    url = f"/application/{application_id}/step/{first_step_id}?country={country}&type={account_type}"
    return RedirectResponse(url=url, status_code=303)

@router.post("/application/resume", response_class=RedirectResponse)
async def handle_resume_submission(
    request: Request,
    application_id: str = Form(...),
    repository: SQLAlchemyApplicationRepository = Depends(get_application_repository)
):
    app_id_clean = application_id.strip()
    app_record = repository.session.query(db.models.ApplicationRecord).filter(
        db.models.ApplicationRecord.id == app_id_clean
    ).first()
    
    generic_resume_error = "We could not resume that application. Check the resume reference or contact support."

    if not app_record:
        return templates.TemplateResponse(
            request, "resume.html", {"error_message": generic_resume_error}
        )
        
    resumer = ResumeService(repository=repository)
    try:
        country_str = str(app_record.country)
        account_type_str = str(app_record.account_type)
        
        outcome = resumer.resume_session(app_id_clean, country_str, account_type_str)
        url = f"/application/{app_id_clean}/step/{outcome['next_step_id']}?country={country_str}&type={account_type_str}"
        return RedirectResponse(url=url, status_code=303)
    except ResumeApplicationError as err:
        return templates.TemplateResponse(request, "resume.html", {"error_message": generic_resume_error})

@router.get("/application/{application_id}/step/{step_id}", response_class=HTMLResponse)
async def render_step_view(
    request: Request,
    application_id: str,
    step_id: str,
    country: str,
    type: str,
    repository: SQLAlchemyApplicationRepository = Depends(get_application_repository)
):
    """Renders forms dynamically using state context configurations fetched from the database layer."""
    try:
        flow = flow_registry.get_flow(country, type)
    except FlowRegistryError as err:
        raise HTTPException(status_code=400, detail="Unsupported onboarding flow.") from err
    step_config = flow.get_step_by_id(step_id)
    if not step_config:
        raise HTTPException(status_code=404, detail="The targeted configuration view step does not exist.")
    
    # FIX: Always fetch the structural single source of truth version sequence straight from the database row
    app_record = repository.session.query(db.models.ApplicationRecord).filter(
        db.models.ApplicationRecord.id == application_id
    ).first()
    
    if not app_record:
        raise HTTPException(status_code=404, detail="Application not found.")
    db_version = app_record.version
    _assert_step_can_be_rendered(flow, repository, application_id, step_id)
        
    return templates.TemplateResponse(
        request,
        "step.html",
        {
            "application_id": application_id,
            "step": step_config,
            "country": country,
            "type": type,
            "version": db_version,
            **_progress_context(flow, step_id),
        }
    )

@router.post("/application/{application_id}/step/{step_id}", response_class=HTMLResponse)
async def submit_step_view(
    request: Request,
    application_id: str,
    step_id: str,
    country: str = Form(...),
    type: str = Form(...),
    version: int = Form(...),
    service: OnboardingService = Depends(get_onboarding_service)
):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    form_data_raw = await request.form()
    form_dict = {k: v for k, v in form_data_raw.items()}
    
    try:
        flow = flow_registry.get_flow(country, type)
    except FlowRegistryError as err:
        raise HTTPException(status_code=400, detail="Unsupported onboarding flow.") from err

    step_config = flow.get_step_by_id(step_id)
    if not step_config:
        raise HTTPException(status_code=404, detail="The targeted configuration view step does not exist.")

    try:
        clean_payload = validate_step_payload(step_config, country, form_dict)
    except FormValidationError as validation_err:
        return templates.TemplateResponse(
            request,
            "step.html",
            {
                "application_id": application_id,
                "step": step_config,
                "country": country,
                "type": type,
                "version": version,
                "error_message": str(validation_err),
                **_progress_context(flow, step_id),
            }
        )

    try:
        result = service.process_step_submission(
            application_id=application_id,
            country=country,
            account_type=type,
            step_id=step_id,
            form_data=clean_payload,
            current_version=version,
            request_id=request_id
        )
    except StateTransitionError as err:
        return templates.TemplateResponse(
            request,
            "step.html",
            {
                "application_id": application_id,
                "step": step_config,
                "country": country,
                "type": type,
                "version": version,
                "error_message": str(err),
                **_progress_context(flow, step_id),
            },
            status_code=409,
        )
    
    status_outcome = result["status"]
    next_step_id = result["next_step_id"]

    if status_outcome in ["APPROVED", "REJECTED", "MANUAL_REVIEW"] and not next_step_id:
        return templates.TemplateResponse(
            request,
            "decision.html",
            {"status": status_outcome}
        )
        
    url = f"/application/{application_id}/step/{next_step_id}?country={country}&type={type}"
    return RedirectResponse(url=url, status_code=303)
