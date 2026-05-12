"""Version response schemas"""

from pydantic import BaseModel


class VersionResponse(BaseModel):
    backend_version: str
    frontend_app_version: str
    frontend_map_version: str
    pypsa_version: str
    snakedispatch_backends: list[str]
    chat_enabled: bool = False
