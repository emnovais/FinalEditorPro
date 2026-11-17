"""Auditable local refinement pass on a real Director EDL; never touches FCP libraries."""
from fractions import Fraction
from pathlib import Path
import html,json,subprocess
from ave.core import sha256,json_bytes,validate
from ave.cli import journal,probe
from ..analysis.pipeline import within_project,fingerprint
from ..director.schemas import EditDecisionList,EditDecision
from ..director.export import timeline_project
from ..director.validation import validate_xml
from .schemas import EditingPackage,EditingSettings,SubjectObservation
from .features import feature_packet,attach_subjects,inspect_boundaries
from .continuity import optimize,evaluate
from .actions import choose_cut
from .reframing import reframe
from .music import analyze,align,alignment_metric
from .mixing import plan_mix
from .export import export_package


def html_report(package,comparison):
    p=package;rows=[]
    for i,d in enumerate(p.base_edl.decisions):
        values=[i+1,d.role,d.candidate_id,d.source_in_seconds,d.source_out_seconds,d.timeline_start_seconds,d.duration_seconds,d.speed,p.reframing[i].method,p.reframing[i].crop]
        rows.append('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in values)+'</tr>')
    return ('<!doctype html><meta charset="utf-8"><title>Intelligent Editing review</title><style>body{font:16px system-ui;margin:30px;max-width:1400px}td,th{padding:8px;border:1px solid #ccc}table{border-collapse:collapse}pre{white-space:pre-wrap}</style>'
      '<h1>Final Editor Pro — MVP 0.4</h1><p>Montagem experimental. Importação, round-trip e qualidade estética aguardam revisão manual.</p>'
      '<h2>Comparação técnica</h2><pre>'+html.escape(json.dumps(comparison,indent=2,ensure_ascii=False))+'</pre><table><tr>'+''.join('<th>'+v+'</th>' for v in ['#','Papel','Candidato','In fonte(s)','Out fonte(s)','Timeline(s)','Duração(s)','Speed','Reframing','Crop normalizado'])+'</tr>'+''.join(rows)+'</table>'
      '<h2>Alertas de enquadramento</h2>'+''.join('<p>'+html.escape(str(i+1)+': '+'; '.join(r.warnings))+'</p>' for i,r in enumerate(p.reframing))+
      '<h2>Mixagem</h2><pre>'+html.escape(p.mix.model_dump_json(indent=2))+'</pre>')


def enhance(edl_path,output,settings=None,*,subjects_path=None,cache='workspace/editing-cache',proposal_dir=None,reference_edl=None):
    settings=settings or EditingSettings();source=within_project(edl_path);edl=EditDecisionList.model_validate_json(source.read_text())
    out=within_project(output)
    if out.exists():raise FileExistsError('Output must be new')
    out.mkdir(parents=True,mode=0o700)
    def save(name,value):
        data=value if isinstance(value,bytes) else json_bytes(value)
        with (out/name).open('xb') as f:f.write(data)
        journal(out,'created',file=name,sha256=sha256(out/name))
    journal(out,'editing_started',source_edl_sha256=sha256(source),version='0.4.0')
    try:
        media={m['sha256']:m for m in edl.media}
        for m in media.values():within_project(m['path'])
        validate(timeline_project(edl))
        paths=[Path(m['path']) for m in edl.media]+([within_project(edl.music['path'])] if edl.music else [])
        before={str(p):(sha256(p),p.stat().st_size,p.stat().st_mtime_ns) for p in paths}
        if edl.music:
            from ..director.music import source_clock_metadata
            music=dict(edl.music);music.update(source_clock_metadata(probe(within_project(music['path']),'/opt/homebrew/bin/ffprobe')))
            edl=EditDecisionList.model_validate(edl.model_dump(mode='json')|dict(music=music))
            journal(out,'music_clock_reconciled',source_start_seconds=music['source_start_seconds'],clock_kind=music['source_clock_kind'])
        observations=[]
        if subjects_path:
            path=within_project(subjects_path)
            if path.with_suffix('.sha256').read_text()!=sha256(path):raise ValueError('Subject observations changed')
            observations=[SubjectObservation.model_validate(o) for o in json.loads(path.read_text())]
            for o in observations:
                if o.asset_sha256 not in media or o.frame_index>=Fraction(media[o.asset_sha256]['duration'])*Fraction(media[o.asset_sha256]['fps']):raise ValueError('Invalid subject source interval')
        features={};cache_usage={}
        for m in edl.media:
            rows,usage=feature_packet(m,cache)
            features[m['sha256']]=attach_subjects(rows,[o for o in observations if o.asset_sha256==m['sha256']],m['fps']);cache_usage[m['sha256']]=usage
        events=analyze(edl.music['path']) if edl.music else dict(cut_points=[])
        hints={}
        if proposal_dir:
            for p in within_project(proposal_dir).glob('clip-*/*-window-*.json'):
                if '.wire.' in p.name:continue
                r=json.loads(p.read_text())
                if r.get('status')=='success' and r.get('source_sha256') in media:
                    hints.setdefault(r['source_sha256'],[]).extend(r.get('observed_event_spans',[]))
        order=optimize(edl.decisions,features,settings)
        ordered=[edl.decisions[i] for i in order]
        durations,notes=align(ordered,media,events,settings)
        refined=[];actions=[];cursor=0
        for i,(d,duration) in enumerate(zip(ordered,durations)):
            relevant=[h for h in hints.get(d.asset_id,[]) if h.get('start_frame',0)<d.source_out_frame and h.get('end_frame',0)>d.source_in_frame]
            start,consumed,detail=choose_cut(d,duration,media[d.asset_id],features[d.asset_id],settings,relevant)
            detail['exact_boundary_inspection']=inspect_boundaries(media[d.asset_id],start,start+consumed)
            data=d.model_dump(mode='json');data.update(source_in_frame=start,source_out_frame=start+consumed,timeline_start_frame=cursor,duration_frames=duration,
                source_in_seconds=str(Fraction(start)/Fraction(d.source_fps)),source_out_seconds=str(Fraction(start+consumed)/Fraction(d.source_fps)),
                timeline_start_seconds=str(Fraction(cursor)/Fraction(d.fps)),duration_seconds=str(Fraction(duration)/Fraction(d.fps)),
                refinement=detail,music_sync=next((n for n in notes if n['after_decision']==i),None),rationale=d.rationale+' | MVP 0.4: deterministic continuity/action/music refinement, with manual review pending.')
            refined.append(EditDecision.model_validate(data));actions.append(detail);cursor+=duration
        revised=EditDecisionList.model_validate(edl.model_dump(mode='json')|dict(decisions=[d.model_dump(mode='json') for d in refined]))
        frames=[reframe(i,d,media[d.asset_id],edl.brief,observations) for i,d in enumerate(refined)]
        continuity=dict(before=evaluate(edl.decisions,features,settings.intentional_break_after),after=evaluate(refined,features,settings.intentional_break_after),order=order)
        mix=plan_mix(revised,settings)
        package=EditingPackage(base_edl=revised,settings=settings,source_edl_sha256=sha256(source),order=order,action_refinements=actions,reframing=frames,continuity=continuity,music=events,mix=mix,
            provenance=dict(source_edl=str(source),source_version=edl.version,feature_cache=cache_usage,subject_evidence=str(subjects_path) if subjects_path else None,manual_import='pending',round_trip='pending'))
        comparison=dict(source='MVP 0.3 input EDL',duration_preserved_frames=cursor,continuity_before=continuity['before']['mean_compatibility'],continuity_after=continuity['after']['mean_compatibility'],
            music_before=alignment_metric(edl.decisions,events),music_after=alignment_metric(refined,events),
            boundary_cost_before=sum(a['cost_before'] for a in actions),boundary_cost_after=sum(a['cost_after'] for a in actions),
            camera_audio_preserved='Original sources/camera audio remain editable; muted on slow motion as in 0.3',
            caveat='Heuristic comparisons on the same observations/event set; no claim of improved aesthetics or semantic action completion.')
        from .redundancy import audit
        comparison['redundancy_before']=audit(edl);comparison['redundancy_after']=audit(revised)
        if reference_edl:
            reference=EditDecisionList.model_validate_json(within_project(reference_edl).read_text())
            if set(m['sha256'] for m in reference.media)!=set(media):raise ValueError('Reference uses different media')
            comparison['reference']=dict(path=str(reference_edl),continuity=evaluate(reference.decisions,features),music=alignment_metric(reference.decisions,events))
        save('edl.json',package.model_dump(mode='json'))
        xml=export_package(package)
        from .validation import validate_package_xml
        validate_package_xml(package,xml)
        save('timeline.fcpxml',xml);save('comparison.json',comparison);save('review.html',html_report(package,comparison).encode())
        result=subprocess.run(['/usr/bin/xmllint','--nonet','--noout','--dtdvalid',str(within_project('audit/FCPXMLv1_10.dtd')),str(out/'timeline.fcpxml')],capture_output=True,timeout=30)
        if result.returncode:raise ValueError('DTD failed: '+result.stderr.decode()[:1000])
        for path,state in before.items():
            p=Path(path)
            if (sha256(p),p.stat().st_size,p.stat().st_mtime_ns)!=state:raise ValueError('Original changed')
        save('validation.json',dict(dtd_valid=True,xml_matches_edl=True,originals_unchanged=True,manual_import='pending',round_trip='pending'))
        journal(out,'editing_complete');return package
    except Exception as exc:
        journal(out,'editing_failed',error=type(exc).__name__);raise
