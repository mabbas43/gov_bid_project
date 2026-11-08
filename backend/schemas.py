"""API and LLM contracts."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

ReqType = Literal["turnover", "experience", "registration", "location", "technical", "document"]
CheckStatus = Literal["pass", "fail", "unclear"]


class Registrations(BaseModel):
    ntn: Optional[str] = None
    atl_status: Optional[str] = None  # "active" | "inactive"
    pec_category: Optional[str] = None
    secp: Optional[str] = None
    pseb: Optional[str] = None


class PastProject(BaseModel):
    title: str
    client: str
    value_pkr: int = Field(ge=0)
    year: int


class ProfileIn(BaseModel):
    name: str = Field(min_length=1)
    city: str = Field(min_length=1)
    team_size: int = Field(ge=1)
    annual_turnover_pkr: int = Field(ge=0)
    years_in_business: int = Field(ge=0)
    capabilities: list[str] = []
    registrations: Registrations = Registrations()
    past_projects: list[PastProject] = []


class Requirement(BaseModel):
    requirement: str
    type: ReqType
    threshold: Optional[str] = None
    mandatory: bool = True
    source_quote: str = ""


class Extraction(BaseModel):
    scope_summary: str
    estimated_value_pkr: Optional[int] = None
    closing_date: Optional[str] = None
    bid_security: Optional[str] = None
    eligibility: list[Requirement] = []


class ChunkSummary(BaseModel):
    summary: str


class FuzzyItem(BaseModel):
    index: int
    status: CheckStatus
    reason: str


class FuzzyBatch(BaseModel):
    verdicts: list[FuzzyItem]


class CheckResult(BaseModel):
    requirement: str
    type: ReqType
    threshold: Optional[str] = None
    mandatory: bool = True
    status: CheckStatus
    reason: str
    source_quote: str = ""
    method: Literal["rule", "llm"] = "rule"


class ScoreResult(BaseModel):
    score: int
    label: Literal["strong", "partial", "non_fit"]
    reason: str
    capped: bool = False
    capability: float = 0.0
    eligibility: float = 0.0
    value_fit: float = 0.0
