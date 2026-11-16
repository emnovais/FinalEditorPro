"""Versioned, provider-independent analysis contracts; intervals are [start,end)."""
from fractions import Fraction
from typing import Literal
import base64
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator


class Schema(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class MediaAsset(Schema):
    asset_id: str
    original_path: str
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    size_bytes: int = Field(gt=0)
    fps: str
    duration: str
    source_start: str
    total_frames: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    codec: str | None
    orientation: Literal['unrotated'] = 'unrotated'
    metadata: dict

    @model_validator(mode='after')
    def clock(self):
        if Fraction(self.fps) <= 0 or Fraction(self.duration) * Fraction(self.fps) != self.total_frames:
            raise ValueError('Inconsistent media clock')
        return self


class FrameSample(Schema):
    frame_index: int = Field(ge=0)
    timestamp: str
    image_path: str
    image_sha256: str


class TechnicalMetrics(Schema):
    sampled_frames: int = Field(ge=1)
    sharpness_laplacian_variance: float = Field(ge=0, allow_inf_nan=False)
    mean_luma: float = Field(ge=0, le=1)
    dark_fraction: float = Field(ge=0, le=1)
    bright_fraction: float = Field(ge=0, le=1)
    interframe_difference: float = Field(ge=0, le=1)
    instability_proxy: float = Field(ge=0, le=1)
    caveats: list[str]


class TransitionOpportunity(Schema):
    kind: Literal['transition', 'mask', 'effect']
    suggestion: str
    evidence_frame_indices: list[int] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    implemented: Literal[False] = False


class VisualAnalysis(Schema):
    description: str = Field(min_length=1, max_length=4000)
    people: list[str] = Field(max_length=30)
    objects: list[str] = Field(max_length=50)
    environment: str
    actions: list[str] = Field(max_length=30)
    framing: str
    apparent_movement: str
    atmosphere: str
    opportunities: list[TransitionOpportunity] = Field(max_length=10)
    evidence_frame_indices: list[int] = Field(min_length=1)
    uncertainties: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    assessments: dict[str, float | None] = Field(default_factory=dict)
    assessment_reasons: dict[str, str] = Field(default_factory=dict)

    @field_validator('assessments')
    @classmethod
    def bounded_assessments(cls, values):
        allowed = {'visual_relevance', 'action_presence', 'narrative_potential', 'transition_potential'}
        if set(values) - allowed or any(v is not None and not 0 <= v <= 1 for v in values.values()):
            raise ValueError('Unknown or out-of-range subjective assessment')
        return values


class TemporalFrame(Schema):
    frame_index: int = Field(ge=0)
    timestamp: str
    data_base64: str = Field(min_length=4, max_length=8_000_000)
    mime: Literal['image/png'] = 'image/png'

    @field_validator('data_base64')
    @classmethod
    def encoded(cls, v):
        base64.b64decode(v, validate=True)
        return v


class TemporalInput(Schema):
    asset_id: str
    fps: str
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    frames: list[TemporalFrame] = Field(min_length=1, max_length=12)

    @model_validator(mode='after')
    def intervals(self):
        if self.end_frame <= self.start_frame or Fraction(self.fps) <= 0:
            raise ValueError('Invalid temporal interval')
        indices = [f.frame_index for f in self.frames]
        if indices != sorted(set(indices)):
            raise ValueError('Frames must be unique and chronological')
        for frame in self.frames:
            if not self.start_frame <= frame.frame_index < self.end_frame:
                raise ValueError('Frame outside temporal segment')
            if Fraction(frame.timestamp) != Fraction(frame.frame_index) / Fraction(self.fps):
                raise ValueError('Frame timestamp does not match source clock')
        return self


class ScoreComponent(Schema):
    value: float | None = Field(default=None, ge=0, le=1)
    weight: float = Field(ge=0)
    reason: str


class ShotScore(Schema):
    profile: str
    components: dict[str, ScoreComponent]
    weighted_score: float | None = Field(default=None, ge=0, le=1)
    available_weight_fraction: float = Field(ge=0, le=1)
    caveat: str = 'Heuristic triage only; never automatically discard a take.'


class SceneSegment(Schema):
    segment_id: str
    asset_id: str
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    start_time: str
    end_time: str
    boundary_uncertainty_frames: int = Field(ge=0)
    sampled_frames: list[FrameSample] = Field(min_length=1)
    technical: TechnicalMetrics
    visual: VisualAnalysis | None = None
    score: ShotScore
    provider: str | None = None
    model: str | None = None
    semantic_status: Literal['not_requested', 'complete', 'failed'] = 'not_requested'


class AnalysisReport(Schema):
    schema_version: Literal['0.2.0'] = '0.2.0'
    pipeline_version: Literal['analyzer-2'] = 'analyzer-2'
    asset: MediaAsset
    segments: list[SceneSegment] = Field(min_length=1)
    config: dict
    benchmark: dict
    limitations: list[str]

    @model_validator(mode='after')
    def coverage(self):
        cursor = 0
        for s in self.segments:
            if s.asset_id != self.asset.asset_id or s.start_frame != cursor or s.end_frame <= cursor:
                raise ValueError('Segments must cover the source contiguously')
            for i,t in [(s.start_frame,s.start_time),(s.end_frame,s.end_time)]:
                if Fraction(t) != Fraction(i) / Fraction(self.asset.fps):
                    raise ValueError('Segment timestamp mismatch')
            for f in s.sampled_frames:
                if not s.start_frame <= f.frame_index < s.end_frame:
                    raise ValueError('Sample outside segment')
                if Fraction(f.timestamp) != Fraction(f.frame_index) / Fraction(self.asset.fps):
                    raise ValueError('Sample timestamp mismatch')
            cursor = s.end_frame
        if cursor != self.asset.total_frames:
            raise ValueError('Segments do not cover complete source')
        return self


class AnalysisConfig(Schema):
    sample_fps: str = '2'
    max_frames: int = Field(default=96, ge=2, le=512)
    proxy_width: int = Field(default=320, ge=64, le=640)
    min_scene_seconds: str = '1'
    histogram_threshold: float = Field(default=.4, gt=0, le=1)
    difference_threshold: float = Field(default=.12, gt=0, le=1)
    max_semantic_frames: int = Field(default=4, ge=2, le=12)
    semantic: bool = False
    profile: Literal['restaurant', 'wedding', 'event', 'travel', 'social'] = 'event'
    score_weights: dict[str, float] | None = None

    @model_validator(mode='after')
    def rates(self):
        if not 0 < Fraction(self.sample_fps) <= 10 or Fraction(self.min_scene_seconds) <= 0:
            raise ValueError('Invalid analysis sampling rate or scene interval')
        return self
