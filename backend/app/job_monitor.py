import ipaddress
import logging
import os
import re
from datetime import date, datetime
from html.parser import HTMLParser
from zoneinfo import ZoneInfo
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from sqlalchemy import select

from .database import SessionLocal
from .models import JobLink

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = max(60, int(os.getenv("JOB_MONITOR_INTERVAL_SECONDS", "900")))
MAX_PAGE_BYTES = 2_000_000
SOURCE_TIMEOUT_SECONDS = 20
INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")
APPLICATION_TERMS = re.compile(
    r"\b(?:apply|application|register|registration|online form)\b", re.IGNORECASE
)
START_LABEL = re.compile(
    r"\b(?:start(?:ing)? date|opening date|application(?:s)? (?:start|begin)|"
    r"registration (?:start|begin)|apply from|from)\b",
    re.IGNORECASE,
)
END_LABEL = re.compile(
    r"\b(?:last date|closing date|end date|application(?:s)? (?:close|end)|"
    r"registration (?:close|end)|apply till|apply up to|to)\b",
    re.IGNORECASE,
)
DATE_TOKEN = re.compile(
    r"\b(?:"
    r"\d{4}-\d{1,2}-\d{1,2}|"
    r"\d{1,2}[/-]\d{1,2}[/-]\d{4}|"
    r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|"
    r"[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}"
    r")\b"
)
GENERIC_TITLES = {
    "apply",
    "apply now",
    "apply online",
    "application",
    "application form",
    "click here",
    "click here to apply",
    "current openings",
    "careers",
    "home",
    "latest news",
    "online application",
    "online form",
    "register",
    "registration",
    "recruitment",
    "recruitment advertisement",
}
TRUSTED_APPLICATION_DOMAINS = ("gov.in", "nic.in", "sbi.co.in", "ibps.in")
SOURCES = (
    ("UPSC", "https://upsc.gov.in/recruitment/recruitment-advertisement"),
    ("SSC", "https://ssc.gov.in/"),
    ("RRB Chandigarh", "https://www.rrbcdg.gov.in/"),
    ("IBPS", "https://www.ibps.in/"),
    ("SBI Careers", "https://sbi.co.in/web/careers"),
)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text_parts = []
        self.text_length = 0
        self.links = []
        self.headings = []
        self.current_link = None
        self.current_heading = None

    def _append_text(self, text):
        self.text_parts.append(f" {text} ")
        self.text_length += len(text) + 2

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag.lower() == "a" and values.get("href"):
            self.current_link = {
                "href": values["href"],
                "offset": self.text_length,
                "parts": [],
            }
        if tag.lower() in {"h1", "h2", "h3"}:
            self.current_heading = {
                "offset": self.text_length,
                "parts": [],
            }

    def handle_data(self, data):
        self._append_text(data)
        if self.current_link is not None:
            self.current_link["parts"].append(data)
        if self.current_heading is not None:
            self.current_heading["parts"].append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.current_link is not None:
            self.current_link["text"] = " ".join(self.current_link.pop("parts")).strip()
            self.links.append(self.current_link)
            self.current_link = None
        if tag.lower() in {"h1", "h2", "h3"} and self.current_heading is not None:
            text = " ".join(self.current_heading["parts"]).strip()
            if text:
                self.headings.append({"offset": self.current_heading["offset"], "text": text})
            self.current_heading = None

    @property
    def text(self):
        return "".join(self.text_parts)


def _parse_date(value):
    value = value.strip().replace(",", "")
    formats = (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d %Y",
        "%b %d %Y",
    )
    for date_format in formats:
        try:
            return date.fromisoformat(value) if date_format == "%Y-%m-%d" else datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    return None


def _dates_from_context(context):
    matches = []
    for match in DATE_TOKEN.finditer(context):
        parsed = _parse_date(match.group())
        if parsed:
            before = context[max(0, match.start() - 90):match.start()]
            labels = [
                (label_match.start(), label)
                for label, pattern in (("start", START_LABEL), ("end", END_LABEL))
                for label_match in pattern.finditer(before)
            ]
            if labels:
                matches.append((max(labels)[1], parsed))

    start_date = next((value for label, value in matches if label == "start"), None)
    end_date = next((value for label, value in matches if label == "end"), None)

    if start_date is None or end_date is None:
        raw_dates = [(match.start(), _parse_date(match.group())) for match in DATE_TOKEN.finditer(context)]
        raw_dates = [(position, value) for position, value in raw_dates if value]
        if len(raw_dates) == 2 and re.search(r"\bfrom\b", context, re.IGNORECASE) and re.search(r"\bto\b", context, re.IGNORECASE):
            start_date = start_date or raw_dates[0][1]
            end_date = end_date or raw_dates[1][1]

    return start_date, end_date


def _safe_application_url(raw_url, source_url):
    url = urljoin(source_url, raw_url.strip())
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    try:
        address = ipaddress.ip_address(parsed.hostname)
        if not address.is_global:
            return None
    except ValueError:
        if "." not in parsed.hostname or parsed.hostname.lower() == "localhost":
            return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def _trusted_application_host(url):
    host = urlsplit(url).hostname or ""
    return any(host == domain or host.endswith(f".{domain}") for domain in TRUSTED_APPLICATION_DOMAINS)


def _is_generic_title(value):
    normalized = re.sub(r"\s+", " ", value).strip(" .:-").lower()
    return normalized in GENERIC_TITLES or len(normalized) < 5


def _candidate_title(link, headings, source_name):
    anchor_text = re.sub(r"\s+", " ", link["text"]).strip()
    if not _is_generic_title(anchor_text):
        return anchor_text[:200], True

    preceding = [
        heading for heading in headings
        if heading["offset"] <= link["offset"] and link["offset"] - heading["offset"] <= 500
    ]
    for heading in reversed(preceding):
        title = re.sub(r"\s+", " ", heading["text"]).strip()
        if not _is_generic_title(title):
            return title[:200], True
    return f"{source_name} application link", False


def extract_application_links(source_name, source_url, html):
    parser = PageParser()
    parser.feed(html)
    page_text = parser.text
    results = []
    seen_urls = set()

    for link in parser.links:
        anchor_text = re.sub(r"\s+", " ", link["text"]).strip()
        href_terms = urlsplit(urljoin(source_url, link["href"])).path
        if not (APPLICATION_TERMS.search(anchor_text) or APPLICATION_TERMS.search(href_terms)):
            continue
        if re.search(r"\b(?:notification|advertisement|syllabus|result|answer key|admit card)\b", anchor_text, re.IGNORECASE):
            continue

        apply_url = _safe_application_url(link["href"], source_url)
        if not apply_url or apply_url in seen_urls:
            continue
        seen_urls.add(apply_url)

        context_start = max(0, link["offset"] - 250)
        context_end = min(len(page_text), link["offset"] + len(anchor_text) + 250)
        context = page_text[context_start:context_end]
        start_date, end_date = _dates_from_context(context)
        title, title_confident = _candidate_title(link, parser.headings, source_name)

        reasons = []
        if start_date is None or end_date is None:
            reasons.append("Application start or end date could not be confirmed")
        if not title_confident:
            reasons.append("Job title could not be confidently identified")
        if not _trusted_application_host(apply_url):
            reasons.append("Application link is outside the monitored official domains")
        if start_date and end_date and end_date < start_date:
            reasons.append("Detected dates appear to be in the wrong order")
        if end_date and end_date < datetime.now(INDIA_TIMEZONE).date():
            reasons.append("Application period has already ended")

        results.append({
            "title": title,
            "apply_url": apply_url,
            "start_date": start_date,
            "end_date": end_date,
            "skip_reason": "; ".join(reasons),
        })
    return results


def _fetch_source(source_name, source_url):
    request = Request(
        source_url,
        headers={"User-Agent": "BharatOneJobLinkMonitor/1.0 (+official recruitment link monitoring)"},
    )
    with urlopen(request, timeout=SOURCE_TIMEOUT_SECONDS) as response:
        final_host = urlsplit(response.geturl()).hostname or ""
        source_host = urlsplit(source_url).hostname or ""
        if final_host != source_host and not final_host.endswith(f".{source_host}"):
            raise ValueError(f"{source_name} redirected outside its official website")
        content = response.read(MAX_PAGE_BYTES + 1)
        if len(content) > MAX_PAGE_BYTES:
            raise ValueError(f"{source_name} page exceeded the size limit")
        charset = response.headers.get_content_charset() or "utf-8"
        return content.decode(charset, errors="replace")


def scan_sources_once():
    added = 0
    with SessionLocal() as db:
        for source_name, source_url in SOURCES:
            try:
                html = _fetch_source(source_name, source_url)
                detections = extract_application_links(source_name, source_url, html)
            except (HTTPError, URLError, TimeoutError, ValueError, UnicodeError) as error:
                logger.warning("Job link scan failed for %s: %s", source_name, error)
                continue
            except Exception:
                logger.exception("Unexpected job link scan failure for %s", source_name)
                continue

            for detection in detections:
                if detection["skip_reason"]:
                    logger.info("Skipped %s link from %s: %s", detection["apply_url"], source_name, detection["skip_reason"])
                    continue
                if db.scalar(select(JobLink.id).where(JobLink.apply_url == detection["apply_url"])):
                    continue

                db.add(JobLink(
                    title=detection["title"],
                    apply_url=detection["apply_url"],
                    start_date=detection["start_date"],
                    end_date=detection["end_date"],
                ))
                db.commit()
                added += 1
            logger.info("Scanned %s and found %s application link(s)", source_name, len(detections))
    return added
