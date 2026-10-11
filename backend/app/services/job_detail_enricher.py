"""Fetch fuller text from public job pages for richer matching and application drafts.

This service only reads public HTTPS pages linked from saved job records. It does
not log in, execute JavaScript, bypass CAPTCHAs, or interact with application forms.
"""
from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_DESCRIPTION_CHARS = 30000
MAX_REDIRECTS = 4
USER_AGENT = "CareerMate-local/0.2 (+public job listing reader)"
_BLOCKED_TAGS = {"script", "style", "nav", "footer", "aside", "noscript", "svg", "iframe", "form", "button", "header"}
_BLOCK_START_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br", "section", "article", "div"}


class JobDetailFetchError(RuntimeError):
    """A public job listing could not safely be fetched or parsed."""


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0
        self._skip_tag_stack: list[str] = []
        self.json_ld: list[str] = []
        self._jsonld_depth = 0
        self._jsonld_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.casefold(): value or "" for key, value in attrs}
        if tag.casefold() == "script" and attrs_map.get("type", "").casefold() == "application/ld+json":
            self._jsonld_depth += 1
            return
        if tag.casefold() in _BLOCKED_TAGS:
            self._skip_depth += 1
            self._skip_tag_stack.append(tag.casefold())
            return
        if self._jsonld_depth:
            return
        if tag.casefold() in _BLOCK_START_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if self._jsonld_depth and tag == "script":
            self._jsonld_depth -= 1
            if self._jsonld_parts:
                self.json_ld.append("".join(self._jsonld_parts))
                self._jsonld_parts = []
            return
        if self._skip_depth:
            # HTML is frequently not perfectly nested; decrement only for a
            # closing tag that appears in the active skipped region.
            if tag in self._skip_tag_stack:
                reverse_index = self._skip_tag_stack[::-1].index(tag)
                index = len(self._skip_tag_stack) - 1 - reverse_index
                self._skip_tag_stack = self._skip_tag_stack[:index]
                self._skip_depth = len(self._skip_tag_stack)
            return
        if tag in _BLOCK_START_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._jsonld_depth:
            self._jsonld_parts.append(data)
        elif not self._skip_depth:
            value = re.sub(r"\s+", " ", data).strip()
            if value:
                self.parts.append(value)


def _normalize_text(value: str) -> str:
    value = html.unescape(value).replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    result: list[str] = []
    for line in lines:
        if not line:
            if result and result[-1] != "":
                result.append("")
            continue
        if not result or result[-1] != line:
            result.append(line)
    return "\n".join(result).strip()[:MAX_DESCRIPTION_CHARS]


def _html_to_text(value: str) -> str:
    parser = _VisibleTextParser()
    try:
        parser.feed(value)
        parser.close()
    except Exception:
        # Visible text is still useful on imperfect HTML.
        pass
    visible = _normalize_text("\n".join(parser.parts))
    structured = _json_ld_job_text(parser.json_ld)
    # JSON-LD JobPosting is explicitly structured for the job advert and is
    # often cleaner than visible text that includes recommendation widgets.
    if len(structured) >= 500 and "Description:" in structured:
        return structured
    if len(structured) > len(visible):
        return structured
    return visible


def _strip_html_fragment(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    parser = _VisibleTextParser()
    try:
        parser.feed(value)
        parser.close()
    except Exception:
        pass
    return _normalize_text("\n".join(parser.parts)) or _normalize_text(re.sub(r"<[^>]+>", " ", value))


def _flatten_jobposting(value: Any, output: list[str]) -> None:
    if isinstance(value, list):
        for item in value:
            _flatten_jobposting(item, output)
        return
    if not isinstance(value, dict):
        return
    type_value = value.get("@type", "")
    if isinstance(type_value, list):
        is_jobposting = any(str(item).casefold() == "jobposting" for item in type_value)
    else:
        is_jobposting = str(type_value).casefold() == "jobposting"
    keys = (
        ("title", "Title"),
        ("description", "Description"),
        ("responsibilities", "Responsibilities"),
        ("qualifications", "Qualifications"),
        ("skills", "Skills"),
        ("experienceRequirements", "Experience requirements"),
        ("educationRequirements", "Education requirements"),
        ("employmentType", "Employment type"),
        ("jobBenefits", "Benefits"),
        ("industry", "Industry"),
    )
    if is_jobposting:
        for key, label in keys:
            item = value.get(key)
            if isinstance(item, (str, int, float)) and str(item).strip():
                text = _strip_html_fragment(str(item)) if key == "description" else _normalize_text(str(item))
                if text:
                    output.append(f"{label}:\n{text}")
    for key in ("@graph", "mainEntity", "mainEntityOfPage", "itemListElement"):
        if key in value:
            _flatten_jobposting(value[key], output)


def _json_ld_job_text(blocks: list[str]) -> str:
    found: list[str] = []
    for block in blocks:
        try:
            value = json.loads(block)
        except (ValueError, TypeError):
            continue
        _flatten_jobposting(value, found)
    return _normalize_text("\n\n".join(dict.fromkeys(found)))


def _check_public_https_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme.casefold() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise JobDetailFetchError("Only public HTTPS job listing URLs can be enriched.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise JobDetailFetchError("The public listing URL has an invalid port.") from exc
    if port not in (None, 443):
        raise JobDetailFetchError("Non-standard ports are not allowed for public job listing enrichment.")
    hostname = parsed.hostname.rstrip(".").casefold()
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith((".local", ".internal", ".localhost")):
        raise JobDetailFetchError("Local or internal URLs cannot be fetched as job listings.")
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        ip = None
    if ip is not None:
        if not ip.is_global:
            raise JobDetailFetchError("Private or reserved IP addresses cannot be fetched.")
    else:
        try:
            addresses = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise JobDetailFetchError("The job listing hostname could not be resolved.") from exc
        if not addresses:
            raise JobDetailFetchError("The job listing hostname could not be resolved.")
        for address in addresses:
            try:
                parsed_ip = ipaddress.ip_address(address[4][0])
            except (ValueError, IndexError, TypeError):
                raise JobDetailFetchError("The job listing resolved to an invalid network address.")
            if not parsed_ip.is_global:
                raise JobDetailFetchError("The job listing resolved to a private or reserved network address.")
    # Remove fragments; keep the public path/query because some providers use
    # listing IDs in query strings.
    return parsed._replace(fragment="").geturl()


def fetch_public_job_description(url: str) -> str:
    """Fetch readable public listing text with bounded size, time and redirects."""
    current_url = _check_public_https_url(url)
    timeout = httpx.Timeout(12.0, connect=5.0, read=8.0)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=True) as client:
            for _ in range(MAX_REDIRECTS + 1):
                current_url = _check_public_https_url(current_url)
                with client.stream(
                    "GET",
                    current_url,
                    headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
                ) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location", "").strip()
                        if not location:
                            raise JobDetailFetchError("The job listing redirected without a destination.")
                        current_url = urljoin(current_url, location)
                        continue
                    if response.status_code in {401, 403, 429}:
                        raise JobDetailFetchError(
                            f"The public listing returned HTTP {response.status_code}; CareerMate will not bypass access controls."
                        )
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").casefold()
                    if "html" not in content_type and "text/plain" not in content_type:
                        raise JobDetailFetchError("The linked URL did not return a readable HTML job page.")
                    chunks: list[bytes] = []
                    size = 0
                    for chunk in response.iter_bytes(65536):
                        size += len(chunk)
                        if size > MAX_PAGE_BYTES:
                            raise JobDetailFetchError("The job page is larger than the safe 2 MB read limit.")
                        chunks.append(chunk)
                    encoding = response.encoding or "utf-8"
                    page = b"".join(chunks).decode(encoding, errors="replace")
                    description = _html_to_text(page)
                    if len(description) < 500:
                        raise JobDetailFetchError("The page did not contain enough readable job details to improve the search result.")
                    return description[:MAX_DESCRIPTION_CHARS]
    except JobDetailFetchError:
        raise
    except httpx.HTTPStatusError as exc:
        raise JobDetailFetchError(f"The public job page returned HTTP {exc.response.status_code}.") from exc
    except (httpx.RequestError, OSError, UnicodeError) as exc:
        raise JobDetailFetchError("Could not read the public job listing. The short search description has been retained.") from exc
    raise JobDetailFetchError("The job listing exceeded the redirect limit.")


def enrich_job_record(job: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    """Return a saved job with the most complete text found on its public listing URLs.

    Some job aggregators expose separate source and application links. Try each unique
    public URL safely and prefer the longest usable advert, rather than letting a short
    redirect or a thin application page hide a fuller source listing.
    """
    current = str(job.get("description", "")).strip()
    if not force and len(current) >= 1800:
        return dict(job)

    candidate_urls: list[str] = []
    for value in (job.get("source_url"), job.get("apply_url"), job.get("job_url")):
        url = str(value or "").strip()
        if url and url not in candidate_urls:
            candidate_urls.append(url)
    if not candidate_urls:
        raise JobDetailFetchError("This job source did not provide a public listing URL.")

    best_text = ""
    last_error: JobDetailFetchError | None = None
    minimum_length = max(500, int(len(current) * 1.15))
    for url in candidate_urls[:3]:
        try:
            text = fetch_public_job_description(url)
        except JobDetailFetchError as exc:
            last_error = exc
            continue
        if len(text) > len(best_text):
            best_text = text

    if len(best_text) < minimum_length:
        if last_error and not best_text:
            raise last_error
        raise JobDetailFetchError(
            "The public source/application pages did not provide a fuller description than the existing search result."
        )

    enriched = dict(job)
    enriched.update({
        "description": best_text[:MAX_DESCRIPTION_CHARS],
        "description_source": "original_listing",
        "description_fetch_status": "success",
        "description_fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "description_fetch_message": f"Retrieved fuller public listing text ({len(best_text):,} characters).",
    })
    return enriched
