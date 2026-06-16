import uuid

from fastapi import APIRouter, Request, Depends, HTTPException, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from web.dependencies import get_onboarding_service, get_application_repository
from services.onboarding_service import OnboardingService, StateTransitionError
from services.integration_runner import IntegrationUnavailableError
from repositories.application_repo import ConcurrentModificationError, SQLAlchemyApplicationRepository
from web.forms import FormValidationError, validate_step_payload
from domain.flow_registry import FlowRegistryError, flow_registry
from domain.ports import ApplicationRepository
from domain.states import ApplicationStatus, is_customer_submittable
from services.resume_service import ResumeService, ResumeApplicationError

from config import settings

router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.autoescape = True

RESUME_COOKIE_NAME = settings.RESUME_COOKIE_NAME
RESUME_COOKIE_MAX_AGE_SECONDS = settings.RESUME_TOKEN_TTL_SECONDS


def _progress_context(flow, step_id: str) -> dict:
    step_ids = [step.step_id for step in flow.steps]
    n = step_ids.index(step_id) + 1 if step_id in step_ids else 1
    total = len(step_ids)
    return {
        "current_step_number": n,
        "total_steps": total,
        "progress_percent": int(n / total * 100) if total else 0,
    }


def _assert_step_can_be_rendered(flow, repository: ApplicationRepository, application_id: str, step_id: str) -> None:
    step_ids = [step.step_id for step in flow.steps]
    if step_id not in step_ids:
        raise HTTPException(status_code=404, detail="Step not found.")
    # find the first step that has no saved response yet
    first_incomplete = next(
        (i for i, s in enumerate(flow.steps) if not repository.get_step_response(application_id, s.step_id)),
        len(flow.steps),
    )
    # block jumping ahead of unfinished steps
    if step_ids.index(step_id) > first_incomplete:
        raise HTTPException(status_code=403, detail="Please complete the previous steps first.")


def _get_application_or_abort(
    repository: ApplicationRepository,
    application_id: str,
    country: str,
    account_type: str,
    resume_token: str | None = None,
) -> dict:
    # load the application
    app_context = repository.get_application_context(application_id)
    if not app_context:
        raise HTTPException(status_code=404, detail="Application not found.")

    # check url country/type match what's stored
    stored_country = str(app_context["country"]).upper()
    stored_account_type = str(app_context["account_type"]).lower()
    if stored_country != country.upper() or stored_account_type != account_type.lower():
        raise HTTPException(status_code=403, detail="Wrong country or account type for this application.")

    # check application status allows more submissions
    if not is_customer_submittable(ApplicationStatus(str(app_context["status"]))):
        raise HTTPException(status_code=409, detail="This application is no longer accepting submissions.")

    if not resume_token:
        raise HTTPException(status_code=403, detail="No active session found on this device.")

    # check resume token matches this application and hasn't expired
    token_context = repository.get_application_context_by_resume_token(resume_token)
    if not token_context or str(token_context["id"]) != application_id or token_context.get("resume_token_expired"):
        raise HTTPException(status_code=403, detail="Session expired or not found. Please resume from your original device.")

    return app_context

@router.get("/", response_class=HTMLResponse)
async def index_view(request: Request):
    return templates.TemplateResponse(request, "start.html")

@router.get("/resume", response_class=HTMLResponse)
async def render_resume_hub(
    request: Request,
    repository: SQLAlchemyApplicationRepository = Depends(get_application_repository)
):
    error_message = "No resumable application was found on this device."
    resume_token = request.cookies.get(RESUME_COOKIE_NAME)
    if not resume_token:
        return templates.TemplateResponse(request, "resume.html", {"error_message": error_message})
    try:
        # look up the application by token and find where the customer left off
        outcome = ResumeService(repository=repository).resume_by_token(resume_token)
        url = "/application/{}/step/{}?country={}&type={}".format(
            outcome["application_id"], outcome["next_step_id"],
            outcome["country"], outcome["account_type"],
        )
        return RedirectResponse(url=url, status_code=303)
    except ResumeApplicationError:
        response = templates.TemplateResponse(request, "resume.html", {"error_message": error_message})
        response.delete_cookie(RESUME_COOKIE_NAME)
        return response

@router.post("/application/start", response_class=RedirectResponse)
async def start_application_view(
    request: Request,
    country: str = Form(...),
    account_type: str = Form(...),
    service: OnboardingService = Depends(get_onboarding_service)
):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    try:
        flow = flow_registry.get_flow(country, account_type)
    except FlowRegistryError:
        return templates.TemplateResponse(
            request,
            "start.html",
            {"error_message": "That combination of country and account type is not supported. Please select from the options below."},
            status_code=400,
        )

    # create the application record and get back a resume token to set as a cookie
    application_id, resume_token = service.start_application(country, account_type, request_id)

    first_step_id = flow.steps[0].step_id
    url = f"/application/{application_id}/step/{first_step_id}?country={country}&type={account_type}"
    response = RedirectResponse(url=url, status_code=303)
    response.set_cookie(
        key=RESUME_COOKIE_NAME,
        value=resume_token,
        max_age=RESUME_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return response

@router.get("/application/{application_id}/step/{step_id}", response_class=HTMLResponse)
async def render_step_view(
    request: Request,
    application_id: str,
    step_id: str,
    country: str,
    account_type: str = Query(alias="type"),
    repository: SQLAlchemyApplicationRepository = Depends(get_application_repository)
):
    # validate request
    app_context = _get_application_or_abort(
        repository,
        application_id,
        country,
        account_type,
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
        raise HTTPException(status_code=404, detail="Step not found.")

    db_version = int(app_context["version"])
    _assert_step_can_be_rendered(flow, repository, application_id, step_id)

    # review step shows a summary of every previous step's answers instead of a form
    if step_config.is_review_step:
        summary = []
        for prior_step in flow.steps:
            if prior_step.is_review_step:
                break  # don't summarize the review step itself
            # pull the saved answers for that step and turn them into label/value rows
            response = repository.get_step_response(application_id, prior_step.step_id)
            if response:
                form_data = response["form_data"]
                rows = [
                    {"label": field.display_label, "value": form_data.get(field.field_name)}
                    for field in prior_step.fields
                    if form_data.get(field.field_name) not in (None, "", False)
                ]
                if rows:
                    summary.append({"title": prior_step.title, "rows": rows})

        return templates.TemplateResponse(
            request,
            "review.html",
            {
                "application_id": application_id,
                "step": step_config,
                "country": stored_country,
                "type": stored_account_type,
                "version": db_version,
                "summary": summary,
                **_progress_context(flow, step_id),
            }
        )

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

@router.post("/application/{application_id}/step/{step_id}", response_class=HTMLResponse)
async def submit_step_view(
    request: Request,
    application_id: str,
    step_id: str,
    country: str = Form(...),
    account_type: str = Form(alias="type"),
    version: int = Form(...),
    service: OnboardingService = Depends(get_onboarding_service)
):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    form_data_raw = await request.form()
    form_dict = dict(form_data_raw)

    # validate request
    app_context = _get_application_or_abort(
        service.repository,
        application_id,
        country,
        account_type,
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
        raise HTTPException(status_code=404, detail="Step not found.")

    db_version = int(app_context["version"])
    step_ctx = {
        "application_id": application_id,
        "step": step_config,
        "country": stored_country,
        "type": stored_account_type,
        "version": db_version,
        **_progress_context(flow, step_id),
    }

    # validate the submitted form fields
    try:
        clean_payload = validate_step_payload(step_config, country, form_dict)
    except FormValidationError as err:
        return templates.TemplateResponse(
            request, "step.html",
            {**step_ctx, "error_message": str(err)},
            status_code=400,
        )

    # run integration checks and save the step
    try:
        result = await service.process_step_submission(
            application_id=application_id,
            country=stored_country,
            account_type=stored_account_type,
            step_id=step_id,
            form_data=clean_payload,
            current_version=version,
            request_id=request_id
        )
    except ConcurrentModificationError:
        return templates.TemplateResponse(
            request, "step.html",
            {**step_ctx, "error_message": "State conflict detected. Refresh this step before submitting again."},
            status_code=409,
        )
    except StateTransitionError as err:
        return templates.TemplateResponse(request, "step.html", {**step_ctx, "error_message": str(err)}, status_code=409)
    except IntegrationUnavailableError:
        return templates.TemplateResponse(
            request, "step.html",
            {**step_ctx, "error_message": "A verification service is temporarily unavailable. Please submit again in a moment."},
            status_code=503,
        )

    status_outcome = result["status"]
    next_step_id = result["next_step_id"]

    if not next_step_id:
        response = templates.TemplateResponse(
            request,
            "decision.html",
            {"status": status_outcome, "reference": application_id[:8].upper()},
        )
        response.delete_cookie(RESUME_COOKIE_NAME)
        return response

    url = f"/application/{application_id}/step/{next_step_id}?country={stored_country}&type={stored_account_type}"
    return RedirectResponse(url=url, status_code=303)
