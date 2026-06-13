from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session
from db.session import SessionLocal
from repositories.application_repo import SQLAlchemyApplicationRepository
from integrations.identity import MockIdentityVerificationService
from integrations.sanctions import MockSanctionsCheckService
from integrations.credit import MockCreditBureauService
from integrations.registry import MockRegistryService
from integrations.bank_account import MockBankAccountService
from domain.decisioning import AutomatedDecisionEngine
from domain.flow_registry import flow_registry
from services.onboarding_service import OnboardingService


def get_db_session() -> Generator[Session, None, None]:
    """Yield a DB session and close it after."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def get_application_repository(session: Session = Depends(get_db_session)) -> SQLAlchemyApplicationRepository:
    return SQLAlchemyApplicationRepository(session=session)

def get_onboarding_service(
    repository: SQLAlchemyApplicationRepository = Depends(get_application_repository)
) -> OnboardingService:
    # Composition root; wire and inject dependencies here.
    return OnboardingService(
        repository=repository,
        identity_service=MockIdentityVerificationService(),
        sanctions_service=MockSanctionsCheckService(),
        credit_service=MockCreditBureauService(),
        registry_service=MockRegistryService(),
        bank_account_service=MockBankAccountService(),
        decision_engine=AutomatedDecisionEngine(),
        registry=flow_registry,
    )
