"""Version information endpoints"""

import json
import logging
from pathlib import Path

import pypsa
from fastapi import APIRouter

from pypsa_app.backend.__version__ import __version__
from pypsa_app.backend.schemas.version import VersionResponse
from pypsa_app.backend.settings import settings

router = APIRouter()


def get_frontend_version(package_json_path: Path) -> str:
    """Read version from a package.json file"""
    try:
        if package_json_path.exists():
            with package_json_path.open() as f:
                data = json.load(f)
                return data.get("version", "unknown")
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).debug("Failed to read %s", package_json_path)
    return "unknown"


@router.get("/", response_model=VersionResponse)
async def get_version() -> dict:
    """Get PyPSA and application version information"""
    # Read frontend versions from package.json files
    project_root = Path(__file__).parent.parent.parent.parent.parent.parent
    app_package_path = project_root / "frontend" / "app" / "package.json"
    map_package_path = project_root / "frontend" / "map" / "package.json"

    frontend_app_version = get_frontend_version(app_package_path)
    frontend_map_version = get_frontend_version(map_package_path)

    return {
        "backend_version": __version__,
        "frontend_app_version": frontend_app_version,
        "frontend_map_version": frontend_map_version,
        "pypsa_version": pypsa.__version__,
        "snakedispatch_backends": [b["name"] for b in settings.resolved_backends],
        "chat_enabled": settings.llm.chat_enabled,
    }
