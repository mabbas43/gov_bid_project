from datetime import date
from pathlib import Path

import httpx
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from backend.agent.tools import collector as col
from backend.agent.tools.collector import (
    DisallowedHost,
    PoliteClient,
    download_document,
    extract_text,
    fetch_tender_listings,
    matches_keywords,
    parse_document_links,
    parse_listings,
    parse_next_page,
)

FIX = Path(__file__).parent / "fixtures"
LIST_HTML = (FIX / "ppra_active_ict.html").read_text()
DETAIL_HTML = (FIX / "ppra_tender_detail.html").read_text()


def client_for(handler):
    return PoliteClient(transport=httpx.MockTransport(handler), min_interval=0)


def test_parse_real_listing_fixture():
    rows = parse_listings(LIST_HTML)
    assert len(rows) == 42  # page said "Showing 42 of 42 tenders"
    first = rows[0]
    assert first.tender_no.startswith("TS") and first.title
    assert first.agency
    assert first.closing_date and date.fromisoformat(first.closing_date)
    assert first.published_date and date.fromisoformat(first.published_date)
    assert first.detail_url.startswith("https://epms.ppra.gov.pk/public/tenders/tender-details/")
    assert first.sector == "Info and Comm Tech"
    assert all(r.agency and r.closing_date for r in rows)


def test_parse_document_links_real_fixture():
    links = parse_document_links(DETAIL_HTML)
    assert links["tender_document"].startswith("https://epms.ppra.gov.pk/pdf?file=")
    assert "advertisement" in links


@pytest.mark.parametrize(
    "title,hit",
    [
        ("Procurement of Software Licences", True),
        ("Supply of IT Equipment", True),
        ("AI based Chatbot", True),
        ("Digitization of Land Records", True),
        ("ERP implementation", True),
        ("Website development", True),
        ("Network switches", True),
        ("Supply of Medicines with delivery", False),  # 'with' contains no IT token
        ("Repair of gates", False),
        ("Said hospital audit", False),  # 'said' contains 'ai'
        ("Fitting of pipes", False),
        ("Civil Works Laying of Deep Well Ground Bed for Gas Network", False),
        ("construction of stone masonry retaining wall", False),
    ],
)
def test_keyword_filter(title, hit):
    assert matches_keywords(title) is hit


def test_next_page():
    html = '<a class="page-link" href="?page=1">1</a><a class="page-link" href="?page=2">2</a>'
    assert parse_next_page(html, 1) == 2
    assert parse_next_page(html, 2) is None


async def test_demo_mode_never_touches_network():
    def boom(_):
        raise AssertionError("network used in demo mode")

    c = client_for(boom)
    r = await fetch_tender_listings(demo_mode=True, client=c)
    await c.aclose()
    assert r.source == "seed" and len(r.listings) == 12 and "DEMO_MODE" in r.fallback_reason


async def test_live_fetch_filters_and_dedupes():
    c = client_for(lambda req: httpx.Response(200, text=LIST_HTML))
    r = await fetch_tender_listings(demo_mode=False, client=c)
    await c.aclose()
    assert r.source == "ppra" and r.fallback_reason is None
    assert 0 < len(r.listings) <= 42
    assert len({t.tender_no for t in r.listings}) == len(r.listings)
    assert all(matches_keywords(t.title) for t in r.listings)


@pytest.mark.parametrize(
    "handler",
    [
        lambda req: httpx.Response(503, text="down"),
        lambda req: httpx.Response(200, text="<html>maintenance</html>"),
    ],
)
async def test_site_failure_falls_back_to_seed(handler):
    c = client_for(handler)
    r = await fetch_tender_listings(demo_mode=False, client=c)
    await c.aclose()
    assert r.source == "seed" and len(r.listings) == 12 and r.fallback_reason


async def test_timeout_falls_back_to_seed():
    def slow(req):
        raise httpx.ConnectTimeout("timed out", request=req)

    c = client_for(slow)
    r = await fetch_tender_listings(demo_mode=False, client=c)
    await c.aclose()
    assert r.source == "seed" and "failed" in r.fallback_reason


async def test_transient_transport_error_is_retried():
    calls = []

    def handler(req):
        calls.append(req)
        if len(calls) == 1:
            raise httpx.RemoteProtocolError("Server disconnected", request=req)
        return httpx.Response(200, content=b"%PDF-ok")

    c = client_for(handler)
    assert await c.get_bytes("https://epms.ppra.gov.pk/pdf?file=y") == b"%PDF-ok"
    await c.aclose()
    assert len(calls) == 2


async def test_responses_are_cached_and_user_agent_set():
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200, text="hello")

    c = client_for(handler)
    url = "https://epms.ppra.gov.pk/x"
    assert await c.get_text(url) == "hello"
    assert await c.get_text(url) == "hello"
    await c.aclose()
    assert len(seen) == 1 and seen[0].headers["user-agent"] == "TenderScout/0.1"


async def test_rejects_non_procurement_hosts(tmp_path):
    with pytest.raises(DisallowedHost):
        await download_document("http://169.254.169.254/latest/meta-data", tmp_path)
    with pytest.raises(DisallowedHost):
        await download_document("file:///etc/passwd", tmp_path)


async def test_redirect_to_other_host_is_blocked():
    c = client_for(lambda req: httpx.Response(302, headers={"location": "https://evil.example/x"}))
    with pytest.raises(DisallowedHost):
        await c.get_bytes("https://epms.ppra.gov.pk/start")
    await c.aclose()


async def test_download_via_detail_page(tmp_path):
    pdf = b"%PDF-1.4 fake"

    def handler(req):
        if "tender-details" in str(req.url):
            return httpx.Response(200, text=DETAIL_HTML)
        return httpx.Response(200, content=pdf)

    c = client_for(handler)
    path = await download_document(
        "https://epms.ppra.gov.pk/public/tenders/tender-details/X", tmp_path, client=c
    )
    await c.aclose()
    assert path.parent == tmp_path and path.read_bytes() == pdf


async def test_download_rejects_non_pdf(tmp_path):
    c = client_for(lambda req: httpx.Response(200, text="<html>error</html>"))
    with pytest.raises(col.CollectorError):
        await download_document("https://epms.ppra.gov.pk/pdf?file=x", tmp_path, client=c)
    await c.aclose()


def _pdf_with_text(path, text):
    cv = canvas.Canvas(str(path), pagesize=A4)
    cv.drawString(72, 720, text)
    cv.save()


def test_extract_text_pdf(tmp_path):
    p = tmp_path / "a.pdf"
    _pdf_with_text(p, "Minimum annual turnover of PKR 30 million is required of all bidders.")
    r = extract_text(p)
    assert r.status == "ok" and "turnover" in r.preview
    assert Path(r.path).read_text().startswith("Minimum")


def test_extract_blank_pdf_is_empty(tmp_path):
    p = tmp_path / "blank.pdf"
    cv = canvas.Canvas(str(p))
    cv.showPage()
    cv.save()
    assert extract_text(p).status == "empty"


def test_extract_scanned_pdf_needs_ocr(tmp_path):
    from PIL import Image

    img = tmp_path / "scan.png"
    Image.new("RGB", (200, 200), "white").save(img)
    p = tmp_path / "scan.pdf"
    cv = canvas.Canvas(str(p))
    cv.drawImage(ImageReader(str(img)), 50, 50, 200, 200)
    cv.showPage()
    cv.save()
    r = extract_text(p)
    assert r.status == "needs_ocr" and r.path is None


def test_extract_corrupt_pdf(tmp_path):
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"not a pdf at all")
    assert extract_text(p).status == "unreadable"


async def test_partial_crawl_survives_later_failure():
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(200, text=LIST_HTML) if len(calls) == 1 else httpx.Response(500)

    c = client_for(handler)
    r = await fetch_tender_listings(demo_mode=False, client=c)
    await c.aclose()
    assert r.source == "ppra" and r.listings


async def test_crawl_budget_stops_early():
    c = client_for(lambda req: httpx.Response(200, text=LIST_HTML))
    rows, pages = await col._crawl(c, max_pages=3, budget_s=0)
    await c.aclose()
    assert rows == [] and pages == 0
