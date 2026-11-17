"""Reviewable creative direction with exact clocks and exclusive local outputs."""
from fractions import Fraction
import html,json
from pathlib import Path
import subprocess
from ave.core import sha256,json_bytes,validate
from ave.cli import probe,journal
from ..analysis.pipeline import within_project,fingerprint
from ..analysis.schemas import AnalysisReport
from ..ai.schemas import Task
from .schemas import CreativeBrief,DirectionRequest,EditDecision,EditDecisionList
from .selection import candidates_from_reports,shortlist
from .refinement import refine
from .music import analyze_music
from .export import export_edl,timeline_project


def allocate(capacities,total):
    if total< len(capacities) or sum(capacities)<total: raise ValueError('Insufficient capacity/target')
    allocation=[min(cap,total//len(capacities)) for cap in capacities]
    remaining=total-sum(allocation)
    while remaining:
        active=[i for i,c in enumerate(capacities) if allocation[i]<c]
        if not active: raise ValueError('Insufficient source duration')
        step=max(1,remaining//len(active))
        for i in active:
            delta=min(step,capacities[i]-allocation[i],remaining)
            allocation[i]+=delta;remaining-=delta
    return allocation


def synchronize(durations,capacities,fps,music):
    durations=list(durations); notes={}
    if not music: return durations,notes
    # Sparse onsets, not an assumed globally stable tempo. Only internal boundaries.
    points=[round(Fraction(t)*fps) for t in music['onsets_seconds']]
    for i in range(len(durations)-1):
        if i%2: continue
        boundary=sum(durations[:i+1]); options=sorted(points,key=lambda p:abs(p-boundary))
        for point in options:
            delta=point-boundary
            if abs(delta)>round(fps*Fraction(3,20)): break
            if 1<=durations[i]+delta<=capacities[i] and 1<=durations[i+1]-delta<=capacities[i+1]:
                durations[i]+=delta;durations[i+1]-=delta
                notes[i]=dict(kind='nearby_energy_onset',timeline_frame=point,shift_frames=delta,confidence='heuristic')
                break
    return durations,notes


def build_edl(brief,reports,candidates,narrative,media,*,refiner=refine,folder=None,music=None,provider=None):
    from .schemas import validate_direction
    validate_direction(DirectionRequest(brief=brief,candidates=candidates),narrative,check_duration=True)
    fps=Fraction(brief.fps); target=int(Fraction(brief.target_seconds)*fps)
    byid={c.candidate_id:c for c in candidates}; sources={m['sha256']:m for m in media}
    capacities=[int(Fraction(byid[ch.candidate_id].end_frame-byid[ch.candidate_id].start_frame)/Fraction(byid[ch.candidate_id].fps)/Fraction(ch.speed)*fps) for ch in narrative.choices]
    durations=allocate(capacities,target);durations,sync=synchronize(durations,capacities,fps,music)
    decisions=[];cursor=0
    for i,(choice,duration) in enumerate(zip(narrative.choices,durations)):
        c=byid[choice.candidate_id]; m=sources[c.asset_id]
        consumed=Fraction(duration)/fps*Fraction(c.fps)*Fraction(choice.speed)
        if consumed.denominator!=1: raise ValueError('Retime is not source-frame aligned')
        start,details=refiner(m,c,int(consumed),folder)
        end=start+int(consumed)
        if not c.start_frame<=start<end<=c.end_frame: raise ValueError('Refinement escaped candidate')
        decisions.append(EditDecision(candidate_id=c.candidate_id,asset_id=c.asset_id,segment_id=c.segment_id,
            source_in_frame=start,source_out_frame=end,timeline_start_frame=cursor,duration_frames=duration,
            fps=brief.fps,source_fps=c.fps,speed=choice.speed,audio_policy='preserve' if choice.speed=='1' else 'mute_slow_motion',
            source_in_seconds=str(Fraction(start)/Fraction(c.fps)),source_out_seconds=str(Fraction(end)/Fraction(c.fps)),
            timeline_start_seconds=str(Fraction(cursor)/fps),duration_seconds=str(Fraction(duration)/fps),role=choice.role,
            rationale=choice.reason,brief_relation=choice.brief_relation,confidence=min(c.confidence,choice.confidence),
            score_components=c.components,refinement=details,music_sync=sync.get(i)))
        cursor+=duration
    return EditDecisionList(brief=brief,media=media,decisions=decisions,total_frames=target,music=music,
        planning=dict(provider=provider,narrative=narrative.model_dump(mode='json'),report_sha256=[fingerprint(r.model_dump(mode='json')) for r in reports]),
        warnings=narrative.warnings+['Central fill crop/upscale requires framing review.','50 fps to 25 fps: normal clips drop alternate source frames; half-speed uses every source frame.',
        'Original camera audio is muted only in half-speed clips; music gain -12 dB is provisional.',
        'Heuristic cut refinement does not guarantee complete actions or visual quality.','Model confidence is not calibrated; subjective constraints require manual review.'])


def review_html(edl):
    rows=[]
    for d in edl.decisions:
        rows.append('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in (d.role,d.candidate_id,d.source_in_seconds,d.source_out_seconds,d.timeline_start_seconds,d.duration_seconds,d.speed,d.audio_policy,d.rationale,d.brief_relation,d.confidence))+'</tr>')
    return ('<!doctype html><meta charset="utf-8"><title>Creative Director review</title><style>body{font:15px system-ui;margin:25px}td,th{border:1px solid #ccc;padding:8px}table{border-collapse:collapse}li{margin:8px}</style>'
      '<h1>Final Editor Pro — revisão da montagem</h1><p>Primeira montagem automática; qualidade visual e importação ainda não confirmadas.</p>'
      '<p>'+html.escape(edl.brief.model_dump_json())+'</p><p>Música: '+html.escape(edl.music['path'] if edl.music else 'nenhuma')+'</p>'
      '<p>Decisões com confiança ≤ 0,6: '+str(sum(d.confidence<=.6 for d in edl.decisions))+'</p>'
      '<p>Duração: '+str(Fraction(edl.total_frames)/Fraction(edl.brief.fps))+' s</p><ul>'+''.join('<li>'+html.escape(w)+'</li>' for w in edl.warnings)+'</ul>'
      '<table><tr>'+''.join('<th>'+x+'</th>' for x in ('Papel','Candidato','In fonte (s)','Out fonte (s)','Timeline (s)','Duração (s)','Velocidade','Áudio','Motivo','Briefing','Confiança'))+'</tr>'+''.join(rows)+'</table>')


def run_director(brief,report_paths,output,router,*,proposal_dir=None,consent=None,ffprobe='/opt/homebrew/bin/ffprobe',ffmpeg='/opt/homebrew/bin/ffmpeg'):
    brief=CreativeBrief.model_validate(brief);out=within_project(output)
    if out.exists(): raise FileExistsError('Director output must be new')
    out.mkdir(parents=True,mode=0o700)
    def save(name,value):
        data=value if isinstance(value,bytes) else json_bytes(value)
        with (out/name).open('xb') as f:f.write(data)
        journal(out,'created',file=name,sha256=sha256(out/name))
    journal(out,'director_started',brief_sha256=fingerprint(brief.model_dump(mode='json')))
    try:
        reports=[AnalysisReport.model_validate_json(within_project(p).read_text()) for p in report_paths]
        media=[r.asset.metadata for r in reports]
        for m in media:within_project(m['path'])
        from ave.core import plan
        base=plan(media); validate(base)
        for r in reports:
            if within_project(r.asset.original_path)!=within_project(r.asset.metadata['path']) or r.asset.sha256!=r.asset.metadata['sha256'] or any(str(getattr(r.asset,k))!=str(r.asset.metadata[k]) for k in ('fps','duration','width','height')): raise ValueError('Report media binding mismatch')
        before={m['path']:(sha256(m['path']),Path(m['path']).stat().st_size,Path(m['path']).stat().st_mtime_ns) for m in media}
        music=None
        if brief.music_path:
            music=analyze_music(brief.music_path,ffmpeg)
            stream=next(s for s in probe(within_project(brief.music_path),ffprobe)['streams'] if s['codec_type']=='audio')
            if Fraction(stream.get('start_time','0'))!=0:raise ValueError('Music source PTS requires explicit reconciliation')
            exact_duration=Fraction(int(stream['duration_ts']))*Fraction(stream['time_base']) if 'duration_ts' in stream and 'time_base' in stream else Fraction(stream['duration'])
            music.update(channels=int(stream['channels']),sample_rate=int(stream['sample_rate']),duration_seconds=str(exact_duration))
            from .schemas import MusicAnalysis
            music=MusicAnalysis.model_validate(music).model_dump(mode='json')
            if Fraction(music['duration_seconds'])<Fraction(brief.target_seconds): raise ValueError('Music is shorter than requested edit')
            save('music-analysis.json',music)
        candidates=candidates_from_reports(reports,brief,proposal_dir)
        save('all-candidates.json',[c.model_dump(mode='json') for c in candidates])
        candidates=shortlist(candidates,brief.required_candidate_ids)
        request=DirectionRequest(brief=brief,candidates=candidates)
        selected=router.select(Task.DIRECTION)
        if not selected.model.startswith(brief.model_id) and brief.model_id not in selected.id: raise ValueError('Selected provider differs from brief model')
        save('brief.json',brief.model_dump(mode='json'));save('candidates.json',[c.model_dump(mode='json') for c in candidates])
        handler=getattr(selected,'_handlers',{}).get(Task.DIRECTION)
        adapter=getattr(handler,'__self__',None)
        try:
            narrative=router.run(Task.DIRECTION,request,consent).output
        finally:
            if adapter is not None and hasattr(adapter,'attempts'):save('planning-attempts.private.json',adapter.attempts)
        from .selection import complete_duration
        save('model-narrative.json',narrative.model_dump(mode='json'))
        narrative=complete_duration(request,narrative)
        save('narrative.json',narrative.model_dump(mode='json'))
        edl=build_edl(brief,reports,candidates,narrative,media,folder=out,music=music,provider=dict(id=selected.id,model=selected.model))
        save('edl.json',edl.model_dump(mode='json'));save('project-source-cuts.json',timeline_project(edl))
        from .validation import validate_xml
        xml=export_edl(edl); validate_xml(edl,xml)
        save('timeline.fcpxml',xml);save('review.html',review_html(edl).encode())
        result=subprocess.run(['/usr/bin/xmllint','--nonet','--noout','--dtdvalid',str(within_project('audit/FCPXMLv1_10.dtd')),str(out/'timeline.fcpxml')],capture_output=True,timeout=30)
        if result.returncode: raise ValueError('Official Apple DTD validation failed: '+result.stderr.decode()[:1500])
        validate(timeline_project(edl))
        for path,state in before.items():
            p=Path(path)
            if (sha256(p),p.stat().st_size,p.stat().st_mtime_ns)!=state: raise ValueError('Original changed')
        save('validation.json',dict(apple_dtd='1.10',valid=True,originals_unchanged=True,total_frames=edl.total_frames,fps=brief.fps,manual_final_cut_import='pending'))
        journal(out,'director_complete');return edl
    except Exception as exc:
        journal(out,'director_failed',error=type(exc).__name__);raise


def undo_run(output):
    """Park generated artifacts after checksum validation; never touch media."""
    out=within_project(output)
    rows=[json.loads(line) for line in (out/'operations.jsonl').read_text().splitlines()]
    created=[r for r in rows if r['action']=='created']
    allowed={'model-narrative.json','planning-attempts.private.json','music-analysis.json','all-candidates.json','candidates.json','brief.json','narrative.json','edl.json','project-source-cuts.json','timeline.fcpxml','review.html','validation.json'}
    for row in created:
        if row['file'] not in allowed:raise ValueError('Unknown generated artifact')
        path=out/row['file']
        if path.is_symlink() or sha256(path)!=row['sha256']:raise ValueError('Artifact changed; refusing undo')
    parked=out/'undone';parked.mkdir(mode=0o700)
    for row in created:(out/row['file']).rename(parked/row['file'])
    journal(out,'director_undo_complete')


def publish_existing_edl(edl,output):
    """Deterministic republication of existing decisions; never calls a model."""
    from .validation import validate_xml
    edl=EditDecisionList.model_validate(edl);out=within_project(output)
    if out.exists():raise FileExistsError('Output must be new')
    xml=export_edl(edl);validate_xml(edl,xml)
    out.mkdir(parents=True,mode=0o700)
    journal(out,'republish_existing_edl',edl_sha256=fingerprint(edl.model_dump(mode='json')),model_called=False)
    for name,data in [('edl.json',json_bytes(edl.model_dump(mode='json'))),('timeline.fcpxml',xml),('review.html',review_html(edl).encode())]:
        with (out/name).open('xb') as f:f.write(data)
        journal(out,'created',file=name,sha256=sha256(out/name))
    result=subprocess.run(['/usr/bin/xmllint','--nonet','--noout','--dtdvalid',str(within_project('audit/FCPXMLv1_10.dtd')),str(out/'timeline.fcpxml')],capture_output=True,timeout=30)
    if result.returncode:raise ValueError('Official DTD failed')
    validate(timeline_project(edl));journal(out,'director_complete',dtd_valid=True)
    return out
