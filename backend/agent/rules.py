"""Deterministic eligibility rules and scoring. No LLM in here."""
from __future__ import annotations

import re
from typing import Optional

from backend.schemas import CheckResult, ProfileIn, Requirement, ScoreResult

_UNITS = {
    "thousand": 1e3, "k": 1e3, "lakh": 1e5, "lac": 1e5, "lacs": 1e5, "lakhs": 1e5,
    "million": 1e6, "mn": 1e6, "m": 1e6, "crore": 1e7, "cr": 1e7, "billion": 1e9, "bn": 1e9, "b": 1e9,
}
_MONEY_RE = re.compile(
    r"(?:(?:pkr|rs\.?|rupees)\s*)?(\d[\d,]*(?:\.\d+)?)\s*"
    r"(thousand|lakhs?|lacs?|million|mn|crore|cr|billion|bn|k|m|b)?\b",
    re.I,
)
_CURRENCY_RE = re.compile(r"pkr|rs\.?\s*\d|rupees", re.I)


def parse_pkr(text: Optional[str]) -> Optional[int]:
    """'PKR 30 million', 'Rs. 5 crore', '2.5M', '50,000,000' to rupees. None if there is no amount."""
    if not text:
        return None
    candidates = []
    for m in _MONEY_RE.finditer(text):
        number = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").lower()
        has_currency = bool(_CURRENCY_RE.search(m.group(0)))
        if not unit and not has_currency and number < 100_000:
            continue  # a bare '3' or '2026' is not money
        candidates.append(int(number * _UNITS.get(unit, 1)))
    return max(candidates) if candidates else None


def parse_years(text: Optional[str]) -> Optional[int]:
    m = re.search(r"(\d+)\s*(?:\+\s*)?(?:years?|yrs?)", text or "", re.I)
    return int(m.group(1)) if m else None


def pkr(n: int) -> str:
    if n >= 1_000_000_000:
        return f"PKR {n / 1e9:g}B"
    if n >= 1_000_000:
        return f"PKR {n / 1e6:g}M"
    return f"PKR {n:,}"


def _result(req: Requirement, status: str, reason: str, method: str = "rule") -> CheckResult:
    return CheckResult(**req.model_dump(), status=status, reason=reason, method=method)


def check_turnover(req: Requirement, profile: ProfileIn) -> CheckResult:
    need = parse_pkr(req.threshold) or parse_pkr(req.requirement)
    if need is None:
        return _result(req, "unclear", "Could not read a turnover figure from the clause.")
    have = profile.annual_turnover_pkr
    if have >= need:
        return _result(req, "pass", f"Turnover {pkr(have)} meets the {pkr(need)} minimum.")
    return _result(req, "fail", f"Turnover {pkr(have)} is below the {pkr(need)} minimum.")


_SIMILAR_RE = re.compile(r"similar|project|implement|assignment|deploy|deliver|complet|digiti[sz]ed", re.I)


def check_years(req: Requirement, profile: ProfileIn) -> Optional[CheckResult]:
    """Years in business only. Returns None for 'similar experience' clauses, which need judgement."""
    text = f"{req.threshold or ''} {req.requirement}"
    years = parse_years(text)
    if years is None or _SIMILAR_RE.search(text):
        return None
    have = profile.years_in_business
    if have >= years:
        return _result(req, "pass", f"{have} years in business meets the {years} year minimum.")
    return _result(req, "fail", f"{have} years in business is below the {years} year minimum.")


_PEC_RE = re.compile(r"\bC\s*-?\s*([1-6AB])\b", re.I)


def _pec_rank(text: Optional[str]) -> Optional[int]:
    """CA > CB > C1 ... > C6. Lower rank means a higher category."""
    m = _PEC_RE.search(text or "")
    if not m:
        return None
    return {"A": -1, "B": 0}.get(m.group(1).upper(), None) if m.group(1).upper() in "AB" else int(m.group(1))


def check_registration(req: Requirement, profile: ProfileIn) -> CheckResult:
    text = f"{req.threshold or ''} {req.requirement} {req.source_quote}"
    regs = profile.registrations
    missing, held = [], []

    def record(name: str, ok: bool) -> None:
        (held if ok else missing).append(name)

    found_any = False
    if re.search(r"\bNTN\b|national tax number", text, re.I):
        found_any = True
        record("NTN", bool(regs.ntn))
    if re.search(r"\bATL\b|active tax\s?payers?", text, re.I):
        found_any = True
        record("ATL", (regs.atl_status or "").lower() == "active")
    if re.search(r"\bSECP\b|securities and exchange", text, re.I):
        found_any = True
        record("SECP", bool(regs.secp))
    if re.search(r"\bPSEB\b|software export board", text, re.I):
        found_any = True
        record("PSEB", bool(regs.pseb))
    if re.search(r"\bPEC\b|pakistan engineering council", text, re.I):
        found_any = True
        need, have = _pec_rank(text), _pec_rank(regs.pec_category)
        if not regs.pec_category:
            record("PEC", False)
        elif need is not None and have is not None:
            record(f"PEC {regs.pec_category}", have <= need)
        else:
            return _result(req, "unclear", "PEC category could not be compared; check the discipline and category.")
    if not found_any:
        return _result(req, "unclear", "This registration is not on the company profile; confirm it manually.")
    if missing:
        return _result(req, "fail", f"Profile lacks: {', '.join(missing)}.")
    return _result(req, "pass", f"Profile holds: {', '.join(held)}.")


_PROVINCE_OF = {
    "islamabad": "ict", "rawalpindi": "punjab", "lahore": "punjab", "faisalabad": "punjab", "multan": "punjab",
    "gujranwala": "punjab", "sialkot": "punjab", "karachi": "sindh", "hyderabad": "sindh", "sukkur": "sindh",
    "peshawar": "kp", "abbottabad": "kp", "mardan": "kp", "quetta": "balochistan", "gwadar": "balochistan",
    "muzaffarabad": "ajk", "gilgit": "gb",
}
_PROVINCE_NAMES = {
    "punjab": "punjab", "sindh": "sindh", "khyber pakhtunkhwa": "kp", "kpk": "kp", "kp": "kp",
    "balochistan": "balochistan", "ict": "ict",
}
_ALTERNATIVE_RE = re.compile(r"undertaking|within \d+ days|or establish|to establish|liaison|joint venture|\bJV\b", re.I)


def check_location(req: Requirement, profile: ProfileIn) -> CheckResult:
    text = f"{req.threshold or ''} {req.requirement} {req.source_quote}"
    lowered = text.lower()
    city = profile.city.strip().lower()
    province = _PROVINCE_OF.get(city)
    cities = {c for c in _PROVINCE_OF if re.search(rf"\b{c}\b", lowered)}
    provinces = {p for n, p in _PROVINCE_NAMES.items() if re.search(rf"\b{n}\b", lowered)}
    if not cities and not provinces:
        if re.search(r"\bpakistan\b", lowered):
            return _result(req, "pass", f"Office in {profile.city}, Pakistan.")
        return _result(req, "unclear", "Could not identify the required location.")
    if city in cities or (province and province in provinces):
        return _result(req, "pass", f"Company office in {profile.city} satisfies this.")
    wanted = ", ".join(sorted(cities | provinces)).title()
    if _ALTERNATIVE_RE.search(text):
        return _result(req, "unclear", f"No office in {wanted}, but the clause allows an alternative such as an undertaking.")
    return _result(req, "fail", f"Company is in {profile.city}; the clause requires {wanted}.")


# --- Scoring ------------------------------------------------------------------------------------

DOMAINS: dict[str, str] = {
    "web": r"\bweb\b|web[- ]?(?:portal|app|application|site)s?|\bportals?\b|\bwebsites?\b",
    "mobile": r"\bmobile\b|\bandroid\b|\bios\b",
    "AI": r"\bAI\b|\bchatbots?\b|artificial intelligence|machine learning|conversational|\bNLP\b",
    "cloud": r"\bcloud\b|\bAWS\b|\bazure\b",
    "networking": r"\bnetwork(?:s|ing)?\b(?! attached)|\bLAN\b|\bWAN\b|wi-?fi|\bswitch(?:es)?\b|\bfirewalls?\b",
    "ERP": r"\bERP\b|enterprise resource planning|\bpayroll\b",
    "cybersecurity": r"\bcyber|\bSIEM\b|\bSOC\b|security operations|penetration test",
    "digitization": r"digiti[sz]|\bscan(?:ning)?\b",
    "health systems": r"\bHMIS\b|hospital management|\blaboratory\b|\bpharmacy\b",
    "core banking": r"core banking|payment switch",
    "construction": r"\bconstruct|civil works|\bHVAC\b|\bbuilding\b",
    "telecom": r"\bfibre\b|\bfiber\b|\bDWDM\b|\bbackbone\b|\btelecom",
    "hardware supply": r"\bhardware\b|\blaptops?\b|\bservers?\b|\bprinters?\b|\bdesktops?\b|\bNAS\b|network attached|\bstorage\b",
}


def domains_in(text: str) -> set[str]:
    return {name for name, pattern in DOMAINS.items() if re.search(pattern, text, re.I)}


def capability_match(title: str, scope: str, profile: ProfileIn) -> tuple[float, set[str], set[str]]:
    """Share of the tender's technical domains the company covers."""
    tender = domains_in(f"{title} {scope}")
    ours = domains_in(" ".join(profile.capabilities))
    if not tender:
        return 0.3, set(), set()  # nothing recognisable: do not reward or disqualify
    covered = tender & ours
    return len(covered) / len(tender), covered, tender - ours


CHECK_VALUE = {"pass": 1.0, "unclear": 0.5, "fail": 0.0}


def eligibility_ratio(checks: list[CheckResult]) -> float:
    """Mandatory clauses count fully, preferred ones half. Paperwork counts little: it can be produced."""
    total = got = 0.0
    for c in checks:
        weight = 0.25 if c.type == "document" else 1.0 if c.mandatory else 0.5
        total += weight
        got += weight * CHECK_VALUE[c.status]
    return got / total if total else 0.5


def value_fit(value: Optional[int], profile: ProfileIn) -> float:
    """How well the contract size suits the company, relative to annual turnover."""
    if not value or not profile.annual_turnover_pkr:
        return 0.5
    ratio = value / profile.annual_turnover_pkr
    if ratio < 0.02:
        return 0.3
    if ratio < 0.1:
        return 0.6
    if ratio <= 0.5:
        return 1.0
    if ratio <= 1.0:
        return 0.7
    if ratio <= 2.0:
        return 0.35
    return 0.1


def label_for(score: int) -> str:
    return "strong" if score >= 70 else "partial" if score >= 30 else "non_fit"


def score_fit(title: str, scope: str, value: Optional[int], checks: list[CheckResult], profile: ProfileIn) -> ScoreResult:
    capability, covered, gaps = capability_match(title, scope, profile)
    eligibility = eligibility_ratio(checks)
    size = value_fit(value, profile)
    raw = round(capability * 40 + eligibility * 40 + size * 20)
    blockers = [c for c in checks if c.mandatory and c.status == "fail"]
    score = min(raw, 20) if blockers else raw
    label = label_for(score)
    if blockers:
        reason = f"Disqualified: {blockers[0].reason}"
    elif label == "strong":
        reason = f"Strong match on {', '.join(sorted(covered)) or 'scope'}; eligibility {eligibility:.0%} satisfied."
    else:
        gap = f"gaps in {', '.join(sorted(gaps))}" if gaps else "scope is only partly covered"
        unclear = sum(c.status == "unclear" and c.type != "document" for c in checks)
        reason = f"Partial fit: {gap}; {unclear} clause(s) need confirmation."
    return ScoreResult(
        score=score,
        label=label,
        reason=reason,
        capped=bool(blockers),
        capability=round(capability, 3),
        eligibility=round(eligibility, 3),
        value_fit=size,
    )
