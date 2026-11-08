"""Company profile storage. A single row; the default is created on first use."""
from sqlmodel import Session, select

from backend.models import CompanyProfile, utcnow
from backend.schemas import ProfileIn

# Sample data: past projects and registration numbers are placeholders to replace with real records.
DEFAULT_PROFILE = ProfileIn(
    name="Margalla Software House (Pvt) Ltd",
    city="Islamabad",
    team_size=20,
    annual_turnover_pkr=50_000_000,
    years_in_business=6,
    capabilities=["web apps", "mobile apps", "AI chatbots", "cloud (AWS/Azure)", "networking"],
    registrations={
        "ntn": "0000000-0",
        "atl_status": "active",
        "pec_category": None,
        "secp": "0000000",
        "pseb": "Z-00000",
    },
    past_projects=[
        {"title": "Citizen Services Web Portal and Mobile App", "client": "Federal Government Department",
         "value_pkr": 12_000_000, "year": 2024},
        {"title": "Hospital Appointment Mobile App", "client": "Provincial Health Authority",
         "value_pkr": 8_500_000, "year": 2023},
        {"title": "AI Customer Support Chatbot", "client": "Commercial Bank",
         "value_pkr": 6_000_000, "year": 2025},
        {"title": "Campus Network Upgrade", "client": "Public University",
         "value_pkr": 15_000_000, "year": 2022},
        {"title": "AWS Cloud Migration", "client": "Regional Logistics Company",
         "value_pkr": 4_500_000, "year": 2024},
    ],
)


def get_or_create_profile(session: Session) -> CompanyProfile:
    row = session.exec(select(CompanyProfile)).first()
    if row is None:
        row = CompanyProfile(**DEFAULT_PROFILE.model_dump())
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def update_profile(session: Session, data: ProfileIn) -> CompanyProfile:
    row = get_or_create_profile(session)
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    row.updated_at = utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def profile_to_schema(row: CompanyProfile) -> ProfileIn:
    return ProfileIn.model_validate(row.model_dump(exclude={"id", "updated_at"}))
