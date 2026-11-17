"""Dense motion-aware temporal proposals, not a semantic action oracle."""
from fractions import Fraction
from statistics import median
from .features import nearest


def motion_events(rows,lo,hi):
    region=[r for r in rows if lo<=r.frame_index<hi]
    if len(region)<3:return [],.01
    values=sorted(r.motion for r in region)
    threshold=max(.012,values[len(values)//2]*1.5)
    events=[];start=None;last=None
    for r in region:
        if r.motion>threshold:
            if start is None:start=r.frame_index
            last=r.frame_index
        elif start is not None:
            events.append(dict(start_frame=start,end_frame=r.frame_index,complete_start=start>region[0].frame_index,complete_end=True));start=None
    if start is not None:events.append(dict(start_frame=start,end_frame=region[-1].frame_index+1,complete_start=start>region[0].frame_index,complete_end=False))
    return events,threshold


def choose_cut(decision,duration_frames,media,rows,settings,event_hints=()):
    consumed=Fraction(duration_frames)/Fraction(decision.fps)*Fraction(decision.source_fps)*Fraction(decision.speed)
    if consumed.denominator!=1:raise ValueError('Nonintegral source consumption')
    consumed=int(consumed);total=int(Fraction(media['duration'])*Fraction(media['fps']))
    radius=round(Fraction(settings.search_radius_seconds)*Fraction(media['fps']))
    lo=max(0,decision.source_in_frame-radius);hi=min(total-consumed,decision.source_in_frame+radius)
    if hi<lo:raise ValueError('Action search has no valid interval')
    starts=sorted({lo,hi,max(lo,min(hi,decision.source_in_frame))}|{r.frame_index for r in rows if lo<=r.frame_index<=hi})
    alignment=int(Fraction(decision.source_fps)/Fraction(decision.fps)) if decision.speed=='1' else 1
    phase=int(Fraction(media['start'])*Fraction(media['fps']))%alignment
    starts=[s for s in starts if (s+phase)%alignment==0]
    if not starts:raise ValueError('No timeline-aligned motion cut')
    coarse_seeds=[]
    for hint in event_hints:
        indices=[i for i in hint.get('evidence_frame_indices',[]) if type(i) is int and 0<=i<total]
        if len(set(indices))<2:continue
        for proposed in (min(indices),max(indices),round(sum(indices)/len(indices))-consumed//2):
            clamped=max(lo,min(hi,proposed))
            seed=min(starts,key=lambda value:abs(value-clamped))
            coarse_seeds.append(seed)
    starts=sorted(set(starts)|set(coarse_seeds))
    events,threshold=motion_events(rows,max(0,lo-radius),min(total,hi+consumed+radius))
    active=[r for r in rows if max(0,lo-radius)<=r.frame_index<min(total,hi+consumed+radius)]
    reversals=[]
    for a,b in zip(active,active[1:]):
        if min(a.shift_confidence,b.shift_confidence)>.1 and sum(x*y for x,y in zip(a.image_shift,b.image_shift))<0:reversals.append(b.frame_index)
    def cost(start):
        end=start+consumed;a=nearest(rows,start);b=nearest(rows,end-1)
        distance=abs(start-decision.source_in_frame)/max(1,radius)
        quality=(1/(1+a.sharpness)+1/(1+b.sharpness))*.02
        motion=(a.motion+b.motion)
        if settings.action_strategy=='cut_on_action':strategy=-a.motion
        elif settings.action_strategy=='cut_before_action':strategy=min([abs(start-e['start_frame']+1)/max(1,radius) for e in events if start<e['start_frame']] or [1])+motion*.1
        elif settings.action_strategy=='cut_after_action':strategy=min([abs(start-e['end_frame'])/max(1,radius) for e in events if start>=e['end_frame']] or [1])+motion*.1
        else:
            interruptions=sum(e['start_frame']<start<e['end_frame'] or e['start_frame']<end<e['end_frame'] for e in events)
            strategy=interruptions*.5+motion
        return strategy+quality+distance*.01
    original=max(lo,min(hi,decision.source_in_frame));chosen=min(starts,key=lambda s:(cost(s),abs(s-original)))
    contained=[e for e in events if chosen<=e['start_frame'] and e['end_frame']<=chosen+consumed and e['complete_start'] and e['complete_end']]
    return chosen,consumed,dict(source_clock_alignment_frames=alignment,coarse_event_seed_frames=sorted(set(coarse_seeds)),strategy=settings.action_strategy,search_frames=[lo,hi],sampled_event_candidates=events,event_hints=list(event_hints),direction_changes=reversals,
        threshold=threshold,original_start=decision.source_in_frame,chosen_start=chosen,cost_before=cost(original),cost_after=cost(chosen),
        motion_complete_events_preserved=len(contained),source_end=chosen+consumed,resolution_frames=max([b.frame_index-a.frame_index for a,b in zip(rows,rows[1:])] or [1]),
        caveat='Image-motion intervals can include camera movement; semantic complete action is unverified. Event hints never define exact bounds.')
