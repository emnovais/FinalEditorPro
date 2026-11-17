"""Explainable compatibility proxies; deliberate cuts can opt out."""
import itertools,math
from ..analysis.metrics import hist_distance
from .features import nearest


def pair(left,right,features,*,intentional=False):
    a=nearest(features[left.asset_id],left.source_out_frame-1);b=nearest(features[right.asset_id],right.source_in_frame)
    if intentional:return dict(compatibility=1.0,components={},intentional_break=True,warning='Deliberate cut excluded from optimization')
    components={}
    def add(name,value,weight,reason):components[name]=dict(value=max(0,min(1,value)),weight=weight,reason=reason)
    add('luminance',1-abs(a.luma-b.luma),1,'Absolute proxy luma difference; not color-managed exposure')
    add('histogram',1-hist_distance(a.histogram,b.histogram),1,'Proxy intensity histogram similarity')
    mad=sum(abs(x-y) for x,y in zip(a.thumbnail,b.thumbnail))/len(a.thumbnail)
    add('composition_similarity',1-mad,1,'Low-resolution image layout similarity, not semantic composition')
    ax,ay=a.image_shift;bx,by=b.image_shift
    if min(a.shift_confidence,b.shift_confidence)>.08 and math.hypot(ax,ay)*math.hypot(bx,by)>0:
        cosine=(ax*bx+ay*by)/(math.hypot(ax,ay)*math.hypot(bx,by))
        add('apparent_image_direction',(cosine+1)/2,.35,'Global pixel shift proxy; does not establish camera versus subject motion')
    if a.subject_position is not None and b.subject_position is not None:
        distance=math.dist(a.subject_position,b.subject_position)
        add('subject_position',1-distance/1.414,.5,'Detected person-union centroid, without identity or gaze inference')
        add('subject_scale',1-abs(a.subject_area-b.subject_area),.4,'Detected union area as apparent shot-scale proxy')
    overlap=max(0,min(left.source_out_frame,right.source_out_frame)-max(left.source_in_frame,right.source_in_frame)) if left.asset_id==right.asset_id else 0
    fraction=overlap/max(1,min(left.source_out_frame-left.source_in_frame,right.source_out_frame-right.source_in_frame))
    add('nonredundancy',1-fraction,.6,'Repeated source intervals; visual similarity alone is not a reason to reject a shot')
    if left.asset_id==right.asset_id:
        add('source_chronology',float(right.source_in_frame>=left.source_in_frame),.2,'Soft preference only; nonchronological storytelling may be intentional')
    score=sum(c['value']*c['weight'] for c in components.values())/sum(c['weight'] for c in components.values())
    return dict(compatibility=score,components=components,intentional_break=False,unavailable=['physical_camera_motion','gaze_direction','semantic_shot_scale_without_subject_evidence'])


def evaluate(decisions,features,intentional=()):
    pairs=[dict(cut=i,**pair(a,b,features,intentional=i in intentional)) for i,(a,b) in enumerate(zip(decisions,decisions[1:]))]
    eligible=[p['compatibility'] for p in pairs if not p['intentional_break']]
    return dict(mean_compatibility=sum(eligible)/len(eligible) if eligible else None,pairs=pairs,meaning='Compatibility heuristic, not aesthetic quality')


def optimize(decisions,features,settings):
    n=len(decisions);original=list(range(n))
    if not settings.allow_reorder or settings.continuity_weight==0:return original
    fixed={0,n-1}|{i for i,d in enumerate(decisions) if d.role=='highlight'}
    free=[i for i in range(n) if i not in fixed]
    if len(free)>7:return original # Explicit bounded search, no silent approximate claim.
    def score(order):
        compat=evaluate([decisions[i] for i in order],features,settings.intentional_break_after)['mean_compatibility'] or 0
        displacement=sum(abs(i-j) for i,j in enumerate(order))/(max(1,n*n))
        return settings.continuity_weight*compat-(1-settings.continuity_weight)*.1*displacement
    best=original;best_score=score(original)
    for permutation in itertools.permutations(free):
        order=original.copy()
        for index,value in zip(free,permutation):order[index]=value
        value=score(order)
        if value>best_score+1e-10:best,best_score=order,value
    return best
