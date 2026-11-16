"""Minimal provider protocol. Production adapters never fabricate model results."""
from dataclasses import dataclass
from decimal import Decimal
import json
from typing import Protocol, runtime_checkable, Callable
from .schemas import Contract, Task, CONTRACTS, validate_output
from .privacy import PrivacyPolicy, preview


@dataclass(frozen=True)
class ProviderResult:
    output: Contract
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: Decimal | None = None


@runtime_checkable
class AIProvider(Protocol):
    id: str
    model: str
    remote: bool
    capabilities: frozenset[Task]

    def run(self, task: Task, request: Contract, consent: str | None = None) -> ProviderResult: ...

    def upload_preview(self, task: Task, request: Contract): ...


class LocalProvider:
    remote = False

    def __init__(self, provider_id: str, model: str, handlers: dict[Task, Callable]):
        self.id, self.model = provider_id, model
        self._handlers = dict(handlers)
        self.capabilities = frozenset(handlers)

    def run(self, task, request, consent=None):
        if task not in self.capabilities:
            raise ValueError('Local model does not support task')
        validated = CONTRACTS[task][0].model_validate(request)
        result = self._handlers[task](validated)
        output = validate_output(task, validated, result)
        return ProviderResult(output=output, estimated_cost_usd=Decimal('0'))

    def upload_preview(self, task, request):
        raise PermissionError('Local providers never upload')


class CloudProvider:
    remote = True

    def __init__(self, provider_id, model, endpoint, capabilities, policy: PrivacyPolicy,
                 transport: Callable, input_usd_per_million=None, output_usd_per_million=None,
                 payload_builder=None):
        self.id, self.model, self.endpoint = provider_id, model, endpoint
        self.capabilities = frozenset(capabilities)
        self._policy, self._transport = policy, transport
        self._payload_builder = payload_builder
        self._input_rate = Decimal(str(input_usd_per_million)) if input_usd_per_million is not None else None
        self._output_rate = Decimal(str(output_usd_per_million)) if output_usd_per_million is not None else None
        if any(rate is not None and (not rate.is_finite() or rate < 0)
               for rate in (self._input_rate, self._output_rate)):
            raise ValueError('Rates must be finite and nonnegative')

    def payload(self, task, request):
        if task not in self.capabilities:
            raise ValueError('Remote model does not support task')
        request = CONTRACTS[task][0].model_validate(request)
        if self._payload_builder is not None:
            return self._payload_builder(task, request, self.model)
        return json.dumps(dict(model=self.model, task=str(task),
                               input=request.model_dump(mode='json'),
                               output_schema=CONTRACTS[task][1].model_json_schema()),
                          sort_keys=True, separators=(',', ':')).encode()

    def upload_preview(self, task, request):
        return preview(self.id, task, self.endpoint, self.payload(task, request))

    def run(self, task, request, consent=None):
        payload = self.payload(task, request)
        self._policy.consume(consent, preview(self.id, task, self.endpoint, payload))
        response = self._transport(self.endpoint, payload)
        output = validate_output(task, request, response['output'])
        usage = response.get('usage', {})
        i, o = usage.get('input_tokens'), usage.get('output_tokens')
        for value in (i, o):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError('Invalid usage returned by provider')
        cost = None
        if i is not None and o is not None and self._input_rate is not None and self._output_rate is not None:
            cost = (i * self._input_rate + o * self._output_rate) / Decimal(1_000_000)
        return ProviderResult(output, i, o, cost)
