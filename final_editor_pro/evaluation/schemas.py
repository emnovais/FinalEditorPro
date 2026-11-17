from fractions import Fraction
from typing import Literal
from pydantic import Field, model_validator
from ..analysis.schemas import Schema, VisualAnalysis

CATEGORIES=('restaurant','wedding','event','travel','people_motion','camera_motion','low_light','rapid_changes')
CRITERIA=('visual_precision','temporal_understanding','reliability','creative_utility','speed','memory_efficiency')


def case_signature(case):
    from ..analysis.pipeline import fingerprint
    return fingerprint({key:getattr(case,key) for key in ('sha256','fps','start_frame','end_frame')})


class EvaluationWeights(Schema):
    visual_precision: float = Field(default=.25,ge=0,le=1)
    temporal_understanding: float = Field(default=.25,ge=0,le=1)
    reliability: float = Field(default=.20,ge=0,le=1)
    creative_utility: float = Field(default=.15,ge=0,le=1)
    speed: float = Field(default=.10,ge=0,le=1)
    memory_efficiency: float = Field(default=.05,ge=0,le=1)

    @model_validator(mode='after')
    def total(self):
        if abs(sum(self.model_dump().values())-1)>1e-9: raise ValueError('Weights must sum to 1; no implicit normalization')
        return self


class HumanFact(Schema):
    label: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)

    @model_validator(mode='after')
    def interval(self):
        if self.end_frame<=self.start_frame: raise ValueError('Fact interval is empty')
        return self


class HumanReference(Schema):
    status: Literal['pending','verified'] = 'pending'
    annotator: str | None = None
    verified_at: str | None = None
    evidence_notes: str = ''
    objects: list[HumanFact] = Field(default_factory=list)
    actions: list[HumanFact] = Field(default_factory=list)
    events: list[HumanFact] = Field(default_factory=list)
    objects_exhaustive: bool = False
    source_path: str | None = None
    source_sha256: str | None = None
    visual_description: str = ''
    audio_notes: str = ''
    pending_fields: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def provenance(self):
        if self.status=='verified' and (not self.annotator or not self.verified_at or not self.evidence_notes):
            raise ValueError('Verified references require human provenance and evidence notes')
        return self


class EvaluationCase(Schema):
    case_id: str = Field(pattern=r'^[A-Za-z0-9_-]+$')
    original_path: str
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    source_group: str = Field(min_length=1)
    split: Literal['development','evaluation','unassigned'] = 'unassigned'
    categories: list[str] = Field(default_factory=list)
    fps: str
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    reference: HumanReference = Field(default_factory=HumanReference)

    @model_validator(mode='after')
    def consistent(self):
        if Fraction(self.fps)<=0 or self.end_frame<=self.start_frame: raise ValueError('Invalid case clock')
        if set(self.categories)-set(CATEGORIES): raise ValueError('Unknown dataset category')
        for fact in self.reference.objects+self.reference.actions+self.reference.events:
            if not self.start_frame<=fact.start_frame<fact.end_frame<=self.end_frame:
                raise ValueError('Human fact outside case interval')
        return self


class EvaluationDataset(Schema):
    schema_version: Literal['0.2.1']='0.2.1'
    dataset_id: str
    frozen: bool = False
    cases: list[EvaluationCase] = Field(min_length=1)

    @model_validator(mode='after')
    def disjoint(self):
        if len({c.case_id for c in self.cases})!=len(self.cases): raise ValueError('Duplicate case IDs')
        groups={}
        for c in self.cases:
            if c.split!='unassigned': groups.setdefault(c.source_group,set()).add(c.split)
        if any(len(s)>1 for s in groups.values()): raise ValueError('Source group leaks across development/evaluation splits')
        for i,a in enumerate(self.cases):
            for b in self.cases[i+1:]:
                if a.sha256==b.sha256 and a.split!=b.split and 'unassigned' not in (a.split,b.split):
                    raise ValueError('Same media leaks across splits even under renamed groups')
        if self.frozen and any(c.split=='unassigned' or c.reference.status!='verified' for c in self.cases):
            raise ValueError('Frozen dataset needs human references and assigned splits')
        return self


class ModelSpec(Schema):
    model_id: str = Field(pattern=r'^[A-Za-z0-9_-]+$')
    display_name: str
    runtime_manifest: str
    model_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    quantization: str
    license: str
    status: Literal['candidate','ready','incompatible']='candidate'
    limitations: list[str] = Field(default_factory=list)


class Trial(Schema):
    trial_id: str
    model_id: str
    case_id: str
    repetition: int = Field(ge=0)
    condition: Literal['cold_inference','warm_inference','report_cache']
    input_sha256: str
    protocol_sha256: str
    case_signature: str | None = None
    status: Literal['success','failed','timeout']
    latency_seconds: float | None = Field(default=None,ge=0,allow_inf_nan=False)
    setup_seconds: float = Field(ge=0,allow_inf_nan=False)
    load_ready_seconds: float | None = Field(default=None,ge=0,allow_inf_nan=False)
    integrity_seconds: float | None = Field(default=None,ge=0,allow_inf_nan=False)
    server_rss_bytes: int | None = Field(default=None,gt=0)
    input_tokens: int | None = Field(default=None,ge=0)
    output_tokens: int | None = Field(default=None,ge=0)
    generation_tokens_per_second: float | None = Field(default=None,gt=0)
    output: VisualAnalysis | None = None
    error_type: str | None = None
    error_details: list[dict] = Field(default_factory=list)
    memory_sampling_errors: int = Field(default=0,ge=0)
    response_sha256: str | None = None
    format_normalized: bool = False

    @model_validator(mode='after')
    def outcome(self):
        if self.status=='success' and self.output is None: raise ValueError('Successful trial needs validated output')
        if self.status!='success' and self.output is not None: raise ValueError('Failed trial cannot carry certified output')
        if self.status=='success':
            from ..analysis.pipeline import fingerprint
            if self.response_sha256!=fingerprint(self.output.model_dump(mode='json')):
                raise ValueError('Response checksum mismatch')
            if self.latency_seconds is None: raise ValueError('Successful trial requires measured latency')
        return self


class HumanReview(Schema):
    blind_id: str
    reviewer: str = Field(min_length=1)
    reviewed_at: str
    response_sha256: str
    visual_precision: int = Field(ge=0,le=4,strict=True)
    temporal_understanding: int = Field(ge=0,le=4,strict=True)
    reliability: int = Field(ge=0,le=4,strict=True)
    creative_utility: int = Field(ge=0,le=4,strict=True)
    unsupported_claims: int = Field(ge=0,strict=True)
    checked_claims: int = Field(gt=0,strict=True)
    uncertainty_notes: str
    notes: str = Field(min_length=1)

    @model_validator(mode='after')
    def claims(self):
        if self.unsupported_claims>self.checked_claims: raise ValueError('Unsupported exceeds reviewed claims')
        return self
