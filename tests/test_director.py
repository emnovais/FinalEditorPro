from fractions import Fraction
import copy,json,subprocess
from pathlib import Path
import pytest
import xml.etree.ElementTree as ET
from ave.core import metadata,sha256
from final_editor_pro.director.schemas import CreativeBrief,Candidate,NarrativePlan,DirectionRequest,validate_direction,EditDecisionList
from final_editor_pro.director.pipeline import allocate,synchronize,build_edl
from final_editor_pro.director.export import export_edl
from final_editor_pro.director.music import envelope_analysis
from final_editor_pro.ai.schemas import Task
from final_editor_pro.ai.providers import LocalProvider,CloudProvider
from final_editor_pro.ai.router import ProcessingRouter,OperationJournal
from final_editor_pro.ai.config import ProcessingConfig,Mode


def brief(**updates):
    data=dict(project_type='couple',objective='romantic montage',target_seconds='4',aspect_ratio='4:3',fps='25',output_width=3840,output_height=2880,slow_motion_allowed=True,visual_style='romantic',pace='balanced',model_id='qwen3-vl-8b-instruct')
    return CreativeBrief(**(data|updates))


def setup_edit(tmp_path):
    p=tmp_path/'source.mov';p.write_bytes(b'fixture bytes, not actual media')
    m=metadata(p,{'streams':[dict(codec_type='video',r_frame_rate='50',avg_frame_rate='50',time_base='1/50',duration_ts=500,width=3840,height=2160,tags={'timecode':'01:00:00:00'}),dict(codec_type='audio',sample_rate='48000',channels=1,duration_ts=480000,time_base='1/48000'),dict(codec_type='audio',sample_rate='48000',channels=1,duration_ts=480000,time_base='1/48000')]})
    candidates=[Candidate(candidate_id=str(i),asset_id=m['sha256'],segment_id='s',start_frame=i*250,end_frame=(i+1)*250,fps='50',description='smile',technical={},confidence=.6,components={'technical_quality':.5},evidence=[],interpretations=[],warnings=[]) for i in range(2)]
    narrative=NarrativePlan(choices=[dict(candidate_id='0',role='opening',reason='introduce',brief_relation='romantic opening',confidence=.8,speed='1/2'),dict(candidate_id='1',role='ending',reason='end smile',brief_relation='closure',confidence=.7,speed='1')],rationale='variety',warnings=[])
    def refiner(m,c,d,f):return c.start_frame,dict(inspected_frames=[c.start_frame,c.start_frame+d-1])
    edl=build_edl(brief(),[],candidates,narrative,[m],refiner=refiner)
    return m,candidates,narrative,edl


def test_brief_essential_geometry_and_clock():
    assert brief().fps=='25'
    with pytest.raises(ValueError):brief(output_height=2160)
    with pytest.raises(ValueError):brief(target_seconds='1/30')
    with pytest.raises(ValueError):CreativeBrief(objective='missing')


def test_capacity_allocation_and_onset_sync():
    assert sum(allocate([40,200,100],250))==250
    with pytest.raises(ValueError):allocate([10],11)
    durations,notes=synchronize([50,50],[60,60],Fraction(25),{'onsets_seconds':['51/25']})
    assert durations==[51,49] and notes[0]['shift_frames']==1
    assert sum(durations)==100


def test_music_silence_and_variable_tempo():
    assert envelope_analysis([0]*1000)['estimated_bpm'] is None
    energy=[1.0 if i%25==0 else .01 for i in range(1000)]
    r=envelope_analysis(energy)
    assert r['onsets_seconds'] and 60<=r['estimated_bpm']<=180
    assert r['warnings']


def test_narrative_bounds_required_and_duplicates(tmp_path):
    m,c,n,e=setup_edit(tmp_path);req=DirectionRequest(brief=brief(),candidates=c)
    validate_direction(req,n)
    with pytest.raises(ValueError):validate_direction(req,n.model_copy(update={'choices':[n.choices[0],n.choices[0]]}))
    with pytest.raises(ValueError):validate_direction(req.model_copy(update={'brief':brief(required_candidate_ids=['missing'])}),n)
    with pytest.raises(ValueError):validate_direction(req.model_copy(update={'brief':brief(slow_motion_allowed=False)}),n)


def test_edl_retime_rational_bounds_and_audio(tmp_path):
    m,c,n,e=setup_edit(tmp_path)
    assert e.total_frames==100 and e.decisions[0].source_out_frame==50
    assert e.decisions[0].duration_seconds=='2' and e.decisions[0].audio_policy=='mute_slow_motion'
    data=e.model_dump(mode='json');data['decisions'][1]['timeline_start_frame']+=1
    with pytest.raises(ValueError):EditDecisionList.model_validate(data)
    data=e.model_dump(mode='json');data['media'][0]['duration']='1'
    with pytest.raises(ValueError):EditDecisionList.model_validate(data)


def test_export_adapter_dtd_cadence_timecode_and_multichannel(tmp_path):
    m,c,n,e=setup_edit(tmp_path);before=sha256(m['path'])
    xml=export_edl(e);tree=ET.fromstring(xml)
    fmt=tree.find("./resources/format[@id='r_sequence']")
    assert fmt.get('frameDuration')=='1/25s' and fmt.get('height')=='2880' and fmt.get('name') is None
    asset=tree.find('./resources/asset');assert asset.get('audioSources')=='2' and asset.get('audioChannels')=='1'
    clips=tree.findall('.//spine/asset-clip');assert clips[0].get('srcEnable')=='video'
    points=clips[0].findall('timeMap/timept');assert points[0].get('value')=='3600/1s' and points[1].get('value')=='3601/1s'
    assert clips[1].get('start')=='3605/1s' and clips[1].get('srcEnable') is None
    target=tmp_path/'edit.fcpxml';target.write_bytes(xml)
    subprocess.run(['/usr/bin/xmllint','--nonet','--noout','--dtdvalid',str(Path('audit/FCPXMLv1_10.dtd').resolve()),str(target)],check=True,capture_output=True)
    assert sha256(m['path'])==before


def test_connected_music_exact_duration_and_no_source_mutation(tmp_path):
    m,c,n,e=setup_edit(tmp_path);p=tmp_path/'music.wav';p.write_bytes(b'music fixture')
    e=e.model_copy(update={'music':dict(path=str(p),sha256=sha256(p),duration_seconds='10',channels=2,sample_rate=44100)})
    tree=ET.fromstring(export_edl(e));a=tree.find('.//audio');assert a.get('duration')=='4/1s' and a.get('offset')=='0s'
    assert a.find('adjust-volume').get('amount')=='-12dB'
    e=e.model_copy(update={'music':e.music|{'duration_seconds':'1'}})
    with pytest.raises(ValueError):export_edl(e)


def test_missing_modified_media_fails(tmp_path):
    m,c,n,e=setup_edit(tmp_path);Path(m['path']).unlink()
    with pytest.raises(FileNotFoundError):export_edl(e)


def test_local_direction_no_remote_fallback_on_model_failure(tmp_path):
    m,c,n,e=setup_edit(tmp_path);calls=[]
    def fail(r):raise RuntimeError('model unavailable')
    local=LocalProvider('local','qwen',[ ] if False else {Task.DIRECTION:fail})
    class Remote:
        id='remote';model='remote';remote=True;capabilities={Task.DIRECTION}
        def run(self,*a):calls.append(a);raise AssertionError('remote called')
    router=ProcessingRouter(ProcessingConfig(mode=Mode.LOCAL),[local,Remote()],OperationJournal(tmp_path/'ops.jsonl'))
    with pytest.raises(RuntimeError):router.run(Task.DIRECTION,DirectionRequest(brief=brief(),candidates=c))
    assert not calls


def test_shortlist_source_diversity_and_required(tmp_path):
    from final_editor_pro.director.selection import shortlist
    m,c,n,e=setup_edit(tmp_path)
    more=[c[0].model_copy(update={'candidate_id':str(i),'asset_id':str(i%3)}) for i in range(30)]
    selected=shortlist(more,required=['29'],limit=9)
    assert len(selected)==9 and selected[0].candidate_id=='29'
    assert len({c.asset_id for c in selected})==3
    with pytest.raises(ValueError):shortlist(more,['missing'])


def test_natural_brief_missing_fields_and_fabricated_evidence():
    from final_editor_pro.ai.schemas import validate_output
    from final_editor_pro.director.schemas import BriefRequest,BriefInterpretation
    req=BriefRequest(instruction='Faça um vídeo romântico')
    pending=BriefInterpretation(brief=None,missing_fields=['fps','target_seconds'],field_evidence={})
    assert validate_output(Task.BRIEF,req,pending).brief is None
    fabricated=BriefInterpretation(brief=brief(),missing_fields=[],field_evidence={})
    with pytest.raises(ValueError):validate_output(Task.BRIEF,req,fabricated)


def test_refinement_cannot_escape_source_window(tmp_path):
    m,c,n,e=setup_edit(tmp_path)
    with pytest.raises(ValueError):build_edl(brief(),[],c,n,[m],refiner=lambda m,c,d,f:(c.end_frame,{}))


def test_xml_semantic_validation_rejects_wrong_offset(tmp_path):
    from final_editor_pro.director.validation import validate_xml
    m,c,n,e=setup_edit(tmp_path);xml=export_edl(e)
    assert validate_xml(e,xml)
    tree=ET.fromstring(xml);tree.find('.//spine/asset-clip').set('offset','9s')
    with pytest.raises(ValueError):validate_xml(e,ET.tostring(tree))


def test_cloud_direction_requires_payload_consent(tmp_path):
    from final_editor_pro.ai.privacy import PrivacyPolicy
    m,c,n,e=setup_edit(tmp_path);calls=[]
    cloud=CloudProvider('remote','remote','https://example.invalid/api',{Task.DIRECTION},PrivacyPolicy(),lambda *a:calls.append(a))
    router=ProcessingRouter(ProcessingConfig(mode=Mode.CLOUD,allow_uploads=True),[cloud],OperationJournal(tmp_path/'ops.jsonl'))
    with pytest.raises(PermissionError):router.run(Task.DIRECTION,DirectionRequest(brief=brief(),candidates=c))
    assert not calls


def test_bounded_local_plan_correction_uses_same_adapter(tmp_path,monkeypatch):
    from final_editor_pro.director.planning import LocalDirectorAdapter
    m,c,n,e=setup_edit(tmp_path);adapter=LocalDirectorAdapter('model','http://127.0.0.1:11435','a'*64)
    invalid=n.model_copy(update={'choices':[n.choices[0].model_copy(update={'candidate_id':'missing'})]})
    results=iter([invalid,n]);calls=[]
    def generate(req,schema,instruction):
        calls.append(instruction);return next(results)
    monkeypatch.setattr(adapter,'generate',generate)
    result=adapter.plan(DirectionRequest(brief=brief(),candidates=c))
    assert result==n and len(calls)==2
    assert [a['status'] for a in adapter.attempts]==['rejected','accepted']


def test_director_undo_only_generated_unchanged_files(tmp_path):
    from final_editor_pro.director.pipeline import undo_run
    from ave.cli import journal
    out=tmp_path/'run';out.mkdir();p=out/'edl.json';p.write_text('{}')
    journal(out,'created',file=p.name,sha256=sha256(p))
    undo_run(out)
    assert (out/'undone/edl.json').read_text()=='{}'
    out2=tmp_path/'run2';out2.mkdir();p=out2/'edl.json';p.write_text('{}')
    journal(out2,'created',file=p.name,sha256=sha256(p));p.write_text('changed')
    with pytest.raises(ValueError):undo_run(out2)


def test_duration_completion_is_explicit_and_bounded(tmp_path):
    from final_editor_pro.director.selection import complete_duration
    m,c,n,e=setup_edit(tmp_path)
    n=n.model_copy(update={'choices':[n.choices[0].model_copy(update={'speed':'1','role':'opening'})]})
    # A one-choice sketch can be supplemented only if it still has a valid ending.
    b=brief(target_seconds='8')
    n=n.model_copy(update={'choices':[n.choices[0],n.choices[0].model_copy(update={'candidate_id':'1','role':'ending'})]})
    # Here capacity is enough; no invented extra choices.
    result=complete_duration(DirectionRequest(brief=b,candidates=c),n)
    assert len(result.choices)==2
    with pytest.raises(ValueError):complete_duration(DirectionRequest(brief=brief(target_seconds='12'),candidates=c),n)
