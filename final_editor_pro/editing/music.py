"""Local music events: observed onset chains, energy sections and pauses."""
from array import array
from fractions import Fraction
import math,subprocess,sys
from ave.core import sha256
from ..analysis.pipeline import within_project
from ..director.music import envelope_analysis


def events_from_energy(energy,rate=50):
    base=envelope_analysis(energy,rate);onsets=[round(Fraction(t)*rate) for t in base['onsets_seconds']]
    maximum=max(energy,default=0);pauses=[];start=None
    for i,v in enumerate(energy+[maximum]):
        if v<=maximum*.04 and maximum>0:
            if start is None:start=i
        elif start is not None:
            if i-start>=round(rate*.2):pauses.append(dict(start_seconds=str(Fraction(start,rate)),end_seconds=str(Fraction(i,rate))))
            start=None
    # Track actual attacks near a locally estimated period; never extrapolate a
    # global fixed BPM through pauses/tempo changes.
    beats=[];last=None;period=None
    for index in onsets:
        window=max(0,index-rate*4);local=[i for i in onsets if window<=i<index]
        intervals=[b-a for a,b in zip(local,local[1:]) if rate/3<=b-a<=rate]
        if intervals:period=sorted(intervals)[len(intervals)//2]
        if period and (last is None or abs(index-last-period)<=period*.25):
            beats.append(dict(seconds=str(Fraction(index,rate)),confidence=.5,local_period_seconds=str(Fraction(period,rate)),kind='observed_beat_candidate'));last=index
        elif last is not None and period and index-last>period*1.5:last=None
    blocks=[sum(energy[i:i+rate])/len(energy[i:i+rate]) for i in range(0,len(energy),rate)]
    sections=[]
    for i in range(2,len(blocks)-1):
        before=sum(blocks[i-2:i])/2;after=sum(blocks[i:i+2])/2
        delta=20*math.log10((after+1e-8)/(before+1e-8))
        if abs(delta)>=4 and (not sections or i-float(Fraction(sections[-1]['seconds']))>=2):
            sections.append(dict(seconds=str(i),delta_db=delta,kind='energy_section_change',confidence=.4))
    points=[dict(seconds=t,kind='onset',confidence=.35) for t in base['onsets_seconds']]
    points+=beats+sections
    points += [dict(seconds=p['start_seconds'],kind='pause_start',confidence=.5) for p in pauses]
    points.sort(key=lambda p:Fraction(p['seconds']))
    return dict(version='0.4.0',onsets=base['onsets_seconds'],observed_beat_candidates=beats,pauses=pauses,energy_sections=sections,intensity_envelope_1s=blocks,
        cut_points=points,estimated_bpm=base['estimated_bpm'],stable_tempo_supported=base['stable_tempo_supported'],
        caveats=['Energy sections are not semantic verse/chorus labels.','Observed beat candidates can miss syncopation or half/double tempo; not a verified tempo map.'])


def analyze(path,ffmpeg='/opt/homebrew/bin/ffmpeg'):
    p=within_project(path);before=sha256(p)
    raw=subprocess.run([ffmpeg,'-v','error','-nostdin','-protocol_whitelist','file','-i',str(p),'-map','0:a:0','-t','900','-vn','-ac','1','-ar','8000','-f','s16le','pipe:1'],capture_output=True,check=True,timeout=180).stdout
    pcm=array('h');pcm.frombytes(raw)
    if sys.byteorder!='little':pcm.byteswap()
    energy=[math.sqrt(sum((x/32768)**2 for x in pcm[i:i+160])/len(pcm[i:i+160])) for i in range(0,len(pcm),160)]
    result=events_from_energy(energy)
    if sha256(p)!=before:raise ValueError('Music changed')
    result.update(source_sha256=before,decoded_seconds=str(Fraction(len(pcm),8000)))
    return result


def align(decisions,media,events,settings):
    durations=[d.duration_frames for d in decisions];fps=Fraction(decisions[0].fps);total=sum(durations)
    tolerance=round(Fraction(settings.music_tolerance_seconds)*fps);minimum=round(Fraction(settings.min_shot_seconds)*fps)
    notes=[]
    points=[Fraction(e['seconds']) for e in events.get('cut_points',[])]
    indices=sorted(range(len(durations)-1),key=lambda i:min([abs(Fraction(sum(durations[:i+1]))/fps-p) for p in points] or [Fraction(0)]),reverse=True)
    budget=(len(durations)-1+1)//2 # At most half the boundaries; spend budget on largest benefit.
    for i in indices:
        if len(notes)>=budget:break
        boundary=sum(durations[:i+1]);options=[]
        for e in events.get('cut_points',[]):
            point=round(Fraction(e['seconds'])*fps);shift=point-boundary
            if abs(shift)<=tolerance:
                options.append((abs(shift)-(.5 if e['kind'] in ('pause_start','energy_section_change') else 0),point,e))
        for _,point,event in sorted(options,key=lambda o:(o[0],o[1])):
            delta=point-boundary;left=durations[i]+delta;right=durations[i+1]-delta
            if min(left,right)<minimum:continue
            valid=True
            for d,length in ((decisions[i],left),(decisions[i+1],right)):
                consumed=Fraction(length)/fps*Fraction(d.source_fps)*Fraction(d.speed)
                available=Fraction(media[d.asset_id]['duration'])*Fraction(d.source_fps)-d.source_in_frame
                if consumed.denominator!=1 or consumed>available:valid=False
            if valid and delta!=0:
                durations[i]=left;durations[i+1]=right
                notes.append(dict(after_decision=i,timeline_frame=point,shift_frames=delta,event=event));break
    assert sum(durations)==total
    return durations,notes


def alignment_metric(decisions,events):
    points=[Fraction(p['seconds']) for p in events.get('cut_points',[])]
    if not points:return None
    fps=Fraction(decisions[0].fps);cursor=0;distances=[]
    for d in decisions[:-1]:
        cursor+=d.duration_frames;time=Fraction(cursor)/fps
        distances.append(float(min(abs(time-p) for p in points)))
    return dict(mean_distance_seconds=sum(distances)/len(distances) if distances else 0,distances_seconds=distances,metric='Distance to nearest same-set music event; not aesthetic quality')
