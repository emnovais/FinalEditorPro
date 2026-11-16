"""Explicit JSON configuration, global defaults plus project overrides."""
from enum import StrEnum
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
from typing import Literal
from pydantic import Field, model_validator
from .schemas import Contract, Task, LOCAL_OPERATIONS


class Mode(StrEnum):
    LOCAL = 'LOCAL'
    HYBRID = 'HYBRID'
    CLOUD = 'CLOUD'


class ProviderSettings(Contract):
    kind: Literal['local', 'cloud']
    model: str = Field(min_length=1, max_length=256)
    enabled: bool = Field(default=False, strict=True)
    capabilities: list[Task] = Field(min_length=1)
    endpoint: str | None = None
    keychain_account: str | None = None
    executable: str | None = None
    model_path: str | None = None
    executable_sha256: str | None = None
    model_sha256: str | None = None
    input_usd_per_million: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    output_usd_per_million: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    adapter: Literal['default', 'ollama', 'llama-server'] = 'default'
    local_endpoint: str = 'http://127.0.0.1:11435'
    model_digest: str | None = None

    @model_validator(mode='after')
    def supported(self):
        allowed = ({Task.TEMPORAL_VISUAL} if self.adapter in ('ollama', 'llama-server') else {Task.PLANNING}) if self.kind == 'local' else {Task.PLANNING, Task.VISUAL, Task.TEMPORAL_VISUAL}
        if self.adapter in ('ollama', 'llama-server') and self.kind != 'local':
            raise ValueError('Ollama adapter must be local')
        if not set(self.capabilities) <= allowed:
            raise ValueError('Optional adapters do not implement segmentation/VFX/media operations')
        if self.endpoint:
            url = urlsplit(self.endpoint)
            if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError('Endpoint must be HTTPS without credentials/query/fragment')
        return self


class ProcessingConfig(Contract):
    mode: Mode = Mode.LOCAL
    routes: dict[Task, str] = Field(default_factory=dict)
    allow_uploads: bool = Field(default=False, strict=True)
    providers: dict[str, ProviderSettings] = Field(default_factory=dict)

    @model_validator(mode='after')
    def valid_routes(self):
        if any(task in LOCAL_OPERATIONS for task in self.routes):
            raise ValueError('Media IO and FCPXML export belong to local engines')
        if any(not value.strip() for value in self.routes.values()):
            raise ValueError('Provider identifier cannot be empty')
        return self


class ProjectOverride(Contract):
    mode: Mode | None = None
    routes: dict[Task, str] = Field(default_factory=dict)
    allow_uploads: bool | None = Field(default=None, strict=True)
    providers: dict[str, ProviderSettings] = Field(default_factory=dict)


def resolve_config(global_config, override=None):
    base = global_config.model_dump(mode='json')
    if override is not None:
        patch = override.model_dump(mode='json', exclude_none=True)
        base['routes'].update(patch.pop('routes', {}))
        base['providers'].update(patch.pop('providers', {}))
        base.update(patch)
    return ProcessingConfig.model_validate(base)


def load_config(global_path, project_path=None):
    base = ProcessingConfig.model_validate_json(Path(global_path).read_text())
    override = ProjectOverride.model_validate_json(Path(project_path).read_text()) if project_path else None
    return resolve_config(base, override)
