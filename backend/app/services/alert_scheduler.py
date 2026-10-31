"""Optional in-process scheduler for local saved-search alerts."""
from __future__ import annotations
import logging
try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:  # Optional until backend dependencies are installed.
    BackgroundScheduler = None
from app.services.saved_searches import list_searches, scan_alerts, record_alerts
from app.services.job_discovery import search_multiple_roles
logger=logging.getLogger(__name__)
_scheduler=None

def _run_search(item):
    try:
        result=search_multiple_roles(roles=item["roles"],country=item.get("country","Sweden"),
            city=item.get("city",""),work_mode=item.get("work_mode","any"),
            sources=item.get("sources") or None,limit=40,offset=0)
        jobs=[x.model_dump() for x in result.get("jobs",[])]
        delta=scan_alerts(item["id"],jobs)
        record_alerts(item["id"],item.get("name","Saved search"),delta["new_jobs"])
        logger.info("Saved search %s found %s new jobs",item.get("name"),delta["new_count"])
    except Exception:
        logger.exception("Scheduled CareerMate search failed: %s",item.get("name"))

def refresh_schedules():
    if _scheduler is None: return
    for job in _scheduler.get_jobs(): _scheduler.remove_job(job.id)
    for item in list_searches():
        frequency=item.get("frequency","manual")
        if frequency not in {"daily","weekly"}: continue
        trigger="interval"
        kwargs={"days":1} if frequency=="daily" else {"weeks":1}
        _scheduler.add_job(_run_search,trigger=trigger,id=item["id"],args=[item],replace_existing=True,coalesce=True,max_instances=1,**kwargs)

def start_scheduler():
    global _scheduler
    if BackgroundScheduler is None:
        logger.warning("APScheduler is not installed; scheduled alerts are disabled. Install backend requirements.")
        return
    if _scheduler is None:
        _scheduler=BackgroundScheduler(timezone="UTC")
        _scheduler.start()
    refresh_schedules()

def stop_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False); _scheduler=None
