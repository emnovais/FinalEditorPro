"""Capability routing with fail-closed LOCAL policy and no automatic retries."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from .config import Mode
from .schemas import CONTRACTS, LOCAL_OPERATIONS, Task, validate_output


class OperationJournal:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.is_symlink():
            raise ValueError('Journal must not be a symlink')
        if not self.path.parent.is_dir():
            raise ValueError('Journal parent must already exist')

    def record(self, **entry):
        # No prompts, frames, responses, credentials or consent tokens.
        with self.path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(dict(time=datetime.now(timezone.utc).isoformat(), **entry)) + '\n')


class ProcessingRouter:
    def __init__(self, config, providers, journal):
        self.config = config.model_copy(deep=True)
        self.providers = {p.id: p for p in providers}
        if len(self.providers) != len(providers):
            raise ValueError('Duplicate provider identifiers')
        self.journal = journal

    def select(self, task):
        task = Task(task)
        if task in LOCAL_OPERATIONS:
            raise ValueError('Mandatory local operation; use media/timeline engine directly')
        explicit = self.config.routes.get(task)
        if explicit:
            if explicit not in self.providers:
                raise ValueError('Configured provider not registered')
            candidates = [self.providers[explicit]]
        else:
            candidates = sorted(self.providers.values(), key=lambda p: (
                p.remote != (self.config.mode == Mode.CLOUD), p.id))
        for p in candidates:
            if p.remote and self.config.mode == Mode.LOCAL:
                if explicit:
                    raise PermissionError('LOCAL forbids remote AI; no cloud fallback')
                continue
            if task in p.capabilities:
                return p
        raise ValueError('No permitted provider supports this task')

    def preview_upload(self, task, request):
        p = self.select(task)
        if not p.remote or not self.config.allow_uploads:
            raise PermissionError('Remote uploads are disabled or task is local')
        validated = CONTRACTS[Task(task)][0].model_validate(request)
        return p.upload_preview(Task(task), validated)

    def run(self, task, request, consent=None):
        task = Task(task)
        start = time.monotonic()
        p = None
        try:
            p = self.select(task)
            request = CONTRACTS[task][0].model_validate(request)
            if p.remote and not self.config.allow_uploads:
                raise PermissionError('Explicit upload eligibility must be enabled')
            # Journal availability is required before model execution.
            self.journal.record(action='started', task=str(task), provider=p.id,
                                model=p.model, remote=p.remote, mode=str(self.config.mode),
                                upload_sha256=p.upload_preview(task, request).sha256 if p.remote else None)
            result = p.run(task, request, consent)
            validate_output(task, request, result.output)
            self.journal.record(action='complete', task=str(task), provider=p.id,
                                model=p.model, remote=p.remote, mode=str(self.config.mode),
                                elapsed_seconds=time.monotonic() - start,
                                input_tokens=result.input_tokens, output_tokens=result.output_tokens,
                                estimated_cost_usd=str(result.estimated_cost_usd) if result.estimated_cost_usd is not None else None,
                                cost_kind='estimate' if result.estimated_cost_usd is not None else 'unknown')
            return result
        except Exception as exc:
            self.journal.record(action='failed', task=str(task),
                                provider=p.id if p else None, error=type(exc).__name__,
                                estimated_cost_usd=None, cost_kind='unknown')
            raise
