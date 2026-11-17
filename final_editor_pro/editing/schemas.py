from fractions import Fraction
import math
from typing import Literal
from pydantic import Field,model_validator
from ..analysis.schemas import Schema
from ..director.schemas import EditDecisionList

class EditingSettings(Schema):
    version: Literal['0.4.0']='0.4.0'
    project_name: str = Field(default='Final Editor Pro — Intelligent Editing 0.4',min_length=1,max_length=256)
    continuity_weight: float = Field(default=.7,ge=0,le=1)
    allow_reorder: bool = True
    intentional_break_after: list[int] = Field(default_factory=list)
    action_strategy: Literal['cut_on_action','preserve_complete_action','cut_before_action','cut_after_action']='preserve_complete_action'
    search_radius_seconds: str = '2/5'
    music_tolerance_seconds: str = '6/25'
    min_shot_seconds: str = '1'
    music_gain_db: float = Field(default=-16,le=0,ge=-60)
    original_gain_db: float = Field(default=-6,le=0,ge=-60)
    fade_seconds: str = '1/5'
    ducking: bool = False
    duck_db: float = Field(default=-8,le=0,ge=-40)
    priority_ranges: list[tuple[str,str]] = Field(default_factory=list)
    @model_validator(mode='after')
    def bounds(self):
        for v in (self.search_radius_seconds,self.music_tolerance_seconds,self.fade_seconds):
            if not 0<=Fraction(v)<=2:raise ValueError('Unbounded editing tolerance')
        if Fraction(self.min_shot_seconds)<=0:raise ValueError('Invalid minimum shot')
        for a,b in self.priority_ranges:
            if not 0<=Fraction(a)<Fraction(b):raise ValueError('Invalid explicit audio priority range')
        if self.ducking and not self.priority_ranges:raise ValueError('Ducking needs explicit priority intervals; no invented dialogue')
        return self

class SubjectBox(Schema):
    x: float = Field(ge=0,le=1)
    y: float = Field(ge=0,le=1)
    width: float = Field(gt=0,le=1)
    height: float = Field(gt=0,le=1)
    confidence: float = Field(ge=0,le=1)
    @model_validator(mode='after')
    def contained(self):
        if self.x+self.width>1.000001 or self.y+self.height>1.000001:raise ValueError('Box outside frame')
        return self

class SubjectObservation(Schema):
    asset_sha256: str
    frame_index: int = Field(ge=0)
    image_sha256: str
    detector: str
    boxes: list[SubjectBox]
    rejected_box_count: int = Field(default=0,ge=0)
    warnings: list[str] = Field(default_factory=list)

class FrameFeature(Schema):
    frame_index: int = Field(ge=0)
    luma: float = Field(ge=0,le=1)
    sharpness: float = Field(ge=0)
    histogram: list[float]
    thumbnail: list[float]
    motion: float = Field(ge=0,le=1)
    image_shift: tuple[int,int]
    shift_confidence: float = Field(ge=0,le=1)
    subject_position: tuple[float,float] | None = None
    subject_area: float | None = Field(default=None,ge=0,le=1)
    subject_count: int | None = None

class ReframeDecision(Schema):
    decision_index: int = Field(ge=0)
    method: Literal['verified_detector_union','central_fallback']
    crop: tuple[float,float,float,float] # x,y,width,height normalized to original
    transform_position: tuple[float,float]
    confidence: float = Field(ge=0,le=1)
    evidence_frames: list[int]
    subject_box: tuple[float,float,float,float] | None = None
    warnings: list[str]
    @model_validator(mode='after')
    def safe(self):
        x,y,w,h=self.crop
        if not 0<w<=1 or not 0<h<=1 or min(x,y)<-1e-8 or x+w>1.00000001 or y+h>1.00000001:raise ValueError('Unsafe crop')
        if self.method=='verified_detector_union' and (len(set(self.evidence_frames))<3 or self.subject_box is None):raise ValueError('Missing temporal subject evidence')
        if self.subject_box is not None:
            a,b,r,bottom=self.subject_box
            if not 0<=a<r<=1 or not 0<=b<bottom<=1 or a<x-1e-7 or r>x+w+1e-7 or b<y-1e-7 or bottom>y+h+1e-7:raise ValueError('Subject outside crop')
        return self

class AudioEnvelope(Schema):
    points: list[tuple[str,float]]
    @model_validator(mode='after')
    def ordered(self):
        times=[Fraction(t) for t,g in self.points]
        if not times or times!=sorted(set(times)) or times[0]<0 or any(not -96<=g<=0 for t,g in self.points):raise ValueError('Invalid audio envelope')
        return self

class MixPlan(Schema):
    music_gain_db: float
    original_gain_db: float
    music_envelope: AudioEnvelope | None
    original_envelopes: list[AudioEnvelope | None]
    estimated_peak_bound_dbfs: float
    peak_measurements: dict
    ducking_applied: bool
    warnings: list[str]

class EditingPackage(Schema):
    version: Literal['0.4.0']='0.4.0'
    base_edl: EditDecisionList
    settings: EditingSettings
    source_edl_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    order: list[int]
    action_refinements: list[dict]
    reframing: list[ReframeDecision]
    continuity: dict
    music: dict
    mix: MixPlan
    provenance: dict
    @model_validator(mode='after')
    def integrity(self):
        n=len(self.base_edl.decisions)
        if sorted(self.order)!=list(range(n)):raise ValueError('Invalid source permutation')
        if [r.decision_index for r in self.reframing]!=list(range(n)) or len(self.mix.original_envelopes)!=n:raise ValueError('Missing per-decision settings')
        lookup={m['sha256']:m for m in self.base_edl.media}
        for d,r in zip(self.base_edl.decisions,self.reframing):
            m=lookup[d.asset_id];x,y,w,h=r.crop
            if abs(w*m['width']/(h*m['height'])-self.base_edl.brief.output_width/self.base_edl.brief.output_height)>1e-6:raise ValueError('Crop aspect differs from project')
            expected=((.5-x-w/2)*m['width']/m['height']*100,(y+h/2-.5)*100)
            if any(abs(a-b)>1e-6 for a,b in zip(expected,r.transform_position)):raise ValueError('Crop/transform mismatch')
            if r.method=='central_fallback' and (abs(x-(1-w)/2)>1e-6 or abs(y-(1-h)/2)>1e-6):raise ValueError('Fallback is not central')
            if any(not d.source_in_frame<=i<d.source_out_frame for i in r.evidence_frames):raise ValueError('Reframing evidence outside shot')
        if any(not math.isfinite(g) or g>0 or g< -120 for g in (self.mix.original_gain_db,self.mix.music_gain_db)):raise ValueError('Unsafe gain')
        duration=Fraction(self.base_edl.total_frames)/Fraction(self.base_edl.brief.fps)
        if self.mix.music_envelope and Fraction(self.mix.music_envelope.points[-1][0])>duration:raise ValueError('Music automation outside timeline')
        for d,envelope in zip(self.base_edl.decisions,self.mix.original_envelopes):
            if envelope and Fraction(envelope.points[-1][0])>Fraction(d.duration_seconds):raise ValueError('Source automation outside decision')
        return self
