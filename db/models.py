from datetime import datetime
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, UniqueConstraint, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def generate_uuid() -> str:
    return str(uuid.uuid4())

class ApplicationRecord(Base):
    __tablename__ = "applications"

    id = Column(String, primary_key=True, default=generate_uuid)
    country = Column(String, nullable=False)
    account_type = Column(String, nullable=False)
    status = Column(String, nullable=False, default="STARTED")
    current_step_index = Column(Integer, default=0, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    resume_token = Column(String, unique=True, index=True, nullable=True, default=generate_uuid)
    resume_token_expires_at = Column(DateTime, nullable=True)
    request_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # These relationships now have a clear join condition thanks to the ForeignKeys below
    step_responses = relationship("StepResponseRecord", back_populates="application", cascade="all, delete-orphan")
    integration_logs = relationship("IntegrationLogRecord", back_populates="application", cascade="all, delete-orphan")

class StepResponseRecord(Base):
    __tablename__ = "step_responses"

    id = Column(String, primary_key=True, default=generate_uuid)
    
    # FIX: Explicit ForeignKey constraint
    application_id = Column(String, ForeignKey("applications.id"), index=True, nullable=False)
    
    step_id = Column(String, nullable=False)
    form_data_json = Column(Text, nullable=False)
    payload_hash = Column(String, nullable=False)
    completed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    application = relationship("ApplicationRecord", back_populates="step_responses")

    __table_args__ = (
        UniqueConstraint('application_id', 'step_id', name='_app_step_uc'),
    )

class IntegrationLogRecord(Base):
    __tablename__ = "integration_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    
    # FIX: Explicit ForeignKey constraint
    application_id = Column(String, ForeignKey("applications.id"), index=True, nullable=False)
    
    service_name = Column(String, nullable=False)
    status_outcome = Column(String, nullable=False)
    raw_response_json = Column(Text, nullable=False)
    request_id = Column(String, nullable=False)
    executed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    application = relationship("ApplicationRecord", back_populates="integration_logs")

    __table_args__ = (
        UniqueConstraint('application_id', 'service_name', 'request_id', name='_app_service_request_uc'),
    )