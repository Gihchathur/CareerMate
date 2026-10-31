"""Curated platform directory. External links are not represented as live API integrations."""
import json
from pathlib import Path
CATALOG_PATH = Path(__file__).resolve().parents[3] / "data" / "platform_catalog.json"
def list_platforms():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
