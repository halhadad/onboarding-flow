import uuid
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import db.models
from web.dependencies import get_onboarding_service, get_application_repository
from services.onboarding_service import OnboardingService
from repositories.application_repo import SQLAlchemyApplicationRepository
from web.forms import IdentityForm, ContactForm, RegulatoryForm, FinancialForm
from domain.flow_registry import flow_registry
from services.resume_service import ResumeService, ResumeApplicationError

router = APIRouter()
templates = Jinja2Templates(directory="templates")

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
    
    service.repository.create_application(
        application_id=application_id,
        country=country,
        account_type=account_type,
        request_id=request_id
    )
    
    flow = flow_registry.get_flow(country, account_type)
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
    
    if not app_record:
        return templates.TemplateResponse(
            request, "resume.html", {"error_message": "Invalid identification reference sequence identifier."}
        )
        
    resumer = ResumeService(repository=repository)
    try:
        country_str = str(app_record.country)
        account_type_str = str(app_record.account_type)
        
        outcome = resumer.resume_session(app_id_clean, country_str, account_type_str)
        url = f"/application/{app_id_clean}/step/{outcome['next_step_id']}?country={country_str}&type={account_type_str}"
        return RedirectResponse(url=url, status_code=303)
    except ResumeApplicationError as err:
        return templates.TemplateResponse(request, "resume.html", {"error_message": str(err)})

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
    flow = flow_registry.get_flow(country, type)
    step_config = flow.get_step_by_id(step_id)
    if not step_config:
        raise HTTPException(status_code=404, detail="The targeted configuration view step does not exist.")
    
    # FIX: Always fetch the structural single source of truth version sequence straight from the database row
    app_record = repository.session.query(db.models.ApplicationRecord).filter(
        db.models.ApplicationRecord.id == application_id
    ).first()
    
    db_version = app_record.version if app_record else 1
        
    return templates.TemplateResponse(
        request,
        "step.html",
        {
            "application_id": application_id,
            "step": step_config,
            "country": country,
            "type": type,
            "version": db_version
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
        if step_id == "collect_identity":
            form_model = await IdentityForm.from_request(form_dict)
            clean_payload = form_model.model_dump()
        elif step_id == "confirm_contact":
            form_model = await ContactForm.from_request(form_dict)
            clean_payload = form_model.model_dump()
        elif step_id == "regulatory_declarations":
            form_model = await RegulatoryForm.from_request(form_dict)
            clean_payload = form_model.model_dump()
        elif step_id == "financial_profile":
            form_model = await FinancialForm.from_request(form_dict)
            clean_payload = form_model.model_dump()
        else:
            raise HTTPException(status_code=400, detail="Mismatched input schema processing specification parameter.")
    except Exception as validation_err:
        flow = flow_registry.get_flow(country, type)
        step_config = flow.get_step_by_id(step_id)
        return templates.TemplateResponse(
            request,
            "step.html",
            {
                "application_id": application_id,
                "step": step_config,
                "country": country,
                "type": type,
                "version": version,
                "error_message": str(validation_err)
            }
        )

    result = service.process_step_submission(
        application_id=application_id,
        country=country,
        account_type=type,
        step_id=step_id,
        form_data=clean_payload,
        current_version=version,
        request_id=request_id
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