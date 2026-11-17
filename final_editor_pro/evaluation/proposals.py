"""AI annotation proposals, kept separate from human benchmark references."""
from fractions import Fraction
from typing import Literal
from pydantic import Field
from ..analysis.schemas import Schema

class ProposedEvent(Schema):
    label: str = Field(min_length=1, max_length=300)
    evidence_frame_indices: list[int] = Field(min_length=2, max_length=8)
    confidence: float = Field(ge=0, le=1)
    uncertainty: str = Field(min_length=1)

class WindowProposal(Schema):
    description: str = Field(min_length=1)
    events: list[ProposedEvent] = Field(max_length=6)
    categories: list[Literal['restaurant','wedding','event','travel','people_motion','camera_motion','low_light','rapid_changes']]
    uncertainties: list[str] = Field(min_length=1)

    def grounded(self, indices):
        for event in self.events:
            evidence=event.evidence_frame_indices
            if len(set(evidence))<2 or not set(evidence)<=set(indices):
                raise ValueError('Event evidence must cite at least two distinct supplied frames')
        return self


def event_interval(event, fps):
    """Observed evidence span only; not a claimed action onset/offset."""
    first,last=min(event.evidence_frame_indices),max(event.evidence_frame_indices)
    return dict(start_frame=first,end_frame=last+1,start_seconds=str(Fraction(first)/Fraction(fps)),
                end_seconds=str(Fraction(last+1)/Fraction(fps)),boundary_status='sampled_evidence_span_not_exact_event_boundary')


def development_dataset(dataset):
    # All existing media have been exposed during development; never manufacture a holdout.
    data=dataset.model_dump(mode='json'); data['dataset_id']+='-development'; data['frozen']=False
    for case in data['cases']: case['split']='development'
    return type(dataset).model_validate(data)
