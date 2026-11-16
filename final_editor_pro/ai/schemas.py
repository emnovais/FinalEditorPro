"""Provider-independent bounded model contracts."""
from enum import StrEnum
from typing import Literal
import base64
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class Task(StrEnum):
    VISUAL = 'visual_analysis'
    PLANNING = 'planning'
    SEGMENTATION = 'segmentation'
    EFFECTS = 'effect_generation'
    PROBE = 'media_probe'
    TRANSCODE = 'transcode'
    EXPORT = 'fcpxml_export'


LOCAL_OPERATIONS = frozenset({Task.PROBE, Task.TRANSCODE, Task.EXPORT})


class Frame(Contract):
    asset_id: str = Field(min_length=1, max_length=128)
    frame_index: int = Field(ge=0, strict=True)
    mime: Literal['image/jpeg', 'image/png']
    data_base64: str = Field(min_length=4, max_length=8_000_000)

    @field_validator('data_base64')
    @classmethod
    def valid_base64(cls, value):
        base64.b64decode(value, validate=True)
        return value


class VisualInput(Contract):
    instruction: str = Field(min_length=1, max_length=16000)
    frames: list[Frame] = Field(min_length=1, max_length=16)


class Observation(Contract):
    asset_id: str = Field(min_length=1, max_length=128)
    frame_index: int = Field(ge=0, strict=True)
    description: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)


class VisualOutput(Contract):
    observations: list[Observation] = Field(max_length=1000)


class AssetSummary(Contract):
    asset_id: str = Field(min_length=1, max_length=128)
    total_frames: int = Field(gt=0, strict=True)


class PlanningInput(Contract):
    brief: str = Field(min_length=1, max_length=16000)
    assets: list[AssetSummary] = Field(min_length=1, max_length=1000)
    evidence: list[Observation] = Field(default_factory=list, max_length=1000)


class Cut(Contract):
    asset_id: str = Field(min_length=1, max_length=128)
    in_frames: int = Field(ge=0, strict=True)
    duration_frames: int = Field(gt=0, strict=True)


class CreativePlan(Contract):
    version: Literal[1] = 1
    cuts: list[Cut] = Field(min_length=1, max_length=10000)
    rationale: str = Field(max_length=16000)


class SegmentationInput(Contract):
    frame: Frame
    object_description: str = Field(min_length=1, max_length=4000)


class SegmentationOutput(Contract):
    mask_png_base64: str = Field(min_length=4, max_length=16_000_000)


class EffectsInput(Contract):
    instruction: str = Field(min_length=1, max_length=4000)
    duration_frames: int = Field(gt=0, strict=True)


class EffectsOutput(Contract):
    recipe: str = Field(min_length=1, max_length=16000)
    executable: Literal[False] = False


CONTRACTS = {
    Task.VISUAL: (VisualInput, VisualOutput),
    Task.PLANNING: (PlanningInput, CreativePlan),
    Task.SEGMENTATION: (SegmentationInput, SegmentationOutput),
    Task.EFFECTS: (EffectsInput, EffectsOutput),
}


def validate_output(task, request, output):
    result = CONTRACTS[task][1].model_validate(output)
    if task == Task.PLANNING:
        assets = {a.asset_id: a.total_frames for a in request.assets}
        if len(assets) != len(request.assets):
            raise ValueError('Duplicate asset identifiers')
        for cut in result.cuts:
            if cut.asset_id not in assets or cut.in_frames + cut.duration_frames > assets[cut.asset_id]:
                raise ValueError('Model proposed a cut outside the source')
    if task == Task.VISUAL:
        frames = {(f.asset_id, f.frame_index) for f in request.frames}
        if any((o.asset_id, o.frame_index) not in frames for o in result.observations):
            raise ValueError('Model referenced an unsubmitted frame')
    return result
