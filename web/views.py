import uuid

from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from web.dependencies import get_onboarding_service, get_application_repository
from services.onboarding_service import OnboardingService, StateTransitionError
from services.integration_runner import IntegrationUnavailableError
from repositories.application_repo import ConcurrentModificationError, SQLAlchemyApplicationRepository
from web.forms import FormValidationError, validate_step_payload
from domain.flow_registry import FlowRegistryError, flow_registry
from domain.states import ApplicationStatus, TERMINAL_APPLICATION_STATUSES, is_customer_submittable
from services.resume_service import ResumeService, ResumeApplicationError

router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.autoescape = True
RESUME_COOKIE_NAME = "bank_onboarding_resume"
RESUME_COOKIE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60


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


def _load_routable_application_context(
    repository: SQLAlchemyApplicationRepository,
    application_id: str,
    country: str,
    account_type: str,
    resume_token: str | None = None,
) -> dict:
    app_context = repository.get_application_context(application_id)
    if not app_context:
        raise HTTPException(status_code=404, detail="Application not found.")

    stored_country = str(app_context["country"]).upper()
    stored_account_type = str(app_context["account_type"]).lower()
    if stored_country != country.upper() or stored_account_type != account_type.lower():
        raise HTTPException(status_code=403, detail="Application route does not match the stored onboarding journey.")

    # Single shared gate with the service layer: only STARTED / IN_PROGRESS
    # applications accept customer routing (MANUAL_REVIEW is parked with a reviewer).
    if not is_customer_submittable(ApplicationStatus(str(app_context["status"]))):
        raise HTTPException(status_code=409, detail="This application is no longer open for customer input.")

    if not resume_token:
        raise HTTPException(status_code=403, detail="This application session is not available on this device.")

    token_context = repository.get_application_context_by_resume_token(resume_token)
    if not token_context or str(token_context["id"]) != application_id or token_context.get("resume_token_expired"):
        raise HTTPException(status_code=403, detail="This application session is not available on this device.")

    return app_context

@router.get("/", response_class=HTMLResponse)
async def index_view(request: Request):
    return templates.TemplateResponse(request, "start.html")

@router.get("/resume", response_class=HTMLResponse)
async def render_resume_hub(
    request: Request,
    repository: SQLAlchemyApplicationRepository = Depends(get_application_repository)
):
    generic_resume_error = "No resumable application was found on this device."
    resume_token = request.cookies.get(RESUME_COOKIE_NAME)
    if not resume_token:
        return templates.TemplateResponse(request, "resume.html", {"error_message": generic_resume_error})

    resumer = ResumeService(repository=repository)
    try:
        outcome = resumer.resume_by_token(resume_token)
        app_id = str(outcome["application_id"])
        country_str = str(outcome["country"])
        account_type_str = str(outcome["account_type"])
        url = f"/application/{app_id}/step/{outcome['next_step_id']}?country={country_str}&type={account_type_str}"
        return RedirectResponse(url=url, status_code=303)
    except ResumeApplicationError:
        response = templates.TemplateResponse(request, "resume.html", {"error_message": generic_resume_error})
        response.delete_cookie(RESUME_COOKIE_NAME)
        return response

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
    
    app_context = service.repository.get_application_context(application_id)
    url = f"/application/{application_id}/step/{first_step_id}?country={country}&type={account_type}"
    response = RedirectResponse(url=url, status_code=303)
    if app_context and app_context.get("resume_token"):
        response.set_cookie(
            key=RESUME_COOKIE_NAME,
            value=str(app_context["resume_token"]),
            max_age=RESUME_COOKIE_MAX_AGE_SECONDS,
            httponly=True,
            samesite="lax",
        )
    return response

@router.post("/application/resume", response_class=RedirectResponse)
async def handle_resume_submission(
    request: Request,
    repository: SQLAlchemyApplicationRepository = Depends(get_application_repository)
):
    generic_resume_error = "No resumable application was found on this device."
    resume_token = request.cookies.get(RESUME_COOKIE_NAME)
    if not resume_token:
        return templates.TemplateResponse(request, "resume.html", {"error_message": generic_resume_error})

    resumer = ResumeService(repository=repository)
    try:
        outcome = resumer.resume_by_token(resume_token)
        app_id = str(outcome["application_id"])
        country_str = str(outcome["country"])
        account_type_str = str(outcome["account_type"])
        url = f"/application/{app_id}/step/{outcome['next_step_id']}?country={country_str}&type={account_type_str}"
        return RedirectResponse(url=url, status_code=303)
    except ResumeApplicationError:
        response = templates.TemplateResponse(request, "resume.html", {"error_message": generic_resume_error})
        response.delete_cookie(RESUME_COOKIE_NAME)
        return response

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
    app_context = _load_routable_application_context(
        repository,
        application_id,
        country,
        type,
        request.cookies.get(RESUME_COOKIE_NAME),
    )
    stored_country = str(app_context["country"])
    stored_account_type = str(app_context["account_type"])

    try:
        flow = flow_registry.get_flow(stored_country, stored_account_type)
    except FlowRegistryError as err:
        raise HTTPException(status_code=400, detail="Unsupported onboarding flow.") from err
    step_config = flow.get_step_by_id(step_id)
    if not step_config:
        raise HTTPException(status_code=404, detail="The targeted configuration view step does not exist.")

    db_version = int(app_context["version"])
    _assert_step_can_be_rendered(flow, repository, application_id, step_id)
        
    return templates.TemplateResponse(
        request,
        "step.html",
        {
            "application_id": application_id,
            "step": step_config,
            "country": stored_country,
            "type": stored_account_type,
            "version": db_version,
            **_progress_context(flow, step_id),
        }
    )

@router.get("/application/{application_id}/review", response_class=HTMLResponse)
async def review_view(
    request: Request,
    application_id: str,
    country: str,
    type: str,
    repository: SQLAlchemyApplicationRepository = Depends(get_application_repository),
):
    """Read-only summary of everything captured so far (already redacted), plus
    which steps remain. Values are rendered through Jinja's native autoescaping
    as plain field/value pairs — never as a raw serialized blob."""
    app_context = _load_routable_application_context(
        repository,
        application_id,
        country,
        type,
        request.cookies.get(RESUME_COOKIE_NAME),
    )
    stored_country = str(app_context["country"])
    stored_account_type = str(app_context["account_type"])

    try:
        flow = flow_registry.get_flow(stored_country, stored_account_type)
    except FlowRegistryError as err:
        raise HTTPException(status_code=400, detail="Unsupported onboarding flow.") from err

    saved_responses = repository.get_all_step_responses(application_id)
    review_steps = []
    for step in flow.steps:
        response = saved_responses.get(step.step_id)
        review_steps.append({
            "title": step.title,
            "step_id": step.step_id,
            "completed": response is not None,
            "fields": [
                {"label": key.replace("_", " "), "value": value}
                for key, value in (response or {}).items()
            ],
        })

    return templates.TemplateResponse(
        request,
        "review.html",
        {
            "application_id": application_id,
            "country": stored_country,
            "type": stored_account_type,
            "review_steps": review_steps,
        },
    )


@router.post("/application/{application_id}/step/{step_id}", response_class=HTMLResponse)
async def submit_step_view(
    request: Request,
    application_id: str,
    step_id: str,
    country: str = Form(...),
    type: str = Form(...),
    service: OnboardingService = Depends(get_onboarding_service)
):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    form_data_raw = await request.form()
    form_dict = {k: v for k, v in form_data_raw.items()}
    
    app_context = _load_routable_application_context(
        service.repository,
        application_id,
        country,
        type,
        request.cookies.get(RESUME_COOKIE_NAME),
    )
    stored_country = str(app_context["country"])
    stored_account_type = str(app_context["account_type"])

    try:
        flow = flow_registry.get_flow(stored_country, stored_account_type)
    except FlowRegistryError as err:
        raise HTTPException(status_code=400, detail="Unsupported onboarding flow.") from err

    step_config = flow.get_step_by_id(step_id)
    if not step_config:
        raise HTTPException(status_code=404, detail="The targeted configuration view step does not exist.")

    current_version = int(app_context["version"])

    try:
        clean_payload = validate_step_payload(step_config, country, form_dict)
    except FormValidationError as validation_err:
        return templates.TemplateResponse(
            request,
            "step.html",
            {
                "application_id": application_id,
                "step": step_config,
                "country": stored_country,
                "type": stored_account_type,
                "version": current_version,
                "error_message": str(validation_err),
                **_progress_context(flow, step_id),
            }
        )

    try:
        result = service.process_step_submission(
            application_id=application_id,
            country=stored_country,
            account_type=stored_account_type,
            step_id=step_id,
            form_data=clean_payload,
            current_version=current_version,
            request_id=request_id
        )
    except ConcurrentModificationError:
        return templates.TemplateResponse(
            request,
            "step.html",
            {
                "application_id": application_id,
                "step": step_config,
                "country": stored_country,
                "type": stored_account_type,
                "version": current_version,
                "error_message": "State conflict detected. Refresh this step before submitting again.",
                **_progress_context(flow, step_id),
            },
            status_code=409,
        )
    except StateTransitionError as err:
        return templates.TemplateResponse(
            request,
            "step.html",
            {
                "application_id": application_id,
                "step": step_config,
                "country": stored_country,
                "type": stored_account_type,
                "version": current_version,
                "error_message": str(err),
                **_progress_context(flow, step_id),
            },
            status_code=409,
        )
    except IntegrationUnavailableError:
        # Transient provider outage: the step was NOT saved, so the customer can
        # simply resubmit. We do not park them in manual review. In production
        # this is where automatic retry/backoff and a circuit breaker would sit.
        return templates.TemplateResponse(
            request,
            "step.html",
            {
                "application_id": application_id,
                "step": step_config,
                "country": stored_country,
                "type": stored_account_type,
                "version": current_version,
                "error_message": "A verification service is temporarily unavailable. Please submit again in a moment.",
                **_progress_context(flow, step_id),
            },
            status_code=503,
        )

    status_outcome = result["status"]
    next_step_id = result["next_step_id"]

    if status_outcome in {status.value for status in TERMINAL_APPLICATION_STATUSES} and not next_step_id:
        response = templates.TemplateResponse(
            request,
            "decision.html",
            {"status": status_outcome}
        )
        response.delete_cookie(RESUME_COOKIE_NAME)
        return response
        
    url = f"/application/{application_id}/step/{next_step_id}?country={stored_country}&type={stored_account_type}"
    return RedirectResponse(url=url, status_code=303)
