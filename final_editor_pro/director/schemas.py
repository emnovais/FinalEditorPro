from fractions import Fraction
from typing import Literal
from pydantic import Field, model_validator
from ..analysis.schemas import Schema

class CreativeBrief(Schema):
    version: Literal['0.3.0']='0.3.0'
    project_type: Literal['wedding','restaurant','event','travel','social','couple']
    objective: str = Field(min_length=1,max_length=2000)
    target_seconds: str
    aspect_ratio: Literal['16:9','9:16','1:1','4:3']
    fps: str
    output_width: int = Field(default=3840,gt=0)
    output_height: int = Field(default=2160,gt=0)
    slow_motion_allowed: bool = False
    max_shots_per_asset: int | None = Field(default=None,ge=1,le=20)
    visual_style: str = Field(min_length=1,max_length=1000)
    pace: Literal['slow','balanced','energetic']
    narrative_preferences: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    required_candidate_ids: list[str] = Field(default_factory=list)
    music_path: str | None = None
    model_id: Literal['qwen3-vl-8b-instruct','gemma3-12b']
    @model_validator(mode='after')
    def clock(self):
        if not 0<Fraction(self.fps)<=120 or not 0<Fraction(self.target_seconds)<=300:
            raise ValueError('Invalid brief duration/fps (maximum 300 seconds)')
        if (Fraction(self.target_seconds)*Fraction(self.fps)).denominator!=1:
            raise ValueError('Target duration must align to timeline frames')
        if Fraction(self.output_width,self.output_height)!=Fraction(self.aspect_ratio.replace(':','/')): raise ValueError('Output geometry/aspect mismatch')
        return self

class BriefInterpretation(Schema):
    brief: CreativeBrief | None
    missing_fields: list[str]
    field_evidence: dict[str,str]
    @model_validator(mode='after')
    def sufficient(self):
        if self.missing_fields and self.brief is not None: raise ValueError('Incomplete brief must request clarification')
        return self

class BriefRequest(Schema):
    instruction: str = Field(min_length=1,max_length=10000)

class Candidate(Schema):
    candidate_id: str
    asset_id: str
    segment_id: str
    start_frame: int = Field(ge=0,strict=True)
    end_frame: int = Field(gt=0,strict=True)
    fps: str
    description: str
    technical: dict
    confidence: float = Field(ge=0,le=1)
    components: dict[str,float | None]
    evidence: list[dict]
    interpretations: list[dict]
    warnings: list[str]
    @model_validator(mode='after')
    def interval(self):
        if self.end_frame<=self.start_frame or Fraction(self.fps)<=0: raise ValueError('Empty candidate')
        return self

class DirectionRequest(Schema):
    brief: CreativeBrief
    candidates: list[Candidate] = Field(min_length=1,max_length=100)

class NarrativeChoice(Schema):
    speed: Literal['1','1/2'] = '1'
    candidate_id: str
    role: Literal['opening','development','highlight','ending']
    reason: str = Field(min_length=1,max_length=1000)
    brief_relation: str = Field(min_length=1,max_length=1000)
    confidence: float = Field(ge=0,le=1)

class NarrativePlan(Schema):
    choices: list[NarrativeChoice] = Field(min_length=1,max_length=20)
    rationale: str = Field(min_length=1,max_length=2000)
    warnings: list[str]

class EditDecision(Schema):
    candidate_id: str
    asset_id: str
    segment_id: str
    source_in_frame: int = Field(ge=0,strict=True)
    source_out_frame: int = Field(gt=0,strict=True)
    timeline_start_frame: int = Field(ge=0,strict=True)
    duration_frames: int = Field(gt=0,strict=True)
    fps: str
    source_fps: str
    speed: Literal['1','1/2']
    audio_policy: Literal['preserve','mute_slow_motion']
    source_in_seconds: str
    source_out_seconds: str
    timeline_start_seconds: str
    duration_seconds: str
    role: str
    rationale: str
    brief_relation: str
    confidence: float = Field(ge=0,le=1)
    score_components: dict[str,float | None]
    refinement: dict
    music_sync: dict | None = None
    @model_validator(mode='after')
    def exact(self):
        if Fraction(self.source_out_frame-self.source_in_frame)/Fraction(self.source_fps)!=Fraction(self.duration_frames)/Fraction(self.fps)*Fraction(self.speed): raise ValueError('Duration/retime mismatch')
        if self.speed=='1/2' and self.audio_policy!='mute_slow_motion': raise ValueError('Slow-motion audio policy missing')
        fps=Fraction(self.fps)
        if fps<=0: raise ValueError('Invalid fps')
        for frame,sec,clock in ((self.source_in_frame,self.source_in_seconds,self.source_fps),(self.source_out_frame,self.source_out_seconds,self.source_fps),(self.timeline_start_frame,self.timeline_start_seconds,self.fps),(self.duration_frames,self.duration_seconds,self.fps)):
            if Fraction(frame)/Fraction(clock)!=Fraction(sec): raise ValueError('EDL time mismatch')
        return self

class EditDecisionList(Schema):
    version: Literal['0.3.0']='0.3.0'
    brief: CreativeBrief
    media: list[dict] = Field(min_length=1)
    decisions: list[EditDecision] = Field(min_length=1)
    total_frames: int = Field(gt=0)
    music: dict | None = None
    planning: dict
    warnings: list[str]
    @model_validator(mode='after')
    def bounded(self):
        assets={m['sha256']:m for m in self.media}; cursor=0
        if len(assets)!=len(self.media): raise ValueError('Duplicate media')
        for d in self.decisions:
            if d.asset_id not in assets: raise ValueError('Missing asset')
            m=assets[d.asset_id]
            if d.fps!=self.brief.fps or Fraction(m['fps'])!=Fraction(d.source_fps): raise ValueError('Invalid source/timeline clock')
            if d.speed!='1' and not self.brief.slow_motion_allowed: raise ValueError('Slow motion not authorized')
            if d.source_out_frame>Fraction(m['duration'])*Fraction(m['fps']): raise ValueError('EDL outside media')
            if d.timeline_start_frame!=cursor: raise ValueError('EDL gap/overlap')
            cursor+=d.duration_frames
        if self.brief.max_shots_per_asset is not None:
            counts={}
            for d in self.decisions:counts[d.asset_id]=counts.get(d.asset_id,0)+1
            if any(n>self.brief.max_shots_per_asset for n in counts.values()):raise ValueError('EDL repeats a source beyond the brief limit')
        if cursor!=self.total_frames or cursor!=Fraction(self.brief.target_seconds)*Fraction(self.brief.fps): raise ValueError('Target duration mismatch')
        return self


def validate_direction(request,plan,check_duration=False):
    candidates={c.candidate_id:c for c in request.candidates}
    ids=[c.candidate_id for c in plan.choices]
    if len(set(ids))!=len(ids) or not set(ids)<=set(candidates): raise ValueError('Unknown/duplicate candidate')
    if request.brief.max_shots_per_asset is not None:
        counts={}
        for candidate_id in ids:
            asset=candidates[candidate_id].asset_id;counts[asset]=counts.get(asset,0)+1
        if any(n>request.brief.max_shots_per_asset for n in counts.values()):raise ValueError('Narrative repeats source media beyond the brief limit')
    if not set(request.brief.required_candidate_ids)<=set(ids): raise ValueError('Required candidate omitted')
    if len(ids)>1 and (plan.choices[0].role!='opening' or plan.choices[-1].role!='ending'): raise ValueError('Missing opening/ending')
    if any(c.speed!='1' for c in plan.choices) and not request.brief.slow_motion_allowed: raise ValueError('Slow motion not permitted')
    available=sum(Fraction(candidates[c.candidate_id].end_frame-candidates[c.candidate_id].start_frame)/Fraction(candidates[c.candidate_id].fps)/Fraction(c.speed)*Fraction(request.brief.fps) for c in plan.choices)
    if check_duration and available<Fraction(request.brief.target_seconds)*Fraction(request.brief.fps): raise ValueError('Insufficient selected footage')
    return plan

class MusicAnalysis(Schema):
    schema_version: Literal['0.3.0']='0.3.0'
    method: Literal['log-energy-novelty-autocorrelation-v1']
    path: str
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    duration_seconds: str
    source_start_seconds: str = '0'
    source_clock_kind: Literal['zero','bwf_sample_reference'] = 'zero'
    bwf_time_reference_samples: int | None = Field(default=None,ge=0)
    decoded_duration_seconds: str | None = None
    decoded_limit_seconds: int = Field(gt=0)
    estimated_bpm: float | None = Field(default=None,gt=0,allow_inf_nan=False)
    stable_tempo_supported: bool
    tempo_windows: list[dict]
    onsets_seconds: list[str]
    estimated_beats_seconds: list[str]
    intensity_peaks_seconds: list[str]
    warnings: list[str]
    channels: int | None = Field(default=None,ge=1,le=2)
    sample_rate: int | None = Field(default=None,gt=0)
    @model_validator(mode='after')
    def times(self):
        duration=Fraction(self.duration_seconds)
        if duration<=0:raise ValueError('Empty music')
        if Fraction(self.source_start_seconds)<0:raise ValueError('Negative music source origin')
        if self.source_clock_kind=='bwf_sample_reference':
            if self.bwf_time_reference_samples is None or self.sample_rate is None or Fraction(self.source_start_seconds)!=Fraction(self.bwf_time_reference_samples,self.sample_rate):raise ValueError('Inconsistent BWF source clock')
        elif Fraction(self.source_start_seconds)!=0 or self.bwf_time_reference_samples is not None:raise ValueError('Unexpected non-BWF origin')
        for field in (self.onsets_seconds,self.estimated_beats_seconds,self.intensity_peaks_seconds):
            if any(not 0<=Fraction(t)<duration for t in field):raise ValueError('Music event out of bounds')
        return self
