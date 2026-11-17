"""Static deterministic framing from detector observations; no invented subject locations."""
from fractions import Fraction
from statistics import median
from .schemas import ReframeDecision


def crop_geometry(width,height,ratio,cx=.5,cy=.5):
    target=Fraction(ratio.replace(':','/'));source=Fraction(width,height)
    if source>=target:w=float(target/source);h=1.0
    else:w=1.0;h=float(source/target)
    x=max(0,min(1-w,cx-w/2));y=max(0,min(1-h,cy-h/2))
    return x,y,w,h


def reframe(index,decision,media,brief,observations):
    relevant=[o for o in observations if o.asset_sha256==decision.asset_id and decision.source_in_frame<=o.frame_index<decision.source_out_frame]
    unions=[];frames=[];counts=[]
    for o in relevant:
        boxes=[b for b in o.boxes if b.confidence>=.6]
        if not boxes:continue
        x=min(b.x for b in boxes);y=min(b.y for b in boxes);r=max(b.x+b.width for b in boxes);bottom=max(b.y+b.height for b in boxes)
        unions.append((x,y,r,bottom));frames.append(o.frame_index);counts.append(len(boxes))
    warnings=[];method='central_fallback';confidence=0;box=None
    center=(.5,.5)
    if len(unions)>=3 and len(set(counts))==1 and len(unions)>=len(relevant)*.7:
        xs=[(b[0]+b[2])/2 for b in unions];ys=[(b[1]+b[3])/2 for b in unions]
        if max(xs)-min(xs)<=.15 and max(ys)-min(ys)<=.15:
            box=(min(b[0] for b in unions),min(b[1] for b in unions),max(b[2] for b in unions),max(b[3] for b in unions))
            center=(median(xs),median(ys));candidate=crop_geometry(media['width'],media['height'],brief.aspect_ratio,*center)
            x,y,w,h=candidate
            if x<=box[0]-.015 and x+w>=box[2]+.015 and y<=max(0,box[1]-.015) and y+h>=min(1,box[3]+.015):
                method='verified_detector_union';confidence=.6
            else:warnings.append('Detected people cannot all fit requested ratio with safety margins; central crop and manual review')
        else:warnings.append('Subject union moves too much for a trustworthy static crop')
    else:warnings.append('Insufficient or inconsistent temporal person detections; central fallback')
    if method=='central_fallback':center=(.5,.5);frames=[];box=None
    crop=crop_geometry(media['width'],media['height'],brief.aspect_ratio,*center)
    x,y,w,h=crop;cx=x+w/2;cy=y+h/2
    # Source-height percentage, matching Apple adjust-transform documentation.
    position=((.5-cx)*media['width']/media['height']*100,(cy-.5)*100)
    warnings.append('No reliable gaze/identity evidence; no gaze-based composition or dynamic tracking asserted')
    return ReframeDecision(decision_index=index,method=method,crop=crop,transform_position=position,confidence=confidence,evidence_frames=frames,subject_box=box,warnings=warnings)
