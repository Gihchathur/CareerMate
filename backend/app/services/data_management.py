"""Safe inspection and cleanup helpers for CareerMate's local data directory.

Only files underneath the supplied data root are managed. Template files
(*.example.json and .gitkeep) are preserved. backend/.env, source code, and the
Python environment are outside this directory and are never touched.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _is_template(path: Path) -> bool:
    return path.name == ".gitkeep" or path.name.endswith(".example.json")


def _read_array_count(path: Path) -> int:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        return len(payload) if isinstance(payload, list) else 0
    except (OSError, ValueError, TypeError):
        return 0


def _workspace_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    try:
        return [path for path in root.rglob("*") if (path.is_file() or path.is_symlink()) and not _is_template(path)]
    except OSError:
        return []


def get_data_summary(data_root: Path) -> dict[str, Any]:
    """Return counts only; never expose private document contents or paths."""
    cv_root = data_root / "cv"
    jobs_root = data_root / "jobs"
    apps_root = data_root / "applications"
    settings_root = data_root / "settings"
    source_cache_root = data_root / "source_cache"

    cv_files = [p for p in _workspace_files(cv_root) if p.is_file()]
    cache_files = [p for p in _workspace_files(source_cache_root) if p.is_file()]
    match_cache = jobs_root / "match_cache.json"
    if match_cache.is_file():
        cache_files.append(match_cache)

    settings_files = [p for p in _workspace_files(settings_root) if p.is_file()]
    sources_config = data_root / "sources.json"
    if sources_config.is_file():
        settings_files.append(sources_config)

    return {
        "success": True,
        "counts": {
            "cv_files": len(cv_files),
            "profile_saved": (cv_root / "profile.json").is_file(),
            "cv_text_saved": (cv_root / "extracted_text.txt").is_file(),
            "saved_jobs": _read_array_count(jobs_root / "jobs.json"),
            "applications": _read_array_count(apps_root / "applications.json"),
            "cache_files": len(cache_files),
            "settings_files": len(settings_files),
            "total_data_files": len(_workspace_files(data_root)),
        },
        "preserved": ["backend/.env (API keys)", "source code", "Python virtual environment", "example/template files"],
    }


def clear_cache_files(data_root: Path) -> int:
    """Clear derived job-match and public-source caches without touching saved data."""
    candidates = [data_root / "jobs" / "match_cache.json"]
    cache_root = data_root / "source_cache"
    if cache_root.exists():
        candidates.extend(path for path in cache_root.rglob("*") if path.is_file() or path.is_symlink())

    removed = 0
    failures = 0
    root_resolved = data_root.resolve()
    for path in candidates:
        try:
            # Never follow a symlink or delete outside the application data root.
            if not path.is_symlink() and not path.resolve().is_relative_to(root_resolved):
                continue
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
                removed += 1
        except OSError:
            failures += 1
    if failures:
        raise OSError(f"Could not remove {failures} cache file(s); check permissions and try again.")
    return removed


def reset_workspace_data(data_root: Path) -> int:
    """Delete all user-generated files within data_root, preserving templates."""
    data_root.mkdir(parents=True, exist_ok=True)
    removed = 0
    failures: list[str] = []
    root_resolved = data_root.resolve()
    try:
        paths = sorted(data_root.rglob("*"), key=lambda path: len(path.parts), reverse=True)
    except OSError as exc:
        raise OSError("Could not enumerate local workspace data files.") from exc

    for path in paths:
        try:
            if path.is_symlink():
                # Unlink the symlink itself; never traverse it.
                path.unlink(missing_ok=True)
                removed += 1
            elif path.is_file():
                if _is_template(path):
                    continue
                if not path.resolve().is_relative_to(root_resolved):
                    continue
                path.unlink(missing_ok=True)
                removed += 1
            elif path.is_dir():
                # Remove only empty directories; template directories remain.
                try:
                    path.rmdir()
                except OSError:
                    pass
        except OSError:
            failures.append(path.name)
    if failures:
        raise OSError(f"Could not remove {len(failures)} local data item(s); check file permissions and try again.")
    return removed

