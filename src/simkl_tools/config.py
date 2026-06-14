import os
from dataclasses import dataclass

DEFAULT_APP_NAME = "simkl-tools"
DEFAULT_APP_VERSION = "0.1.0"


@dataclass
class Config:
    client_id: str
    access_token: str | None
    app_name: str
    app_version: str


def load_config(*, require_token: bool = False) -> Config:
    client_id = os.environ.get("SIMKL_CLIENT_ID", "")
    access_token = os.environ.get("SIMKL_ACCESS_TOKEN") or None
    app_name = os.environ.get("SIMKL_APP_NAME", DEFAULT_APP_NAME)
    app_version = os.environ.get("SIMKL_APP_VERSION", DEFAULT_APP_VERSION)

    if not client_id:
        raise ValueError("SIMKL_CLIENT_ID environment variable is required")
    if require_token and not access_token:
        raise ValueError("SIMKL_ACCESS_TOKEN environment variable is required for authenticated requests")

    return Config(
        client_id=client_id,
        access_token=access_token,
        app_name=app_name,
        app_version=app_version,
    )
