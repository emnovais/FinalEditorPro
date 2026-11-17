"""Evaluation integrity and abstention, without running a model or fabricating scores."""
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from final_editor_pro.evaluation.schemas import (EvaluationWeights,EvaluationCase,EvaluationDataset,
    HumanReference,HumanFact,Trial,HumanReview)
from final_editor_pro.evaluation.metrics import summary,compare,label_metrics,interval_iou
from final_editor_pro.evaluation.review import create_blind_packet,load_reviews
from final_editor_pro.evaluation.annotation import create_annotation_form
from final_editor_pro.analysis.schemas import VisualAnalysis
from final_editor_pro.analysis.pipeline import fingerprint


def case(**updates):
    base=dict(case_id='case-a',original_path='workspace/source.mov',sha256='a'*64,source_group='group-a',
              fps='25',start_frame=0,end_frame=100)
    return EvaluationCase(**dict(base,**updates))


def output():
    return VisualAnalysis(description='Test-only human-like output',people=[],objects=['cup'],environment='unknown',actions=[],
        framing='unknown',apparent_movement='uncertain',atmosphere='unknown',opportunities=[],evidence_frame_indices=[0],
        uncertainties=['insufficient'],confidence=.5)


def trial(id='t1',model='private-model',condition='warm_inference',**updates):
    out=output()
    base=dict(trial_id=id,model_id=model,case_id='case-a',repetition=0,condition=condition,input_sha256='input',
        protocol_sha256='protocol',status='success',latency_seconds=2.,setup_seconds=4.,server_rss_bytes=1000,
        output=out,response_sha256=fingerprint(out.model_dump(mode='json')))
    return Trial(**dict(base,**updates))


def test_weights_exact_user_values():
    w=EvaluationWeights()
    assert list(w.model_dump().values())==[.25,.25,.20,.15,.10,.05]
    assert sum(w.model_dump().values())==pytest.approx(1)
    with pytest.raises(ValidationError): EvaluationWeights(speed=.5)
    with pytest.raises(ValidationError): EvaluationWeights(visual_precision=float('nan'))


def test_dataset_leakage_even_renamed_group():
    a=case(split='development')
    for second in [case(case_id='b',split='evaluation'),case(case_id='b',source_group='renamed',split='evaluation')]:
        with pytest.raises(ValidationError): EvaluationDataset(dataset_id='x',cases=[a,second])
    with pytest.raises(ValidationError): EvaluationDataset(dataset_id='x',cases=[case()],frozen=True)
    with pytest.raises(ValidationError): HumanReference(status='verified')
    with pytest.raises(ValidationError): case(reference=HumanReference(objects=[HumanFact(label='cup',start_frame=99,end_frame=101)]))


def test_metrics_do_not_call_nonmatch_a_hallucination():
    facts=[HumanFact(label='cup',aliases=['mug'],start_frame=0,end_frame=10)]
    assert label_metrics(['mug'],facts)['recall']==1
    assert label_metrics(['mug','table'],facts)['precision'] is None
    assert label_metrics(['mug','table'],facts,True)['precision']==.5
    assert interval_iou((0,10),(5,15))==pytest.approx(1/3)
    assert summary([1,2,3,4])==dict(n=4,median=2.5,iqr=1.5,min=1,max=4)
    assert summary([None])['median'] is None


def test_missing_human_scores_abstain_instead_of_redistributing():
    dataset=EvaluationDataset(dataset_id='draft',cases=[case()])
    report=compare(dataset,[trial()],{})
    row=report['models'][0]
    assert row['weighted_score'] is None
    assert row['criteria']['visual_precision'] is None and row['criteria']['speed'] is not None
    assert report['conclusion']=='inconclusive' and report['automatic_winner'] is None
    assert 'restaurant' in report['dataset_coverage']['missing_categories']


def test_human_review_binding_and_weighted_score():
    t=trial(); dataset=EvaluationDataset(dataset_id='draft',cases=[case()])
    r=HumanReview(blind_id='b',reviewer='human-test',reviewed_at='2026-11-16',response_sha256=t.response_sha256,
        visual_precision=4,temporal_understanding=2,reliability=3,creative_utility=1,unsupported_claims=0,
        checked_claims=2,uncertainty_notes='test',notes='Human fixture, not real evaluation')
    report=compare(dataset,[t],{t.trial_id:r})
    criteria=report['models'][0]['criteria']
    assert criteria['visual_precision']==1 and criteria['temporal_understanding']==.5
    expected=sum(criteria[k]*v for k,v in EvaluationWeights().model_dump().items())
    assert report['models'][0]['weighted_score']==pytest.approx(expected)
    assert report['conclusion']=='inconclusive'  # no held-out dataset or repetitions
    bad=r.model_copy(update={'response_sha256':'different'})
    with pytest.raises(ValueError): compare(dataset,[t],{t.trial_id:bad})


def test_input_mismatch_and_duplicate_trials_do_not_rank():
    dataset=EvaluationDataset(dataset_id='draft',cases=[case()])
    a,b=trial(),trial(id='t2',model='other',input_sha256='different')
    r=compare(dataset,[a,b],{})
    assert any('Different input' in reason for reason in r['reasons'])
    with pytest.raises(ValueError): compare(dataset,[a,a],{})
    with pytest.raises(ValidationError): trial(response_sha256='changed')


def test_blind_packet_excludes_identity_and_requires_bound_review(tmp_path,monkeypatch):
    from final_editor_pro.analysis import pipeline
    monkeypatch.setattr(pipeline,'ROOT',tmp_path)
    t=trial()
    create_blind_packet([t],tmp_path/'review')
    public=(tmp_path/'review/blind/review.html').read_text()
    assert t.model_id not in public and t.trial_id not in public
    assert 'temperature' not in public and 'model_id' not in public
    rows=json.loads((tmp_path/'review/blind/responses.json').read_text())
    mapping=json.loads((tmp_path/'review/identity-map.private.json').read_text())
    assert mapping[rows[0]['blind_id']]['trial_id']==t.trial_id
    form=tmp_path/'annotation.html'
    create_annotation_form(EvaluationDataset(dataset_id='draft',cases=[case()]),form)
    assert '"status": "pending"' in form.read_text()
    assert 'Test-only human-like output' not in form.read_text()
    assert not list(tmp_path.rglob('*.mov'))


def test_runner_uses_six_real_calls_not_report_cache(tmp_path,monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from final_editor_pro.evaluation import runner
    from final_editor_pro.evaluation.schemas import ModelSpec
    from final_editor_pro.analysis import pipeline
    from final_editor_pro.analysis.schemas import TemporalInput,TemporalFrame
    from ave.core import sha256
    monkeypatch.setattr(pipeline,'ROOT',tmp_path)
    source=tmp_path/'source.mov'; source.write_bytes(b'unit-only')
    c=case(original_path=str(source),sha256=sha256(source),end_frame=100,
           reference=HumanReference(visual_description='DO_NOT_SEND_GROUND_TRUTH'))
    dataset=EvaluationDataset(dataset_id='test',cases=[c])
    request=TemporalInput(asset_id=c.sha256,fps='25',start_frame=0,end_frame=100,
        frames=[TemporalFrame(frame_index=i,timestamp=str(i//25),data_base64='dGVzdA==') for i in (0,25)])
    inputs=tmp_path/'inputs'; inputs.mkdir()
    (inputs/'case-a.json').write_text(json.dumps(dict(case_id='case-a',source_sha256=c.sha256,
        modality='ordered_timestamped_frames',request=request.model_dump(mode='json'),input_sha256=fingerprint(request.model_dump(mode='json')))))
    manifest=tmp_path/'runtime.json'; manifest.write_text(json.dumps({'manifest_sha256':'a'*64,'model_name':'test'}))
    spec=ModelSpec(model_id='test',display_name='test',runtime_manifest=str(manifest),model_digest='a'*64,
                   quantization='unit',license='unit',status='ready')
    sessions=Mock(); calls=Mock()
    @contextmanager
    def server(path,metrics=None,content_only=False):
        assert content_only
        sessions(); metrics.update(load_ready_seconds=.1,integrity_seconds=.2); yield SimpleNamespace(pid=1)
    @contextmanager
    def rss(pid): yield [1000],[0]
    class Adapter:
        def __init__(self,*args): self.protocol_sha256='same'; self.response=None; self.format_normalized=False
        def request(self,*args): return {'data':[]}
        def __call__(self,request):
            assert 'DO_NOT_SEND_GROUND_TRUTH' not in request.model_dump_json()
            calls(); self.response={'usage':{'completion_tokens':10},'timings':{'predicted_per_second':20}}
            return output()
    monkeypatch.setattr(runner,'local_server',server); monkeypatch.setattr(runner,'rss_observer',rss)
    monkeypatch.setattr(runner,'MeasuredTemporal',Adapter)
    trials=runner.run_model(dataset,spec,inputs,tmp_path/'out',3,exploratory=True)
    assert sessions.call_count==3 and calls.call_count==6 and len(trials)==12
    assert sum(t.condition=='report_cache' for t in trials)==6
    assert all(t.output_tokens is None for t in trials if t.condition=='report_cache')
    assert all(t.load_ready_seconds==.1 for t in trials if t.condition!='report_cache')
    assert sha256(source)==c.sha256


def test_reliability_penalizes_observed_failures_without_fabricating_latency():
    dataset=EvaluationDataset(dataset_id='draft',cases=[case()])
    good=trial()
    failed=Trial(trial_id='fail',model_id=good.model_id,case_id='case-a',repetition=1,
        condition='cold_inference',input_sha256='input',protocol_sha256='protocol',status='failed',setup_seconds=2)
    review=HumanReview(blind_id='x',reviewer='human-test',reviewed_at='2026-11-16',response_sha256=good.response_sha256,
        visual_precision=4,temporal_understanding=4,reliability=4,creative_utility=4,unsupported_claims=0,
        checked_claims=1,uncertainty_notes='test',notes='unit fixture')
    row=compare(dataset,[good,failed],{good.trial_id:review})['models'][0]
    assert row['success_rate']==.5 and row['criteria']['reliability']==.5
    assert failed.latency_seconds is None


def test_protocol_is_equivalent_across_model_aliases(monkeypatch):
    from final_editor_pro.evaluation.runner import MeasuredTemporal
    from final_editor_pro.analysis.ollama import LlamaServerTemporal
    captured=[]
    def send(self,path,data=None): captured.append(data); return {'usage':{},'choices':[{'message':{'content':'{}'}}]}
    monkeypatch.setattr(LlamaServerTemporal,'request',send)
    first=MeasuredTemporal('first','http://127.0.0.1:11435','a'*64)
    second=MeasuredTemporal('second','http://127.0.0.1:11435','b'*64)
    payload={'model':'first','messages':[{'content':[{'type':'text','text':'same input'}]}],
             'response_format':{'json_schema':{'schema':{'type':'object'}}}}
    first.request('/v1/chat/completions',payload)
    second.request('/v1/chat/completions',dict(payload,model='second'))
    assert first.protocol_sha256==second.protocol_sha256
    assert 'OUTPUT CONTRACT' in captured[0]['messages'][0]['content'][0]['text']
    assert payload['messages'][0]['content'][0]['text']=='same input'


def test_duplicate_sessions_and_changed_dataset_are_rejected():
    from final_editor_pro.evaluation.schemas import case_signature
    dataset=EvaluationDataset(dataset_id='draft',cases=[case()])
    a=trial(case_signature=case_signature(case()))
    b=trial(id='t2',case_signature=case_signature(case()))
    with pytest.raises(ValueError,match='session'): compare(dataset,[a,b],{})
    changed=EvaluationDataset(dataset_id='changed',cases=[case(end_frame=99)])
    with pytest.raises(ValueError,match='interval'): compare(changed,[a],{})


def test_import_human_notes_preserves_audio_separation_and_no_timestamps(tmp_path,monkeypatch):
    from final_editor_pro.analysis import pipeline
    from final_editor_pro.evaluation.import_reference import import_descriptions
    from ave.core import sha256
    monkeypatch.setattr(pipeline,'ROOT',tmp_path)
    source=tmp_path/'notes.txt'
    source.write_text('Arquivo 1. source.mov\n\nDuas pessoas se olham.\nNo áudio há instruções.\n')
    before=sha256(source)
    dataset=EvaluationDataset(dataset_id='draft',cases=[case()])
    imported,result=import_descriptions(dataset,source,tmp_path/'imported.json')
    ref=imported.cases[0].reference
    assert ref.status=='pending' and ref.objects==[] and ref.actions==[]
    assert 'Duas pessoas' in ref.visual_description and 'instruções' not in ref.visual_description
    assert 'instruções' in ref.audio_notes and 'event_frame_intervals' in ref.pending_fields
    assert ref.source_sha256==before==sha256(source)


def test_only_exact_whole_json_fences_are_normalized(monkeypatch):
    from final_editor_pro.evaluation.runner import MeasuredTemporal
    from final_editor_pro.analysis.ollama import LlamaServerTemporal
    content=['```json\n{}\n```']
    def send(self,path,data=None): return {'choices':[{'message':{'content':content[0]}}]}
    monkeypatch.setattr(LlamaServerTemporal,'request',send)
    adapter=MeasuredTemporal('model','http://127.0.0.1:11435','a'*64)
    assert adapter.request('/v1/chat/completions')['choices'][0]['message']['content']=='{}'
    assert adapter.format_normalized
    content[0]='Prose before\n```json\n{}\n```'
    assert adapter.request('/v1/chat/completions')['choices'][0]['message']['content']==content[0]
    assert not adapter.format_normalized
    assert adapter.response['choices'][0]['message']['content']==content[0]


def test_missing_harder_case_cannot_improve_speed_or_quality_score():
    dataset=EvaluationDataset(dataset_id='draft',cases=[case(),case(case_id='hard',sha256='b'*64,source_group='group-b')])
    good=trial()
    failed=Trial(trial_id='hard-failure',model_id=good.model_id,case_id='hard',repetition=0,
        condition='cold_inference',input_sha256='hard-input',protocol_sha256='hard-protocol',status='failed',setup_seconds=1)
    review=HumanReview(blind_id='x',reviewer='human-test',reviewed_at='2026-11-16',response_sha256=good.response_sha256,
        visual_precision=4,temporal_understanding=4,reliability=4,creative_utility=4,unsupported_claims=0,
        checked_claims=1,uncertainty_notes='test',notes='unit fixture')
    result=compare(dataset,[good,failed],{good.trial_id:review})
    row=result['models'][0]
    assert not row['complete_valid_case_coverage']
    assert row['criteria']['visual_precision'] is None and row['criteria']['speed'] is None
    assert row['weighted_score'] is None


def test_identical_blind_responses_share_one_explicit_human_judgment(tmp_path,monkeypatch):
    from final_editor_pro.analysis import pipeline
    monkeypatch.setattr(pipeline,'ROOT',tmp_path)
    a,b=trial(),trial(id='t2',condition='cold_inference')
    result=create_blind_packet([a,b],tmp_path/'blind')
    assert result['unique_responses']==1 and result['trial_responses']==2
    cards=json.loads((tmp_path/'blind/blind/responses.json').read_text())
    review=HumanReview(blind_id=cards[0]['blind_id'],reviewer='human-test',reviewed_at='2026-11-16',response_sha256=a.response_sha256,
        visual_precision=4,temporal_understanding=4,reliability=4,creative_utility=4,unsupported_claims=0,
        checked_claims=1,uncertainty_notes='test',notes='unit fixture')
    p=tmp_path/'reviews.json';p.write_text(json.dumps([review.model_dump(mode='json')]))
    mapped=load_reviews(p,tmp_path/'blind/identity-map.private.json')
    assert set(mapped)=={'t1','t2'} and mapped['t1'].blind_id==mapped['t2'].blind_id
