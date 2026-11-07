"""Health checks for configured employer career portals.

Only known ATS API hosts are contacted. Board identifiers are validated by
job_search.validate_source_config before this service uses them. Credentials
are read from the local environment and are never returned or persisted.
"""
from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.services.job_search import load_source_config, SUPPORTED_ATS

BASE_DIR = Path(__file__).resolve().parents[3]
HEALTH_PATH = BASE_DIR / "data" / "portal_health.json"
MAX_CHECKED_PORTALS = 40
MAX_WORKERS = 6
TIMEOUT = httpx.Timeout(9.0, connect=4.0)
HEADERS = {
    "accept": "application/json, application/xml, text/xml;q=0.9, */*;q=0.8",
    "user-agent": "CareerMate-local/3.0 (+local career portal health check)",
}

PROVIDER_LABELS = {
    "greenhouse": "Greenhouse",
    "lever": "Lever",
    "teamtailor": "Teamtailor",
    "ashby": "Ashby",
    "smartrecruiters": "SmartRecruiters",
    "workable": "Workable",
    "recruitee": "Recruitee",
    "breezy": "Breezy HR",
    "personio": "Personio",
    "workday": "Workday",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _identifier(provider: str, board: dict[str, Any]) -> str:
    if provider == "greenhouse":
        return str(board.get("board_token", "")).strip()
    if provider == "lever":
        return str(board.get("site", "")).strip()
    if provider == "teamtailor":
        return str(board.get("company", "")).strip()
    return str(board.get("slug", "")).strip()


def _portal_id(provider: str, identifier: str) -> str:
    return f"{provider}:{identifier.casefold()}"


def _domain_label(provider: str, identifier: str, board: dict[str, Any]) -> str:
    if provider == "greenhouse":
        return f"job-boards.greenhouse.io/{identifier}"
    if provider == "lever":
        return f"jobs.lever.co/{identifier}"
    if provider == "teamtailor":
        return f"Teamtailor · {board.get('region', 'eu').upper()} region"
    if provider == "ashby":
        return f"jobs.ashbyhq.com/{identifier}"
    if provider == "smartrecruiters":
        return f"jobs.smartrecruiters.com/{identifier}"
    if provider == "workable":
        return f"apply.workable.com/{identifier}"
    if provider == "recruitee":
        return f"{identifier}.recruitee.com"
    if provider == "breezy":
        return f"{identifier}.breezy.hr"
    if provider == "personio":
        return f"{identifier}.jobs.personio.de"
    if provider == "workday":
        raw = identifier if "://" in identifier else f"https://{identifier}"
        parsed = urlparse(raw)
        return f"{parsed.netloc}{parsed.path}".rstrip("/") or "Workday careers"
    return identifier


def _base_item(provider: str, board: dict[str, Any]) -> dict[str, Any]:
    identifier = _identifier(provider, board)
    company = str(board.get("company") or identifier or PROVIDER_LABELS[provider]).strip()
    enabled = board.get("enabled") is True
    return {
        "id": _portal_id(provider, identifier),
        "provider": provider,
        "provider_label": PROVIDER_LABELS[provider],
        "company": company,
        "identifier": identifier,
        "domain": _domain_label(provider, identifier, board),
        "country": str(board.get("country", "")).strip(),
        "career_url": str(board.get("career_url", "")).strip(),
        "jobs_url": str(board.get("jobs_url", "")).strip(),
        "notes": str(board.get("notes", "")).strip(),
        "enabled": enabled,
        "status": "not_checked" if enabled else "paused",
        "job_count": None,
        "checked_at": None,
        "duration_ms": None,
        "message": "Not checked yet." if enabled else "Paused. This portal is excluded from searches.",
    }


def _request_json(url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    response = httpx.get(url, params=params, headers=headers or HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def _probe(provider: str, board: dict[str, Any]) -> int | None:
    """Make one bounded read-only request and return a visible job count if known."""
    identifier = _identifier(provider, board)

    if provider == "greenhouse":
        payload = _request_json(
            f"https://boards-api.greenhouse.io/v1/boards/{quote(identifier, safe='')}/jobs",
            params={"content": "false"},
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ValueError("Unexpected Greenhouse response format")
        return len(payload["jobs"])

    if provider == "lever":
        region = str(board.get("region", "global")).casefold()
        api_root = "https://api.eu.lever.co/v0/postings" if region == "eu" else "https://api.lever.co/v0/postings"
        payload = _request_json(
            f"{api_root}/{quote(identifier, safe='')}",
            params={"mode": "json", "skip": 0, "limit": 1},
        )
        if not isinstance(payload, list):
            raise ValueError("Unexpected Lever response format")
        return 1 if payload else 0

    if provider == "teamtailor":
        key_name = str(board.get("api_key_env", "")).strip()
        api_key = os.getenv(key_name, "")
        if not api_key:
            raise PermissionError(f"API key variable {key_name or '(not set)'} is not configured")
        region = str(board.get("region", "eu")).casefold()
        roots = {
            "eu": "https://api.teamtailor.com/v1/jobs",
            "na": "https://api.na.teamtailor.com/v1/jobs",
            "apac": "https://api.au.teamtailor.com/v1/jobs",
        }
        headers = {
            **HEADERS,
            "accept": "application/vnd.api+json",
            "authorization": f"Token token={api_key}",
            "x-api-version": datetime.now(timezone.utc).strftime("%Y%m%d"),
        }
        payload = _request_json(roots[region], params={"page[size]": 1, "page[number]": 1, "filter[status]": "published", "filter[feed]": "public"}, headers=headers)
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError("Unexpected Teamtailor response format")
        return 1 if payload["data"] else 0

    if provider == "ashby":
        payload = _request_json(f"https://api.ashbyhq.com/posting-api/job-board/{quote(identifier, safe='')}", params={"includeCompensation": "false"})
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ValueError("Unexpected Ashby response format")
        return len(payload["jobs"])

    if provider == "smartrecruiters":
        payload = _request_json(f"https://api.smartrecruiters.com/v1/companies/{quote(identifier, safe='')}/postings", params={"limit": 1, "offset": 0})
        if not isinstance(payload, dict) or not isinstance(payload.get("content"), list):
            raise ValueError("Unexpected SmartRecruiters response format")
        total = payload.get("totalFound")
        return int(total) if isinstance(total, (int, float)) else (1 if payload["content"] else 0)

    if provider == "workable":
        payload = _request_json(f"https://apply.workable.com/api/v1/widget/accounts/{quote(identifier, safe='')}", params={"details": "false"})
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ValueError("Unexpected Workable response format")
        return len(payload["jobs"])

    if provider == "recruitee":
        payload = _request_json(f"https://{identifier}.recruitee.com/api/offers/")
        if not isinstance(payload, dict) or not isinstance(payload.get("offers"), list):
            raise ValueError("Unexpected Recruitee response format")
        return len(payload["offers"])

    if provider == "breezy":
        payload = _request_json(f"https://{identifier}.breezy.hr/json")
        if not isinstance(payload, list):
            raise ValueError("Unexpected Breezy response format")
        return len(payload)

    if provider == "personio":
        response = httpx.get(f"https://{identifier}.jobs.personio.de/xml", params={"language": "en"}, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        return len(root.findall(".//position"))

    if provider == "workday":
        raw = identifier if "://" in identifier else f"https://{identifier}"
        parsed = urlparse(raw)
        match = re.fullmatch(r"(?P<tenant>[a-z0-9-]+)\.(?P<cluster>wd\d+)\.myworkdayjobs\.com", parsed.netloc, re.I)
        site = parsed.path.strip("/").split("/")[-1] if parsed.path.strip("/") else ""
        if not match or not site:
            raise ValueError("Invalid Workday careers URL")
        tenant = match.group("tenant")
        endpoint = f"https://{parsed.netloc}/wday/cxs/{tenant}/{site}/jobs"
        response = httpx.post(endpoint, json={"limit": 1, "offset": 0, "searchText": "", "appliedFacets": {}}, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("jobPostings"), list):
            raise ValueError("Unexpected Workday response format")
        total = payload.get("total") or payload.get("totalCount")
        return int(total) if isinstance(total, (int, float)) else (1 if payload["jobPostings"] else 0)

    raise ValueError("Unsupported employer portal")


def _check_one(provider: str, board: dict[str, Any]) -> dict[str, Any]:
    item = _base_item(provider, board)
    if not item["enabled"]:
        return item
    if not item["identifier"]:
        item.update(status="needs_setup", message="A public board identifier is required.")
        return item
    if provider == "teamtailor" and not os.getenv(str(board.get("api_key_env", "")).strip(), ""):
        item.update(status="needs_setup", checked_at=_now(), message=f"API key variable {board.get('api_key_env') or '(not set)'} is not configured.")
        return item

    started = time.perf_counter()
    try:
        count = _probe(provider, board)
        status = "empty" if count == 0 else "live"
        message = "Responding · no published jobs found." if status == "empty" else (f"Responding · {count} job(s) available." if count is not None else "Responding · jobs endpoint is available.")
        item.update(status=status, job_count=count, checked_at=_now(), duration_ms=round((time.perf_counter() - started) * 1000), message=message)
    except PermissionError as exc:
        item.update(status="needs_setup", checked_at=_now(), duration_ms=round((time.perf_counter() - started) * 1000), message=str(exc))
    except httpx.HTTPStatusError as exc:
        item.update(status="broken", checked_at=_now(), duration_ms=round((time.perf_counter() - started) * 1000), message=f"The portal returned HTTP {exc.response.status_code}.")
    except httpx.TimeoutException:
        item.update(status="broken", checked_at=_now(), duration_ms=round((time.perf_counter() - started) * 1000), message="The portal did not respond before the 9-second timeout.")
    except httpx.RequestError:
        item.update(status="broken", checked_at=_now(), duration_ms=round((time.perf_counter() - started) * 1000), message="The portal could not be reached. Check the network or board URL.")
    except (ValueError, ET.ParseError, KeyError, TypeError):
        item.update(status="broken", checked_at=_now(), duration_ms=round((time.perf_counter() - started) * 1000), message="The portal responded with an unexpected data format.")
    return item


def _read_saved() -> dict[str, Any]:
    if not HEALTH_PATH.exists():
        return {"checked_at": None, "items": {}}
    try:
        data = json.loads(HEALTH_PATH.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) and isinstance(data.get("items"), dict) else {"checked_at": None, "items": {}}
    except (OSError, json.JSONDecodeError):
        return {"checked_at": None, "items": {}}


def _summary(items: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(items),
        "enabled": sum(1 for item in items if item.get("enabled")),
        "paused": sum(1 for item in items if item.get("status") == "paused"),
        "live": sum(1 for item in items if item.get("status") == "live"),
        "empty": sum(1 for item in items if item.get("status") == "empty"),
        "broken": sum(1 for item in items if item.get("status") == "broken"),
        "needs_setup": sum(1 for item in items if item.get("status") == "needs_setup"),
        "not_checked": sum(1 for item in items if item.get("status") == "not_checked"),
    }


def get_portal_health() -> dict[str, Any]:
    """Return configured portals with the latest persisted health observation."""
    config = load_source_config()
    saved = _read_saved()
    cached_items = saved.get("items", {})
    items: list[dict[str, Any]] = []
    for provider in SUPPORTED_ATS:
        for board in config.get(provider, []):
            identifier = _identifier(provider, board)
            if not identifier:
                continue
            item = _base_item(provider, board)
            cached = cached_items.get(item["id"])
            if isinstance(cached, dict) and cached.get("checked_at"):
                for key in ("status", "job_count", "checked_at", "duration_ms", "message"):
                    if key in cached and item["enabled"]:
                        item[key] = cached[key]
            items.append(item)
    items.sort(key=lambda item: (not item["enabled"], str(item["company"]).casefold()))
    return {"success": True, "checked_at": saved.get("checked_at"), "summary": _summary(items), "items": items}


def check_portal_health() -> dict[str, Any]:
    """Probe enabled configured portals in parallel and persist safe results."""
    config = load_source_config()
    board_entries: list[tuple[str, dict[str, Any]]] = []
    for provider in SUPPORTED_ATS:
        for board in config.get(provider, []):
            if _identifier(provider, board):
                board_entries.append((provider, board))

    enabled = [(provider, board) for provider, board in board_entries if board.get("enabled") is True]
    checkable = enabled[:MAX_CHECKED_PORTALS]
    skipped = {str(_base_item(provider, board)["id"]) for provider, board in enabled[MAX_CHECKED_PORTALS:]}
    results: dict[str, dict[str, Any]] = {}

    for provider, board in board_entries:
        base = _base_item(provider, board)
        if not base["enabled"]:
            results[base["id"]] = base
        elif base["id"] in skipped:
            base.update(status="not_checked", message=f"Not checked in this run; the per-run limit is {MAX_CHECKED_PORTALS} enabled portals.")
            results[base["id"]] = base

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(_check_one, provider, board): (provider, board) for provider, board in checkable}
        for future in as_completed(futures):
            provider, board = futures[future]
            try:
                item = future.result()
            except Exception:  # fail-soft: one unexpected adapter error must not cancel the directory check
                item = _base_item(provider, board)
                item.update(status="broken", checked_at=_now(), message="Unexpected error while checking this portal.")
            results[item["id"]] = item

    items = sorted(results.values(), key=lambda item: (not item["enabled"], str(item["company"]).casefold()))
    checked_at = _now()
    HEALTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = HEALTH_PATH.with_suffix(".json.tmp")
    try:
        temporary.write_text(json.dumps({"checked_at": checked_at, "items": {item["id"]: item for item in items}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(HEALTH_PATH)
    finally:
        temporary.unlink(missing_ok=True)

    return {"success": True, "checked_at": checked_at, "summary": _summary(items), "items": items, "check_limit": MAX_CHECKED_PORTALS}
