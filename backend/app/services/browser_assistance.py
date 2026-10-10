"""Visible, user-initiated browser assistance for reviewing application forms.

This module intentionally never clicks a submit button, uploads files, fills
password/OTP fields, or attempts to bypass CAPTCHAs or access controls. Browser
state is transient and held in memory only; application data remains in JSON.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse


BLOCKED_AUTOMATION_DOMAINS = ("linkedin.com", "indeed.com", "glassdoor.com")
SUPPORTED_INPUT_TYPES = {"text", "email", "tel", "url", "search", "textarea", "date", "number"}
SENSITIVE_FIELD_PATTERN = re.compile(
    r"\b(?:password|passcode|one[-\s]?time code|otp|captcha|verification code|security code|"
    r"social security(?: number)?|ssn|national (?:id|identification)(?: number)?|"
    r"passport(?: number)?|credit card|bank account|date of birth|birth date|birthdate|birthday|dob|"
    r"personal identity number|personnummer|tax (?:id|identification)(?: number)?|"
    r"driver(?:['’]?s)? license(?: number)?|residence permit (?:number|id)|"
    r"immigration (?:id|number)|work permit (?:number|id)|"
    r"cc-(?:number|exp|csc|name))\b",
    re.IGNORECASE,
)
MAX_FORM_FIELDS = 100


def _is_sensitive_field(value: str) -> bool:
    return bool(SENSITIVE_FIELD_PATTERN.search(value))


class BrowserAssistanceError(Exception):
    """A safe and user-facing browser-assistance failure."""


@dataclass
class BrowserField:
    field_id: str
    label: str
    kind: str
    required: bool
    placeholder: str = ""
    autocomplete: str = ""
    suggested_key: str = ""


@dataclass
class ActiveBrowserSession:
    playwright: Any
    browser: Any
    context: Any
    page: Any
    application_id: str
    fields: dict[str, BrowserField] = field(default_factory=dict)


_active_session: ActiveBrowserSession | None = None
_session_lock = asyncio.Lock()


def _hostname_is_public(hostname: str, port: int) -> bool:
    """Resolve hostname and reject private, reserved, loopback and link-local targets."""
    try:
        records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError:
        return False
    addresses: set[str] = set()
    for record in records:
        try:
            addresses.add(record[4][0].split("%", 1)[0])
        except (IndexError, TypeError):
            return False
    if not addresses:
        return False
    try:
        return all(ipaddress.ip_address(address).is_global for address in addresses)
    except ValueError:
        return False


def validate_public_https_url(value: str) -> str:
    """Validate a public HTTPS URL before Playwright is allowed to navigate to it."""
    parsed = urlparse(value.strip())
    if parsed.scheme.casefold() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise BrowserAssistanceError("Browser assistance only opens public HTTPS application links.")
    host = parsed.hostname.casefold().rstrip(".")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise BrowserAssistanceError("Local or internal network destinations are blocked for safety.")
    if any(host == domain or host.endswith("." + domain) for domain in BLOCKED_AUTOMATION_DOMAINS):
        raise BrowserAssistanceError(
            "CareerMate does not automate LinkedIn, Indeed, or Glassdoor. Open the employer's official career page directly instead."
        )
    try:
        port = parsed.port or 443
    except ValueError as exc:
        raise BrowserAssistanceError("Invalid URL port.") from exc
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            raise BrowserAssistanceError("Private or reserved IP addresses are blocked for safety.")
    except ValueError:
        if not _hostname_is_public(host, port):
            raise BrowserAssistanceError("CareerMate could not verify that this destination is publicly routable.")
    return value.strip()


def suggest_profile_key(label: str, kind: str = "text", autocomplete: str = "") -> str:
    """Suggest only low-risk mappings; the user still reviews every value."""
    text = re.sub(r"[_-]+", " ", f"{label} {autocomplete}").casefold()
    if _is_sensitive_field(text):
        return ""
    if re.search(r"\b(first name|given name|firstname)\b", text):
        return "personal.first_name"
    if re.search(r"\b(last name|family name|surname|lastname)\b", text):
        return "personal.last_name"
    if re.search(r"\b(email|e mail|email address)\b", text) or autocomplete == "email":
        return "personal.email"
    if re.search(r"\b(phone|telephone|mobile|tel)\b", text) or autocomplete == "tel":
        return "personal.phone"
    if re.search(r"\b(full name|your name|name)\b", text) or autocomplete == "name":
        return "personal.name"
    if re.search(r"\b(linkedin)\b", text):
        return "personal.linkedin"
    if re.search(r"\b(github)\b", text):
        return "personal.github"
    if re.search(r"\b(portfolio|personal website|website url|website)\b", text):
        return "personal.portfolio"
    if re.search(r"\b(city|location|address|where are you based)\b", text):
        return "personal.location"
    if re.search(r"\b(cover letter|motivation letter|letter of motivation)\b", text):
        return "cover_letter"
    if re.search(r"\b(why.*(role|company|job)|application question|additional information)\b", text):
        return "latest_answer"
    if kind == "textarea" and re.search(r"\b(summary|about you|professional summary)\b", text):
        return "summary"
    return ""


def _field_from_raw(raw: dict[str, Any]) -> BrowserField | None:
    kind = str(raw.get("kind", "text")).casefold()
    label = str(raw.get("label", "Field")).strip()[:240]
    placeholder = str(raw.get("placeholder", "")).strip()[:240]
    autocomplete = str(raw.get("autocomplete", "")).strip()[:100]
    combined = f"{label} {placeholder} {autocomplete}".casefold()
    if kind not in SUPPORTED_INPUT_TYPES:
        return None
    if _is_sensitive_field(combined):
        return None
    field_id = str(raw.get("field_id", ""))
    if not re.fullmatch(r"cm-field-\d{1,3}", field_id):
        return None
    return BrowserField(
        field_id=field_id,
        label=label or "Unlabelled field",
        kind=kind,
        required=bool(raw.get("required")),
        placeholder=placeholder,
        autocomplete=autocomplete,
        suggested_key=suggest_profile_key(label, kind, autocomplete),
    )


async def _route_public_requests(route: Any) -> None:
    """Block navigation/subresources outside public HTTPS origins, including redirects."""
    request_url = route.request.url
    try:
        await asyncio.to_thread(validate_public_https_url, request_url)
        await route.continue_()
    except BrowserAssistanceError:
        await route.abort()


async def _close_active_session_unlocked() -> None:
    global _active_session
    session, _active_session = _active_session, None
    if session is None:
        return
    for resource in (session.context, session.browser):
        try:
            await resource.close()
        except Exception:
            pass
    try:
        await session.playwright.stop()
    except Exception:
        pass


async def scan_current_form() -> dict[str, Any]:
    """Refresh the visible page's supported, non-sensitive form-field inventory."""
    global _active_session
    async with _session_lock:
        session = _active_session
        if session is None or session.page.is_closed():
            raise BrowserAssistanceError("No active browser session. Open an application page first.")
        try:
            await asyncio.to_thread(validate_public_https_url, session.page.url)
            raw_fields = await session.page.evaluate(
                """() => {
                  const allowed = new Set(['text','email','tel','url','search','date','number','textarea']);
                  const elements = Array.from(document.querySelectorAll('input, textarea'));
                  const result = [];
                  for (const el of elements) {
                    const type = el.tagName.toLowerCase() === 'textarea' ? 'textarea' : (el.type || 'text').toLowerCase();
                    if (!allowed.has(type) || el.disabled || el.readOnly || el.hidden) continue;
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    if (rect.width === 0 || rect.height === 0 || style.visibility === 'hidden' || style.display === 'none') continue;
                    const labelParts = [];
                    if (el.labels) for (const label of Array.from(el.labels)) labelParts.push(label.innerText || label.textContent || '');
                    const labelledBy = (el.getAttribute('aria-labelledby') || '').split(/\\s+/).filter(Boolean);
                    for (const id of labelledBy) { const item = document.getElementById(id); if (item) labelParts.push(item.innerText || item.textContent || ''); }
                    const ariaLabel = el.getAttribute('aria-label') || '';
                    const placeholder = el.getAttribute('placeholder') || '';
                    const name = el.getAttribute('name') || '';
                    const id = el.getAttribute('id') || '';
                    const autocomplete = el.getAttribute('autocomplete') || '';
                    const sensitiveText = [...labelParts, ariaLabel, placeholder, name, id, autocomplete].join(' ');
                    const sensitive = /password|passcode|one[- ]time code|\\botp\\b|captcha|verification code|security code|social security|\\bssn\\b|passport|credit card|bank account|date of birth|birth date|birthdate|birthday|\bdob\b|personnummer|personal identity number|tax (?:id|identification)|driver(?:['’]?s)? license|residence permit (?:number|id)|immigration (?:id|number)|work permit (?:number|id)/i.test(sensitiveText);
                    if (sensitive) continue;
                    const label = [labelParts.join(' '), ariaLabel, placeholder, name, id].find(v => String(v || '').trim()) || `Field ${result.length + 1}`;
                    const fieldId = `cm-field-${result.length}`;
                    el.setAttribute('data-careermate-field-id', fieldId);
                    result.push({ field_id: fieldId, label: String(label).replace(/\\s+/g, ' ').trim().slice(0,240), kind: type, required: !!el.required || el.getAttribute('aria-required') === 'true', placeholder, autocomplete });
                    if (result.length >= 100) break;
                  }
                  return result;
                }"""
            )
        except BrowserAssistanceError:
            raise
        except Exception as exc:
            raise BrowserAssistanceError("Could not inspect this page. Try refreshing the fields after the form has loaded.") from exc

        fields: dict[str, BrowserField] = {}
        for item in raw_fields if isinstance(raw_fields, list) else []:
            if isinstance(item, dict):
                parsed = _field_from_raw(item)
                if parsed is not None:
                    fields[parsed.field_id] = parsed
        session.fields = fields
        return {
            "success": True,
            "application_id": session.application_id,
            "url": session.page.url,
            "title": (await session.page.title())[:300],
            "field_count": len(fields),
            "fields": [item.__dict__ for item in fields.values()],
            "message": "Fields scanned. Review each proposed value before filling; CareerMate will not submit the form.",
        }


async def open_application_page(application_id: str, url: str) -> dict[str, Any]:
    """Open a visible Chromium window for a user-selected tracked application."""
    global _active_session
    safe_url = await asyncio.to_thread(validate_public_https_url, url)
    async with _session_lock:
        await _close_active_session_unlocked()
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise BrowserAssistanceError(
                "Browser assistance requires Playwright. Install backend dependencies and run `python -m playwright install chromium`."
            ) from exc

        manager = None
        browser = None
        context = None
        try:
            manager = await async_playwright().start()
            browser = await manager.chromium.launch(headless=False)
            context = await browser.new_context(accept_downloads=False, service_workers="block")
            await context.route("**/*", _route_public_requests)
            page = await context.new_page()
            await page.goto(safe_url, wait_until="domcontentloaded", timeout=45000)
            _active_session = ActiveBrowserSession(
                playwright=manager, browser=browser, context=context, page=page, application_id=application_id,
            )
        except Exception as exc:
            for resource in (context, browser):
                if resource is not None:
                    try:
                        await resource.close()
                    except Exception:
                        pass
            if manager is not None:
                try:
                    await manager.stop()
                except Exception:
                    pass
            if isinstance(exc, BrowserAssistanceError):
                raise
            raise BrowserAssistanceError(
                "Could not open the visible browser. Install Chromium with `python -m playwright install chromium` and check the application link."
            ) from exc

    return await scan_current_form()


async def fill_reviewed_fields(application_id: str, requested_fields: list[dict[str, str]]) -> dict[str, Any]:
    """Fill only explicitly reviewed supported text fields; never submit or upload."""
    if not requested_fields:
        raise BrowserAssistanceError("Select at least one field with a reviewed value before filling.")
    if len(requested_fields) > 80:
        raise BrowserAssistanceError("Fill no more than 80 fields in one action.")

    # Refresh selectors first so a page navigation can't reuse stale field IDs.
    scan = await scan_current_form()
    async with _session_lock:
        session = _active_session
        if session is None or session.application_id != application_id:
            raise BrowserAssistanceError("The active browser belongs to a different application. Reopen the correct application.")
        current_fields = session.fields
        filled: list[str] = []
        skipped: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in requested_fields:
            field_id = str(item.get("field_id", ""))
            value = str(item.get("value", ""))
            if field_id in seen:
                skipped.append({"field_id": field_id, "reason": "Duplicate field selection."})
                continue
            seen.add(field_id)
            field = current_fields.get(field_id)
            if field is None:
                skipped.append({"field_id": field_id, "reason": "The field no longer exists on the current page. Scan the form again."})
                continue
            if not value.strip():
                skipped.append({"field_id": field_id, "reason": "Blank values are not filled."})
                continue
            if len(value) > 12000:
                skipped.append({"field_id": field_id, "reason": "Value exceeds the 12,000 character limit."})
                continue
            try:
                selector = f'[data-careermate-field-id="{field_id}"]'
                locator = session.page.locator(selector)
                if await locator.count() != 1 or not await locator.is_editable():
                    skipped.append({"field_id": field_id, "reason": "Field is no longer uniquely editable."})
                    continue
                await locator.fill(value, timeout=5000)
                filled.append(field_id)
            except Exception:
                skipped.append({"field_id": field_id, "reason": "The field could not be filled. Try refreshing the field list."})

        return {
            "success": True,
            "filled_field_ids": filled,
            "filled_count": len(filled),
            "skipped": skipped,
            "message": "Selected fields were filled. Review the live employer form; CareerMate did not submit it.",
            "url": session.page.url,
            "scanned_field_count": scan.get("field_count", 0),
        }


async def get_browser_session_status() -> dict[str, Any]:
    session = _active_session
    if session is None or session.page.is_closed():
        return {"active": False, "application_id": None, "url": "", "title": ""}
    try:
        return {
            "active": True,
            "application_id": session.application_id,
            "url": session.page.url,
            "title": (await session.page.title())[:300],
        }
    except Exception:
        return {"active": False, "application_id": None, "url": "", "title": ""}


async def close_browser_session() -> dict[str, Any]:
    async with _session_lock:
        await _close_active_session_unlocked()
    return {"success": True, "active": False, "message": "Browser session closed. No form data was saved by the browser assistant."}
