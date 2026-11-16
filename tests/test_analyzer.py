"""Analyzer unit/integration tests. No network, models or private footage required."""
from fractions import Fraction
import json
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from final_editor_pro.analysis.schemas import (AnalysisConfig, AnalysisReport, TemporalInput,
    TemporalFrame, VisualAnalysis, MediaAsset)
from final_editor_pro.analysis.metrics import measure, aggregate, score
from final_editor_pro.analysis.media import sample_indices, boundaries, png
from final_editor_pro.analysis.pipeline import analyze, representative
from final_editor_pro.analysis.ollama import OllamaTemporal, LlamaServerTemporal
from final_editor_pro.ai.providers import LocalProvider, CloudProvider
from final_editor_pro.ai.router import ProcessingRouter, OperationJournal
from final_editor_pro.ai.config import ProcessingConfig, Mode
from final_editor_pro.ai.schemas import Task
from final_editor_pro.ai.privacy import PrivacyPolicy
from ave.core import sha256


def visual(indices=(0,25)):
    return VisualAnalysis(description='Test-only visible subject',people=[],objects=[],environment='unknown',
        actions=[],framing='unknown',apparent_movement='uncertain',atmosphere='unknown',opportunities=[],
        evidence_frame_indices=list(indices),uncertainties=['Sparse temporal samples'],confidence=.5,
        assessments={'visual_relevance':None},assessment_reasons={})


def test_metrics_dark_bright_and_texture():
    width,height=8,8
    dark,g,hist=measure(bytes(width*height*3),width,height)
    bright,_,_=measure(bytes([255])*(width*height*3),width,height)
    texture=bytes(v for y in range(height) for x in range(width) for v in ([255 if (x+y)%2 else 0]*3))
    sharp,_,_=measure(texture,width,height)
    assert dark['dark']==1 and dark['sharpness']==0
    assert bright['bright']==1 and bright['luma']==1
    assert sharp['sharpness']>dark['sharpness']
    metrics=aggregate([dark,bright],[1])
    scored=score(metrics,None,'wedding')
    assert scored.components['narrative_potential'].value is None
    assert 0<scored.available_weight_fraction<1
    assert 'never' in scored.caveat
    with pytest.raises(ValueError): score(metrics,None,'event',{'opaque':2})
    with pytest.raises(ValueError): score(metrics,None,'event',{'technical_quality':float('nan')})


def test_scene_detection_requires_persistence_not_just_motion():
    config=AnalysisConfig(min_scene_seconds='1')
    a=[1.,0.]; b=[0.,1.]
    rows=[dict(frame_index=i*25,histogram=h,difference=1.) for i,h in enumerate([a,a,b,b])]
    assert boundaries(rows,100,'25',config)==[0,50,100]
    # A flash returns to prior histogram and should not become a new scene.
    rows=[dict(frame_index=i*25,histogram=h,difference=1.) for i,h in enumerate([a,a,b,a])]
    assert boundaries(rows,100,'25',config)==[0,100]
    # High pixel motion with unchanged global distribution is not enough.
    rows=[dict(frame_index=i*25,histogram=a,difference=1.) for i in range(4)]
    assert boundaries(rows,100,'25',config)==[0,100]


def test_sampling_exact_budget_and_chronology():
    config=AnalysisConfig(max_frames=8,sample_fps='2')
    indices,stride=sample_indices(1000,'30000/1001',config)
    assert len(indices)<=8 and all(0<=i<1000 for i in indices)
    assert indices==list(range(0,1000,stride))
    assert representative(indices,4)==[0,250,625,875]
    frame=TemporalFrame(frame_index=30,timestamp='1001/1000',data_base64='dGVzdA==')
    TemporalInput(asset_id='a',fps='30000/1001',start_frame=0,end_frame=100,frames=[frame])
    with pytest.raises(ValidationError): TemporalInput(asset_id='a',fps='25',start_frame=0,end_frame=20,frames=[frame])


def test_local_endpoint_and_model_eligibility():
    for endpoint in ['https://api.example.invalid','http://localhost:11435','http://127.0.0.1:11435?key=x']:
        with pytest.raises(ValueError): OllamaTemporal('local',endpoint,'a'*64)
    with pytest.raises(ValueError): OllamaTemporal('model-cloud','http://127.0.0.1:11435','a'*64)


def test_temporal_provider_grounding_and_local_no_remote(tmp_path):
    req=TemporalInput(asset_id='a',fps='25',start_frame=0,end_frame=50,
        frames=[TemporalFrame(frame_index=i,timestamp=str(Fraction(i,25)),data_base64='dGVzdA==') for i in (0,25)])
    local=LocalProvider('local','test-only',{Task.TEMPORAL_VISUAL:lambda request:visual()})
    remote_send=Mock()
    remote=CloudProvider('remote','fake','https://example.invalid',[Task.TEMPORAL_VISUAL],PrivacyPolicy(),remote_send)
    router=ProcessingRouter(ProcessingConfig(),[remote,local],OperationJournal(tmp_path/'log.jsonl'))
    assert router.run(Task.TEMPORAL_VISUAL,req).output.confidence==.5
    remote_send.assert_not_called()
    local._handlers[Task.TEMPORAL_VISUAL]=lambda request:visual((999,))
    with pytest.raises(ValueError,match='unsubmitted'): router.run(Task.TEMPORAL_VISUAL,req)
    remote_send.assert_not_called()
    single=req.model_copy(update={'frames':req.frames[:1]})
    local._handlers[Task.TEMPORAL_VISUAL]=lambda request:visual((0,)).model_copy(update={'actions':['running']})
    with pytest.raises(ValueError,match='two'): router.run(Task.TEMPORAL_VISUAL,single)


def fake_pipeline(tmp_path,monkeypatch):
    from final_editor_pro.analysis import pipeline
    monkeypatch.setattr(pipeline,'ROOT',tmp_path)
    source=tmp_path/'original.mov'; source.write_bytes(b'fake-controlled-video')
    tool=tmp_path/'tool'; tool.write_bytes(b'not-executed')
    facts={'streams':[dict(codec_type='video',width=8,height=8,r_frame_rate='25',avg_frame_rate='25',time_base='1/25',duration_ts=50)]}
    probe=Mock(return_value=facts); monkeypatch.setattr(pipeline,'probe',probe)
    counter=Mock()
    def extraction(asset,config,tool,folder):
        counter(); rows=[]
        for index in (0,25):
            data=png(bytes([100])*8*8*3,8,8); p=folder/f'{index}.png'; p.write_bytes(data)
            metrics,g,hist=measure(bytes([100])*8*8*3,8,8)
            rows.append(dict(frame_index=index,timestamp=str(Fraction(index,25)),image_path=str(p),
                image_sha256=sha256(p),metrics=metrics,histogram=hist,difference=0.))
        return rows,25
    monkeypatch.setattr(pipeline,'extract',extraction)
    return source,tool,counter,probe


def test_pipeline_cache_invalidation_and_source_integrity(tmp_path,monkeypatch):
    source,tool,extractions,probes=fake_pipeline(tmp_path,monkeypatch)
    before=sha256(source)
    kwargs=dict(ffmpeg=tool,ffprobe=tool)
    a=analyze(source,tmp_path/'run1',tmp_path/'cache',**kwargs)
    b=analyze(source,tmp_path/'run2',tmp_path/'cache',**kwargs)
    assert not a.benchmark['cache_hit'] and b.benchmark['cache_hit']
    assert extractions.call_count==1 and probes.call_count==1
    assert a.asset.total_frames==50 and a.segments[0].score.components['action_presence'].value is None
    assert AnalysisReport.model_validate_json((tmp_path/'run1/analysis.json').read_text())==a
    assert sha256(source)==before
    changed=AnalysisConfig(profile='wedding')
    analyze(source,tmp_path/'run3',tmp_path/'cache',changed,**kwargs)
    assert extractions.call_count==1  # scoring change reuses decoded frames
    source.write_bytes(b'changed-test-source')
    analyze(source,tmp_path/'run4',tmp_path/'cache',**kwargs)
    assert extractions.call_count==2
    with pytest.raises(FileExistsError): analyze(source,tmp_path/'run4',tmp_path/'cache',**kwargs)


def test_semantic_failure_is_partial_no_false_success(tmp_path,monkeypatch):
    source,tool,_,_=fake_pipeline(tmp_path,monkeypatch)
    def broken(request): raise RuntimeError('simulated-unavailable-model')
    local=LocalProvider('local','test-only',{Task.TEMPORAL_VISUAL:broken})
    router=ProcessingRouter(ProcessingConfig(),[local],OperationJournal(tmp_path/'ai.jsonl'))
    report=analyze(source,tmp_path/'run',tmp_path/'cache',AnalysisConfig(semantic=True),
        ffmpeg=tool,ffprobe=tool,router=router)
    assert report.benchmark['status']=='partial'
    assert report.segments[0].semantic_status=='failed' and report.segments[0].visual is None
    assert not list((tmp_path/'cache').glob('*.json'))


@pytest.mark.skipif(not Path('/opt/homebrew/bin/ffmpeg').is_file(),reason='Approved FFmpeg unavailable')
def test_synthetic_real_decoder_scene_integration(tmp_path,monkeypatch):
    from final_editor_pro.analysis import pipeline
    monkeypatch.setattr(pipeline,'ROOT',tmp_path)
    path=tmp_path/'two-scenes.mov'
    subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-nostdin','-f','lavfi','-i',
        'color=c=black:s=64x36:r=25:d=2','-f','lavfi','-i','color=c=white:s=64x36:r=25:d=2',
        '-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0','-c:v','mpeg4',str(path)],check=True,timeout=30)
    before=sha256(path)
    report=analyze(path,tmp_path/'output',tmp_path/'cache',AnalysisConfig(proxy_width=64),
        ffmpeg='/opt/homebrew/bin/ffmpeg',ffprobe='/opt/homebrew/bin/ffprobe')
    assert report.asset.total_frames==100 and len(report.segments)==2
    assert report.segments[1].start_frame==52
    assert report.segments[1].boundary_uncertainty_frames==13
    assert sha256(path)==before


def test_cache_corruption_is_not_silently_reused(tmp_path,monkeypatch):
    source,tool,_,_=fake_pipeline(tmp_path,monkeypatch)
    analyze(source,tmp_path/'run1',tmp_path/'cache',ffmpeg=tool,ffprobe=tool)
    cached=next((tmp_path/'cache').glob('*.json'))
    cached.write_text(cached.read_text().replace('Sparse','Changed')+' ')
    with pytest.raises(ValueError,match='integrity'): analyze(source,tmp_path/'run2',tmp_path/'cache',ffmpeg=tool,ffprobe=tool)


def test_sampling_config_and_report_schema_reject_bad_values():
    with pytest.raises(ValidationError): AnalysisConfig(sample_fps='0')
    with pytest.raises(ValidationError): AnalysisConfig(max_frames=1)
    for cls in (MediaAsset,AnalysisReport,TemporalInput): assert cls.model_json_schema()


def test_local_server_schema_forces_grounded_evidence(monkeypatch):
    runner=LlamaServerTemporal('approved','http://127.0.0.1:11435','a'*64)
    req=TemporalInput(asset_id='a',fps='25',start_frame=0,end_frame=50,
        frames=[TemporalFrame(frame_index=i,timestamp=str(Fraction(i,25)),data_base64='dGVzdA==') for i in (0,25)])
    send=Mock(return_value={'choices':[{'finish_reason':'stop','message':{'content':visual().model_dump_json()}}]})
    runner.request=send
    assert runner(req).evidence_frame_indices==[0,25]
    schema=send.call_args.args[1]['response_format']['json_schema']['schema']
    assert schema['properties']['evidence_frame_indices']['items']['enum']==[0,25]
    assert schema['properties']['evidence_frame_indices']['minItems']==2
    send.return_value={'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}
    with pytest.raises(ValueError,match='truncated'): runner(req)


def test_runtime_profile_and_modified_binary_fail_before_start(tmp_path,monkeypatch):
    from final_editor_pro.analysis import runtime
    from final_editor_pro.analysis import pipeline
    monkeypatch.setattr(pipeline,'ROOT',tmp_path)
    profile=runtime.sandbox_profile(tmp_path)
    assert '(deny network*)' in profile and 'localhost:*' in profile and '(deny file-write*)' in profile
    binary=tmp_path/'binary'; binary.write_bytes(b'never-executed')
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'binary':{'path':str(binary),'sha256':'0'*64}}))
    with pytest.raises(PermissionError):
        with runtime.local_server(manifest): pytest.fail('Must not start')


def test_persistent_analysis_config_overrides(tmp_path,monkeypatch):
    from final_editor_pro.analysis import pipeline
    from final_editor_pro.analysis.config import load_analysis_config
    monkeypatch.setattr(pipeline,'ROOT',tmp_path)
    global_file=tmp_path/'global.json'; project_file=tmp_path/'project.json'
    global_file.write_text(json.dumps({'max_frames':10,'score_weights':{'technical_quality':3}}))
    project_file.write_text(json.dumps({'profile':'wedding','score_weights':{'narrative_potential':5}}))
    result=load_analysis_config(global_file,project_file)
    assert result.max_frames==10 and result.profile=='wedding'
    assert result.score_weights=={'technical_quality':3,'narrative_potential':5}
    assert 'profile' not in json.loads(global_file.read_text())
    project_file.write_text('{"unknown":true}')
    with pytest.raises(ValidationError): load_analysis_config(global_file,project_file)
