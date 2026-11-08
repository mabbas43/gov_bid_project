"""SQLite tables."""
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CompanyProfile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    city: str
    team_size: int
    annual_turnover_pkr: int
    years_in_business: int
    capabilities: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    registrations: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    past_projects: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=utcnow)


class Tender(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    external_id: str = Field(index=True, unique=True)
    title: str
    agency: str = ""
    source: str = "seed"  # seed | ppra
    published_date: Optional[date] = None
    closing_date: Optional[date] = None
    document_url: Optional[str] = None
    text_path: Optional[str] = None
    # new | analyzed | needs_ocr | no_document | error
    status: str = "new"
    status_detail: Optional[str] = None
    scope_summary: Optional[str] = None
    estimated_value_pkr: Optional[int] = None
    bid_security: Optional[str] = None
    requirements: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    fit_score: Optional[int] = Field(default=None, index=True)
    fit_label: Optional[str] = None  # strong | partial | non_fit
    fit_reason: Optional[str] = None
    score_breakdown: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    analyzed_at: Optional[datetime] = None


class EligibilityCheck(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tender_id: int = Field(foreign_key="tender.id", index=True)
    requirement: str
    type: str
    threshold: Optional[str] = None
    mandatory: bool = True
    status: str  # pass | fail | unclear
    reason: str = ""
    source_quote: str = ""
    method: str = "rule"  # rule | llm


class BidPack(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tender_id: int = Field(foreign_key="tender.id", index=True)
    status: str = "pending"  # pending | ready | failed
    zip_path: Optional[str] = None
    files: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    generation_ms: Optional[int] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class AgentRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    goal: str
    status: str = "queued"  # queued | running | completed | failed
    demo_mode: bool = False
    workspace: Optional[str] = None
    final_answer: Optional[str] = None
    error: Optional[str] = None
    best_tender_id: Optional[int] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: Optional[datetime] = None


class AgentStep(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: Optional[int] = Field(default=None, foreign_key="agentrun.id", index=True)
    step: int = 0
    scope: str = "orchestrator"  # orchestrator | analyst | bidpack
    tool: str = ""
    tender_id: Optional[int] = None
    status: str = "running"  # running | done | error
    thought_summary: str = ""
    input_summary: str = ""
    output_summary: str = ""
    duration_ms: int = 0
    tokens: int = 0
    created_at: datetime = Field(default_factory=utcnow)


class AppSetting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
