"""Candidates preserve coarse semantic evidence without treating it as edit boundaries."""
from fractions import Fraction
import json
from ..analysis.pipeline import within_project
from .schemas import Candidate


def candidates_from_reports(reports,brief,proposal_dir=None):
    results=[]; seen=set()
    for report in reports:
        asset=report.asset
        if asset.asset_id in seen: raise ValueError('Duplicate analysis asset')
        seen.add(asset.asset_id)
        if Fraction(asset.fps)/Fraction(brief.fps) not in (1,2):
            raise ValueError('Only equal fps or explicit 50-to-25 cadence supported')
        proposals=[]
        if proposal_dir:
            for p in sorted(within_project(proposal_dir).glob('clip-*/*-window-*.json')):
                if '.wire.' in p.name: continue
                row=json.loads(p.read_text())
                if row.get('source_sha256')==asset.sha256 and row.get('status')=='success': proposals.append(row)
        for segment in report.segments:
            # Bounded candidate windows, independent of model event-span boundaries.
            size=round(Fraction(asset.fps)*{'slow':6,'balanced':5,'energetic':3}[brief.pace])
            for start in range(segment.start_frame,segment.end_frame,size):
                end=min(start+size,segment.end_frame)
                if end-start<min(size,round(Fraction(asset.fps))): continue
                interpretations=[]
                if segment.visual:
                    interpretations.append(dict(model=segment.model,description=segment.visual.description,confidence=segment.visual.confidence))
                for row in proposals:
                    if any(start<=i<end for i in row['frame_indices']):
                        interpretations.append(dict(model=row['model_id'],description=row['proposal']['description'],confidence=None,
                            events=[e['label'] for e in row.get('observed_event_spans',[]) if any(start<=i<end for i in e['evidence_frame_indices'])]))
                descriptions=[v['description'] for v in interpretations]
                confidence=segment.visual.confidence if segment.visual else .5
                components={k:v.value for k,v in segment.score.components.items()}
                evidence=[dict(frame_index=f.frame_index,image_sha256=f.image_sha256) for f in segment.sampled_frames if start<=f.frame_index<end]
                results.append(Candidate(candidate_id=f'{asset.sha256[:12]}-{start}-{end}',asset_id=asset.asset_id,segment_id=segment.segment_id,
                    start_frame=start,end_frame=end,fps=asset.fps,description=' | '.join(dict.fromkeys(descriptions))[:1600] or 'Semantic description unavailable',
                    technical=segment.technical.model_dump(),confidence=confidence,components=components,evidence=evidence,
                    interpretations=interpretations,warnings=['Interpretations may cover neighboring sampled frames; event evidence is not an exact cut boundary.']))
    if not results: raise ValueError('No candidates')
    if len(results)>100: raise ValueError('Candidate budget exceeded; shorten inputs explicitly')
    return results


def shortlist(candidates,required=(),limit=18):
    """Bound model context by source coverage and temporal diversity, not opaque scores."""
    byid={c.candidate_id:c for c in candidates}
    if not set(required)<=set(byid): raise ValueError('Required candidate does not exist')
    chosen=[byid[i] for i in dict.fromkeys(required)]
    groups={}
    for c in candidates:groups.setdefault(c.asset_id,[]).append(c)
    # Distribute source coverage fairly; prefer distinct temporal positions.
    queues=[]
    for group in groups.values():
        middle=len(group)//2; order=[middle,0,len(group)-1]+list(range(len(group)))
        queues.append([group[i] for i in dict.fromkeys(order)])
    while len(chosen)<limit and any(queues):
        for q in queues:
            if q:
                c=q.pop(0)
                if c not in chosen:chosen.append(c)
                if len(chosen)==limit:break
    if len(required)>limit:raise ValueError('Required candidates exceed context budget')
    return chosen


def complete_duration(request,narrative):
    """Explicit deterministic supplementation of a model ranking; never fake model choices."""
    from .schemas import NarrativeChoice,validate_direction
    validate_direction(request,narrative)
    candidates={c.candidate_id:c for c in request.candidates};choices=list(narrative.choices)
    def available():
        return sum(Fraction(candidates[ch.candidate_id].end_frame-candidates[ch.candidate_id].start_frame)/Fraction(candidates[ch.candidate_id].fps)/Fraction(ch.speed) for ch in choices)
    target=Fraction(request.brief.target_seconds);added=[]
    while available()<target:
        used={ch.candidate_id for ch in choices};sources={candidates[ch.candidate_id].asset_id for ch in choices}
        counts={}
        for ch in choices:
            asset=candidates[ch.candidate_id].asset_id;counts[asset]=counts.get(asset,0)+1
        options=[c for c in request.candidates if c.candidate_id not in used and (request.brief.max_shots_per_asset is None or counts.get(c.asset_id,0)<request.brief.max_shots_per_asset)]
        if not options or len(choices)>=20:raise ValueError('Not enough unique footage for requested duration')
        # Prefer a new source, then more available footage; no single opaque quality score.
        c=max(options,key=lambda c:(c.asset_id not in sources,c.end_frame-c.start_frame,c.confidence))
        choice=NarrativeChoice(candidate_id=c.candidate_id,role='development',speed='1',
            reason='Deterministic duration completion: adds source coverage and footage capacity; '+c.description[:160],
            brief_relation='Completes the requested duration with an additional distinct candidate; manual narrative review required.',confidence=min(c.confidence,.5))
        choices.insert(max(0,len(choices)-1),choice);added.append(c.candidate_id)
    result=narrative.model_copy(update={'choices':choices,'warnings':narrative.warnings+(['Deterministic engine supplemented model ranking for duration: '+', '.join(added)] if added else [])})
    return validate_direction(request,result,check_duration=True)


def unique_source_shortlist(candidates,required=()):
    """Structural diversity: one explicit candidate per file, not only a prompt request."""
    groups={}
    for c in candidates:groups.setdefault(c.asset_id,[]).append(c)
    chosen=[]
    for group in groups.values():
        mandated=[c for c in group if c.candidate_id in required]
        if len(mandated)>1:raise ValueError('Required candidates conflict with single-use source policy')
        def evidence(c):
            events=set(e.casefold() for row in c.interpretations for e in row.get('events',[]))
            blurred=sum('blur' in e or 'out of focus' in e for e in events)
            return (c.end_frame-c.start_frame,-blurred,len(events),-c.start_frame)
        selected=mandated[0] if mandated else max(group,key=evidence)
        selected=selected.model_copy(update={'warnings':selected.warnings+['One candidate per source selected by available duration, blur-event warnings and evidence variety; no aesthetic quality guarantee.']})
        chosen.append(selected)
    if set(required)-{c.candidate_id for c in chosen}:raise ValueError('Required candidate absent')
    return chosen


def assign_boundary_roles(narrative):
    """Deterministic role labels only; preserve model order, choices and speeds."""
    if len(narrative.choices)<2:return narrative
    choices=list(narrative.choices);changes=[]
    for index,role in ((0,'opening'),(len(choices)-1,'ending')):
        if choices[index].role!=role:
            changes.append(f'{index+1}: {choices[index].role}->{role}')
            choices[index]=choices[index].model_copy(update={'role':role})
    return narrative.model_copy(update={'choices':choices,'warnings':narrative.warnings+(['Deterministic boundary role labels: '+', '.join(changes)+'; narrative closure still requires review.'] if changes else [])})
