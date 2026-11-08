"""Tender collector: the agent's eyes.

Source: https://epms.ppra.gov.pk/public/tenders/active-tenders (ppra.org.pk now redirects to ppra.gov.pk,
which links here). Polite by construction: fixed user agent, 1 request/sec, 15s timeout, disk cache.
Falls back to data/seed/ when DEMO_MODE is on or the site fails, and says so in the result.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import shutil
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
import pdfplumber
from bs4 import BeautifulSoup, Tag
from sqlmodel import Session, select

from backend.config import get_settings
from backend.models import Tender
from backend.seed import render_document, seed_records

log = logging.getLogger(__name__)

BASE_URL = "https://epms.ppra.gov.pk"
LISTING_PATH = "/public/tenders/active-tenders"
ICT_SECTOR = 14  # "Info and Comm Tech" in the site's sector filter
USER_AGENT = "TenderScout/0.1"
TIMEOUT_S = 15.0
MIN_INTERVAL_S = 1.0
CACHE_TTL_S = 6 * 3600
MAX_DOWNLOAD_BYTES = 30 * 1024 * 1024
MAX_PAGES = 3
CRAWL_BUDGET_S = 60.0
ALLOWED_HOSTS = {"ppra.gov.pk", "epms.ppra.gov.pk", "ppra.org.pk", "www.ppra.org.pk", "epads.gov.pk", "eprocure.gov.pk"}
SEARCH_KEYWORDS = ["software", "digitization", "automation", "network", "ERP", "website", "cloud"]

# IT and AI are case-sensitive: "with", "digitization" and "said" must not match.
_KEYWORD_RE = re.compile(
    r"\b(?:software|digiti[sz]ation|digiti[sz]e|automation|networks?|networking|erp|websites?|cloud)\b",
    re.I,
)
_ACRONYM_RE = re.compile(r"\b(?:IT|AI)\b")
# Seen on the live site: "gas network" and utility works matched the keywords above.
_NOT_IT_RE = re.compile(
    r"civil works|construction of|masonry|retaining wall|ground bed|deep well|pipeline|gas network|"
    r"distribution network|road network|irrigation|sewerage|water supply",
    re.I,
)


class CollectorError(RuntimeError):
    pass


class DisallowedHost(CollectorError):
    """Refused: the URL is not on a procurement host we trust."""


@dataclass
class Listing:
    tender_no: str
    title: str
    agency: str = ""
    published_date: Optional[str] = None
    closing_date: Optional[str] = None
    detail_url: Optional[str] = None
    document_url: Optional[str] = None
    sector: str = ""
    status: str = ""
    source: str = "ppra"


@dataclass
class ListingResult:
    listings: list[Listing] = field(default_factory=list)
    source: str = "ppra"  # ppra | seed
    fallback_reason: Optional[str] = None
    pages_fetched: int = 0


def matches_keywords(text: str) -> bool:
    if _NOT_IT_RE.search(text):
        return False
    return bool(_KEYWORD_RE.search(text) or _ACRONYM_RE.search(text))


def _parse_date(text: str) -> Optional[str]:
    text = " ".join(text.split())
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _text(node: Optional[Tag]) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def _detail_field(detail_row: Optional[Tag], label: str) -> Optional[Tag]:
    if detail_row is None:
        return None
    for dl in detail_row.select(".cb-rt-dl"):
        if _text(dl).lower() == label.lower():
            return dl.find_next_sibling(class_="cb-rt-dv")
    return None


def parse_listings(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "lxml")
    out: list[Listing] = []
    for row in soup.select("table.cb-rt tr.cb-rt-main"):
        no = _text(row.select_one('td[data-label="Tender No"] strong.cb-rt-name'))
        title = _text(row.select_one('td[data-label="Tender Details"] strong'))
        if not no or not title:
            continue
        link = row.select_one('td[data-label="Actions"] a[href*="tender-details"]')
        detail = row.find_next_sibling("tr", class_="cb-rt-detail")
        org = _detail_field(detail, "Organization")
        out.append(
            Listing(
                tender_no=no,
                title=title,
                agency=_text(org.find("strong")) if org else "",
                published_date=_parse_date(_text(row.select_one('td[data-label="Advertised"]'))),
                closing_date=_parse_date(_text(row.select_one('td[data-label="Closing"] strong'))),
                detail_url=urljoin(BASE_URL, link["href"]) if link else None,
                sector=_text(_detail_field(detail, "Sector")),
                status=_text(row.select_one('td[data-label="Status"] .tender-badge')),
            )
        )
    return out


def parse_next_page(html: str, current: int) -> Optional[int]:
    pages = [
        int(m.group(1))
        for a in BeautifulSoup(html, "lxml").select('a.page-link[href*="page="]')
        if (m := re.search(r"page=(\d+)", a.get("href", "")))
    ]
    later = [p for p in pages if p > current]
    return min(later) if later else None


def parse_document_links(html: str) -> dict[str, str]:
    """Returns {"tender_document": url, "advertisement": url} from a tender detail page."""
    links: dict[str, str] = {}
    for a in BeautifulSoup(html, "lxml").select('a[href^="/pdf?file="]'):
        label = _text(a).lower()
        key = "tender_document" if "tender document" in label else "advertisement" if "advert" in label else None
        if key:
            links.setdefault(key, urljoin(BASE_URL, a["href"]))
    return links


def check_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or (parsed.hostname or "").lower() not in ALLOWED_HOSTS:
        raise DisallowedHost(f"Refusing to fetch {url!r}: not an allowlisted procurement host")


class PoliteClient:
    """Rate limited, cached HTTP client. Every hop, including redirects, must be on the allowlist."""

    _lock = asyncio.Lock()
    _last_request = 0.0

    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None, min_interval: float = MIN_INTERVAL_S):
        self.min_interval = min_interval
        self.cache_dir = get_settings().cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        async def _check_hop(request: httpx.Request) -> None:
            check_url(str(request.url))

        self._client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_S,
            follow_redirects=True,
            transport=transport,
            event_hooks={"request": [_check_hop]},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _throttle(self) -> None:
        cls = PoliteClient
        async with cls._lock:
            wait = self.min_interval - (time.monotonic() - cls._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            cls._last_request = time.monotonic()

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / hashlib.sha256(url.encode()).hexdigest()

    async def get_bytes(self, url: str, ttl: float = CACHE_TTL_S) -> bytes:
        check_url(url)
        path = self._cache_path(url)
        if path.exists() and time.time() - path.stat().st_mtime < ttl:
            return path.read_bytes()
        for attempt in (1, 2):  # the live site drops connections now and then
            await self._throttle()
            try:
                data = await self._download(url)
                break
            except httpx.TransportError:
                if attempt == 2:
                    raise
                log.info("Retrying %s after a transport error", url)
        path.write_bytes(data)
        return data

    async def _download(self, url: str) -> bytes:
        buf = bytearray()
        async with self._client.stream("GET", url) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes():
                buf.extend(chunk)
                if len(buf) > MAX_DOWNLOAD_BYTES:
                    raise CollectorError(f"{url} is larger than {MAX_DOWNLOAD_BYTES} bytes")
        return bytes(buf)

    async def get_text(self, url: str, ttl: float = CACHE_TTL_S) -> str:
        return (await self.get_bytes(url, ttl)).decode("utf-8", errors="replace")


def seed_listings() -> list[Listing]:
    today = date.today()
    return [
        Listing(
            tender_no=r["external_id"],
            title=r["title"],
            agency=r["agency"],
            published_date=(today - timedelta(days=r["published_days_ago"])).isoformat(),
            closing_date=(today + timedelta(days=r["closing_in_days"])).isoformat(),
            document_url=f"seed://{r['external_id']}",
            sector="Info and Comm Tech",
            status="Published",
            source="seed",
        )
        for r in seed_records()
    ]


async def _crawl(client: PoliteClient, max_pages: int, budget_s: float = CRAWL_BUDGET_S) -> tuple[list[Listing], int]:
    """ICT sector pages first (most relevant), then one page per keyword. Stops at the time budget."""
    found: dict[str, Listing] = {}
    fetched = 0
    deadline = time.monotonic() + budget_s
    queries = [(f"sector={ICT_SECTOR}", max_pages)] + [(f"keyword={k}", 1) for k in SEARCH_KEYWORDS]
    for query, limit in queries:
        page: Optional[int] = 1
        while page and page <= limit:
            if time.monotonic() > deadline:
                log.warning("Crawl budget reached after %s pages; using what was found", fetched)
                return list(found.values()), fetched
            try:
                html = await client.get_text(f"{BASE_URL}{LISTING_PATH}?{query}&page={page}")
            except (httpx.HTTPError, CollectorError):
                if found:  # keep a partial crawl rather than discarding it
                    log.warning("Crawl stopped early at %s page %s", query, page, exc_info=True)
                    return list(found.values()), fetched
                raise
            fetched += 1
            for item in parse_listings(html):
                found.setdefault(item.tender_no, item)
            page = parse_next_page(html, page)
    return list(found.values()), fetched


async def fetch_tender_listings(
    demo_mode: bool, client: Optional[PoliteClient] = None, max_pages: int = MAX_PAGES
) -> ListingResult:
    """Open tenders matching the IT keywords, or seed data when demo mode is on or the site fails."""
    if demo_mode:
        return ListingResult(seed_listings(), source="seed", fallback_reason="DEMO_MODE is on")
    owned = client is None
    client = client or PoliteClient()
    try:
        raw, pages = await _crawl(client, max_pages)
    except (httpx.HTTPError, CollectorError) as exc:
        log.warning("PPRA fetch failed, using seed data: %s", exc)
        return ListingResult(seed_listings(), source="seed", fallback_reason=f"PPRA fetch failed: {exc}")
    finally:
        if owned:
            await client.aclose()
    if not raw:
        # A 200 with no rows means the markup changed or the site is serving an error page.
        reason = "PPRA returned no parseable tender rows"
        log.warning("%s, using seed data", reason)
        return ListingResult(seed_listings(), source="seed", fallback_reason=reason)
    today = date.today().isoformat()
    kept = [
        t for t in raw if matches_keywords(t.title) and (t.closing_date is None or t.closing_date >= today)
    ]
    return ListingResult(kept, source="ppra", pages_fetched=pages)


def save_listings(session: Session, result: ListingResult) -> list[Tender]:
    rows = []
    for item in result.listings:
        row = session.exec(select(Tender).where(Tender.external_id == item.tender_no)).first()
        if row is None:
            row = Tender(external_id=item.tender_no, title=item.title, source=item.source)
        row.title = item.title
        row.agency = item.agency or row.agency
        row.published_date = date.fromisoformat(item.published_date) if item.published_date else row.published_date
        row.closing_date = date.fromisoformat(item.closing_date) if item.closing_date else row.closing_date
        row.document_url = item.document_url or item.detail_url or row.document_url
        if item.source == "seed" and not row.text_path:
            rec = next(r for r in seed_records() if r["external_id"] == item.tender_no)
            row.text_path = str(render_document(rec))
        session.add(row)
        rows.append(row)
    session.commit()
    for row in rows:
        session.refresh(row)
    return rows


def _safe_name(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


async def download_document(url: str, workspace: Path, client: Optional[PoliteClient] = None) -> Path:
    """Saves a tender document into the run workspace. Accepts seed://, a PDF URL or a tender detail URL."""
    workspace.mkdir(parents=True, exist_ok=True)
    if url.startswith("seed://"):
        ext_id = url.removeprefix("seed://")
        rec = next((r for r in seed_records() if r["external_id"] == ext_id), None)
        if rec is None:
            raise CollectorError(f"Unknown seed tender {ext_id!r}")
        target = workspace / rec["document"]
        shutil.copyfile(render_document(rec), target)
        return target
    check_url(url)
    owned = client is None
    client = client or PoliteClient()
    try:
        if "/tender-details/" in url:
            links = parse_document_links(await client.get_text(url))
            pdf_url = links.get("tender_document") or links.get("advertisement")
            if not pdf_url:
                raise CollectorError(f"No document link on {url}")
            url = pdf_url
        data = await client.get_bytes(url)
    finally:
        if owned:
            await client.aclose()
    if not data.startswith(b"%PDF"):
        raise CollectorError(f"{url} did not return a PDF")
    target = workspace / f"{_safe_name(url)}.pdf"
    target.write_bytes(data)
    return target


@dataclass
class ExtractResult:
    path: Optional[str]
    preview: str
    status: str  # ok | empty | needs_ocr | unreadable
    pages: int = 0
    chars: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


MIN_TEXT_CHARS = 40


def extract_text(path: Path | str) -> ExtractResult:
    """PDF to .txt beside the original. Returns the path and the first 500 chars.

    needs_ocr: pages have images but no text layer (a scan). empty: no pages or nothing on them.
    """
    path = Path(path)
    if path.suffix.lower() == ".txt":
        text = path.read_text(errors="replace")
        status = "ok" if len(text.strip()) >= MIN_TEXT_CHARS else "empty"
        return ExtractResult(str(path), text[:500], status, 1, len(text))
    try:
        with pdfplumber.open(path) as pdf:
            pages = len(pdf.pages)
            parts, images = [], 0
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
                images += len(page.images)
    except Exception as exc:  # pdfplumber raises many types on corrupt input
        log.warning("Could not read %s: %s", path, exc)
        return ExtractResult(None, "", "unreadable")
    text = "\n\n".join(parts).strip()
    if len(text) < MIN_TEXT_CHARS:
        return ExtractResult(None, "", "needs_ocr" if images else "empty", pages, len(text))
    out = path.with_suffix(".txt")
    out.write_text(text)
    return ExtractResult(str(out), text[:500], "ok", pages, len(text))
