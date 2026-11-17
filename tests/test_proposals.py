import pytest
from final_editor_pro.evaluation.proposals import WindowProposal, event_interval, development_dataset
from final_editor_pro.evaluation.schemas import EvaluationDataset

def test_grounded_evidence_and_fraction_clock():
    p=WindowProposal(description='movement',events=[dict(label='turn',evidence_frame_indices=[0,50],confidence=.5,uncertainty='sampled')],categories=['people_motion'],uncertainties=['no audio'])
    p.grounded([0,50])
    assert event_interval(p.events[0],'50')['end_seconds']=='51/50'
    with pytest.raises(ValueError): p.grounded([0,25])
    bad=p.model_copy(update={'events':[p.events[0].model_copy(update={'evidence_frame_indices':[0,0]})]})
    with pytest.raises(ValueError): bad.grounded([0])

def test_development_assignment_never_verifies_reference():
    d=EvaluationDataset(dataset_id='test',cases=[dict(case_id='a',original_path='x',sha256='a'*64,source_group='session',fps='50',start_frame=0,end_frame=100)])
    new=development_dataset(d)
    assert new.cases[0].split=='development'
    assert new.cases[0].reference.status=='pending' and not new.frozen
    assert d.cases[0].split=='unassigned'
