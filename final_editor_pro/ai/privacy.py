"""Single-use, expiring consent bound to exact serialized upload and destination."""
from dataclasses import dataclass
import hashlib
import secrets
import time


@dataclass(frozen=True)
class UploadPreview:
    provider: str
    task: str
    endpoint: str
    sha256: str
    size_bytes: int


def preview(provider, task, endpoint, payload):
    return UploadPreview(provider, str(task), endpoint, hashlib.sha256(payload).hexdigest(), len(payload))


class PrivacyPolicy:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._grants = {}

    def approve(self, upload, *, confirmed=False, ttl_seconds=300):
        if confirmed is not True or not 0 < ttl_seconds <= 300:
            raise PermissionError('Explicit consent with a maximum five-minute TTL required')
        token = secrets.token_urlsafe(32)
        self._grants[token] = (upload, self._clock() + ttl_seconds)
        return token

    def consume(self, token, upload):
        grant = self._grants.pop(token, None)
        if not grant or grant[0] != upload or grant[1] <= self._clock():
            raise PermissionError('Upload is not approved, changed, expired or already used')
