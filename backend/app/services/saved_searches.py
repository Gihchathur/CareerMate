"""Local JSON storage for saved job searches and notification snapshots."""
from __future__ import annotations
import json, uuid
from pathlib import Path
from datetime import datetime, timezone
BASE=Path(__file__).resolve().parents[3]
PATH=BASE/"data"/"saved_searches.json"
ALERTS=BASE/"data"/"job_alert_snapshots.json"
HISTORY=BASE/"data"/"job_alert_history.json"
def _read(path, default):
    try:
        value=json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value,type(default)) else default
    except (OSError,json.JSONDecodeError): return default
def _write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".tmp"); tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8"); tmp.replace(path)
def list_searches(): return _read(PATH,[])
def save_search(payload):
    items=list_searches()
    item={**payload,"id":str(uuid.uuid4()),"created_at":datetime.now(timezone.utc).isoformat()}
    items.insert(0,item); _write(PATH,items[:100]); return item
def delete_search(search_id):
    items=list_searches(); kept=[x for x in items if x.get("id")!=search_id]
    _write(PATH,kept); return len(items)!=len(kept)
def scan_alerts(search_id, jobs):
    snapshots=_read(ALERTS,{})
    previous=set(snapshots.get(search_id,[]))
    current=[str(x.get("id","")) for x in jobs if x.get("id")]
    new=[x for x in jobs if str(x.get("id","")) not in previous]
    snapshots[search_id]=current; _write(ALERTS,snapshots)
    return {"new_count":len(new),"new_jobs":new}


def list_alert_history(limit=100):
    return _read(HISTORY, [])[:max(1,min(int(limit),500))]

def record_alerts(search_id, search_name, new_jobs):
    if not new_jobs: return
    history=_read(HISTORY, [])
    for job in new_jobs:
        history.insert(0, {
            "id": str(uuid.uuid4()),
            "search_id": search_id,
            "search_name": search_name,
            "job_id": job.get("id",""),
            "title": job.get("title",""),
            "company": job.get("company",""),
            "location": job.get("location",""),
            "url": job.get("source_url") or job.get("apply_url",""),
            "found_at": datetime.now(timezone.utc).isoformat(),
            "read": False,
        })
    _write(HISTORY, history[:500])

def mark_alert_read(alert_id):
    history=_read(HISTORY, [])
    changed=False
    for item in history:
        if item.get("id")==alert_id:
            item["read"]=True; changed=True
    _write(HISTORY, history)
    return changed
