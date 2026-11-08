"""Runtime settings. The UI's demo toggle persists here and overrides the DEMO_MODE env default."""
from sqlmodel import Session

from backend.config import get_settings
from backend.models import AppSetting

DEMO_KEY = "demo_mode"


def get_demo_mode(session: Session) -> bool:
    row = session.get(AppSetting, DEMO_KEY)
    return row.value == "true" if row else get_settings().demo_mode


def set_demo_mode(session: Session, enabled: bool) -> bool:
    row = session.get(AppSetting, DEMO_KEY) or AppSetting(key=DEMO_KEY, value="")
    row.value = "true" if enabled else "false"
    session.add(row)
    session.commit()
    return enabled
