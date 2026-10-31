"""Public employer ATS board adapters. Configure board slugs/tenant URLs explicitly."""
from __future__ import annotations
from datetime import datetime, timezone
from xml.etree import ElementTree as ET
from typing import Any
from pathlib import Path
import re
import httpx
import hashlib, json, time
from app.models.job import JobPosting
from app.services.job_sources.base import clean_html, classify_work_mode, get_with_retries, infer_country, make_job_id, safe_http_url, text_value, JobSourceError

UA = {"User-Agent": "CareerMate/0.9 (local job discovery; public careers feeds)"}
CACHE_DIR = Path(__file__).resolve().parents[4] / "data" / "source_cache" / "public_ats"
CACHE_TTL_SECONDS = 900

def _get(url: str, params=None):
    try:
        return get_with_retries(url, params=params, headers=UA)
    except Exception as exc:
        raise JobSourceError(f"Public board request failed: {exc}") from exc

def _posting(source: str, sid: Any, title: Any, company: str, location: Any, description: Any, published: Any, url: Any, country: str="") -> JobPosting:
    loc=text_value(location) or "Location not specified"
    return JobPosting(id=make_job_id(source,str(sid)),source=source,source_id=str(sid),title=text_value(title) or "Untitled role",
        company=company or "Company not specified",location=loc,description=clean_html(text_value(description)),
        published_at=text_value(published),source_url=safe_http_url(url),apply_url=safe_http_url(url),
        country=infer_country(loc,country),work_mode=classify_work_mode(loc,description))

def _fetch_public_board_uncached(source: str, board: dict[str,Any]) -> list[JobPosting]:
    slug=str(board.get("slug","")).strip()
    company=str(board.get("company","")).strip() or slug
    country=str(board.get("country","")).strip()
    if not slug: raise JobSourceError("Board slug is required.")
    jobs=[]
    if source == "ashby":
        data=_get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}",{"includeCompensation":"true"}).json()
        for x in data.get("jobs",[]):
            if x.get("isListed") is False: continue
            jobs.append(_posting(source,x.get("id"),x.get("title"),company,x.get("location"),x.get("descriptionPlain") or x.get("description"),x.get("publishedAt"),x.get("jobUrl") or x.get("applyUrl"),country))
    elif source == "smartrecruiters":
        for offset in range(0,500,100):
            data=_get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",{"limit":100,"offset":offset}).json()
            rows=data.get("content",[])
            for x in rows:
                loc=x.get("location",{})
                label=loc.get("fullLocation") or ", ".join(v for v in [loc.get("city"),loc.get("region"),loc.get("country")] if v)
                detail=""
                try:
                    d=_get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{x.get('id')}").json()
                    detail=" ".join(str(v.get("text","")) for v in d.get("jobAd",{}).get("sections",{}).values() if isinstance(v,dict))
                except Exception: pass
                jobs.append(_posting(source,x.get("id"),x.get("name"),company,label,detail,x.get("releasedDate"),x.get("ref") or f"https://jobs.smartrecruiters.com/{slug}/{x.get('id')}",country))
            if len(rows)<100: break
    elif source == "workable":
        data=_get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}",{"details":"true"}).json()
        for x in data.get("jobs",[]):
            loc=", ".join(v for v in [x.get("city"),x.get("state"),x.get("country")] if v) or text_value(x.get("locations"))
            jobs.append(_posting(source,x.get("shortcode"),x.get("title"),company,loc,x.get("description"),x.get("published_on"),x.get("application_url") or x.get("url"),country))
    elif source == "recruitee":
        data=_get(f"https://{slug}.recruitee.com/api/offers/").json()
        for x in data.get("offers",[]):
            loc=", ".join(v for v in [x.get("city"),x.get("country_code")] if v) or text_value(x.get("location"))
            desc=" ".join(str(x.get(k,"")) for k in ("description","requirements"))
            jobs.append(_posting(source,x.get("id"),x.get("title"),company,loc,desc,x.get("published_at"),x.get("careers_url") or x.get("careers_apply_url"),country))
    elif source == "breezy":
        data=_get(f"https://{slug}.breezy.hr/json").json()
        for x in data if isinstance(data,list) else []:
            loc=x.get("location",{})
            label=", ".join(v for v in [loc.get("city"),loc.get("state"),loc.get("country")] if v) or ("Remote" if loc.get("is_remote") else "")
            jobs.append(_posting(source,x.get("id"),x.get("name"),company,label,"",x.get("published_date"),x.get("url"),country))
    elif source == "workday":
        from urllib.parse import urlparse
        board_url = str(board.get("slug", "")).strip()
        parsed = urlparse(board_url if "://" in board_url else "https://" + board_url)
        match = re.match(r"^(?P<tenant>[a-z0-9-]+)\.(?P<cluster>wd\d+)\.myworkdayjobs\.com$", parsed.netloc, re.I)
        site = parsed.path.strip("/").split("/")[-1] if parsed.path.strip("/") else ""
        if not match or not site:
            raise JobSourceError("Workday board slug must be the full careers URL, including tenant, wd cluster and site path.")
        tenant, cluster = match.group("tenant"), match.group("cluster")
        endpoint = f"https://{parsed.netloc}/wday/cxs/{tenant}/{site}/jobs"
        payload = {"limit": 20, "offset": 0, "searchText": "", "appliedFacets": {}}
        for offset in range(0, 400, 20):
            payload["offset"] = offset
            try:
                response = httpx.post(endpoint, json=payload, headers=UA, timeout=20.0)
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                raise JobSourceError(f"Workday board request failed: {exc}") from exc
            rows = data.get("jobPostings", [])
            for x in rows:
                ext = str(x.get("externalPath", ""))
                detail = ""
                if ext:
                    try:
                        d = _get(f"https://{parsed.netloc}/wday/cxs/{tenant}/{site}{ext}").json()
                        detail = d.get("jobPostingInfo", {}).get("jobDescription", "")
                    except Exception: pass
                url = f"https://{parsed.netloc}/{site}{ext}" if ext else board_url
                jobs.append(_posting(source, x.get("jobReqId") or ext, x.get("title"), company, x.get("locationsText"), detail, x.get("postedOn"), url, country))
            if len(rows) < 20: break
    elif source == "personio":
        response=_get(f"https://{slug}.jobs.personio.de/xml",{"language":"en"})
        try: root=ET.fromstring(response.text)
        except ET.ParseError as exc: raise JobSourceError("Personio returned invalid XML.") from exc
        for x in root.findall(".//position"):
            ident=x.findtext("id") or x.findtext("name") or slug
            title=x.findtext("name") or "Untitled role"
            loc=x.findtext("office") or country
            sections=[]
            for desc in x.findall(".//jobDescription"):
                sections.append(desc.findtext("value") or "")
            url=f"https://{slug}.jobs.personio.de/job/{ident}"
            jobs.append(_posting(source,ident,title,company,loc," ".join(sections),x.findtext("createdAt"),url,country))
    else:
        raise JobSourceError(f"Unsupported public ATS source: {source}")
    return jobs


def fetch_public_board(source: str, board: dict[str, Any]) -> list[JobPosting]:
    """Read a 15-minute local cache before requesting the employer's public board."""
    cache_key = hashlib.sha256(json.dumps({"source": source, "board": board}, sort_keys=True).encode()).hexdigest()
    cache_path = CACHE_DIR / f"{source}-{cache_key}.json"
    try:
        if cache_path.is_file() and time.time() - cache_path.stat().st_mtime < CACHE_TTL_SECONDS:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return [JobPosting.model_validate(item) for item in payload]
    except (OSError, ValueError, TypeError):
        pass
    jobs = _fetch_public_board_uncached(source, board)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_suffix(".tmp")
        temporary.write_text(json.dumps([job.model_dump() for job in jobs], ensure_ascii=False), encoding="utf-8")
        temporary.replace(cache_path)
    except OSError:
        # Cache failure must not discard successful live results.
        pass
    return jobs
