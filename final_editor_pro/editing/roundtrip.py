"""Read-only canonical comparison for simple FCPXML round-trips, no app automation."""
from fractions import Fraction
from pathlib import Path
from urllib.parse import unquote,urlsplit
import xml.etree.ElementTree as ET
from ..analysis.pipeline import within_project


def q(value):return Fraction(value.removesuffix('s'))


def interpolate(points,time):
    if not points:return None
    if time<=points[0][0]:return points[0][1]
    for (a,x),(b,y) in zip(points,points[1:]):
        if a<=time<=b:return x+(y-x)*(time-a)/(b-a)
    return points[-1][1]


def gain_samples(node,origin,duration):
    adjust=node.find('adjust-volume')
    if adjust is None:return [0.0]*9
    base=float(adjust.get('amount','0dB').removesuffix('dB'))
    param=adjust.find("param[@name='amount']")
    if param is not None:
        if param.get('value'):base=float(param.get('value').removesuffix('dB'))
        keys=param.findall('keyframeAnimation/keyframe')
        if keys:
            points=[(q(k.get('time')),Fraction(k.get('value').removesuffix('dB'))) for k in keys]
            if any(k.get('interp','linear')!='linear' for k in keys):raise ValueError('Nonlinear native gain interpolation requires manual comparison')
            return [float(interpolate(points,origin+duration*Fraction(i,8))) for i in range(9)]
        if param.find('fadeIn') is not None or param.find('fadeOut') is not None:raise ValueError('Native fade element needs manual envelope comparison')
    return [base]*9


def gain_curve(node,origin,duration):
    adjust=node.find('adjust-volume');gain=Fraction(0)
    keys=[]
    if adjust is not None:
        gain=Fraction(adjust.get('amount','0dB').removesuffix('dB'))
        param=adjust.find("param[@name='amount']")
        if param is not None:
            if param.get('value'):gain=Fraction(param.get('value').removesuffix('dB'))
            if param.find('fadeIn') is not None or param.find('fadeOut') is not None:raise ValueError('Native fades require manual curve comparison')
            keys=param.findall('keyframeAnimation/keyframe')
    if keys:
        if any(k.get('interp','linear')!='linear' or k.get('curve','linear')!='linear' for k in keys):raise ValueError('Nonlinear native gain curve requires manual review')
        points=[(q(k.get('time'))-origin,Fraction(k.get('value').removesuffix('dB'))) for k in keys]
        times={Fraction(0),duration}|{t for t,g in points if 0<=t<=duration}
        points=[(t,interpolate(points,t)) for t in sorted(times)]
    else:points=[(Fraction(0),gain),(duration,gain)]
    reduced=[]
    for point in points:
        reduced.append(point)
        while len(reduced)>=3:
            a,b,c=reduced[-3:]
            if abs(float((b[1]-a[1])*(c[0]-b[0])-(c[1]-b[1])*(b[0]-a[0])))<1e-9:reduced.pop(-2)
            else:break
    return [(str(t),float(g)) for t,g in reduced]


def snapshot(path):
    path=within_project(path)
    if path.is_dir():path=path/'Info.fcpxml'
    data=path.read_bytes()
    if b'<!ENTITY' in data.upper() or b'SYSTEM ' in data.upper() or b'PUBLIC ' in data.upper():raise ValueError('External/entity declarations forbidden')
    root=ET.fromstring(data);resources={e.get('id'):e for e in root.findall('./resources/*')}
    seq=root.find('.//sequence')
    if seq is None:raise ValueError('No sequence')
    fmt=resources[seq.get('format')];spine=seq.find('spine')
    if spine is None or any(e.tag!='asset-clip' for e in spine):raise ValueError('Only simple asset-clip primary storyline supported; compare other structures manually')
    def uri(asset):
        rep=asset.find("media-rep[@kind='original-media']")
        if rep is None:raise ValueError('Original reference absent')
        value=rep.get('src');parts=urlsplit(value)
        return 'file://'+unquote(parts.path) if parts.scheme=='file' and parts.netloc in ('','localhost') else unquote(value)
    clips=[];music=[]
    for clip in spine:
        asset=resources[clip.get('ref')];start=q(clip.get('start','0s'));duration=q(clip.get('duration'));offset=q(clip.get('offset','0s'))
        time_map=clip.find('timeMap')
        if time_map is not None:
            points=[(q(p.get('time')),q(p.get('value'))) for p in time_map.findall('timept')]
            if len(points)<2 or any(p.get('interp','smooth2')!='linear' for p in time_map):raise ValueError('Nonlinear/unknown retime requires manual review')
            samples=[interpolate(points,start+duration*Fraction(i,4))-q(asset.get('start','0s')) for i in range(5)]
        else:samples=[start+duration*Fraction(i,4)-q(asset.get('start','0s')) for i in range(5)]
        local_times=sorted({start,start+duration}|({t for t,v in points if start<t<start+duration} if time_map is not None else set()))
        curve_points=[(t-start,interpolate(points,t)-q(asset.get('start','0s'))) for t in local_times] if time_map is not None else [(Fraction(0),samples[0]),(duration,samples[-1])]
        simplified=[]
        for point in curve_points:
            simplified.append(point)
            while len(simplified)>=3:
                a,b,c=simplified[-3:]
                if (b[1]-a[1])*(c[0]-b[0])==(c[1]-b[1])*(b[0]-a[0]):simplified.pop(-2)
                else:break
        source_format=resources.get(asset.get('format'))
        for channel in clip.findall('audio-channel-source'):
            if channel.find('adjust-volume') is not None or channel.find('mute') is not None:raise ValueError('Per-channel native gain/mute needs manual comparison')
        transform=clip.find('adjust-transform');conform=clip.find('adjust-conform')
        if transform is not None and list(transform):raise ValueError('Transform parameter overrides/animation require manual comparison')
        position=[float(v) for v in (transform.get('position','0 0') if transform is not None else '0 0').split()]
        scale=[float(v) for v in (transform.get('scale','1 1') if transform is not None else '1 1').split()]
        clips.append(dict(media=uri(asset),timeline_offset=str(offset),duration=str(duration),source_samples=[str(v) for v in samples],
            speed=str((samples[-1]-samples[0])/duration),source_curve=[(str(t),str(v)) for t,v in simplified],source_frame_duration=str(q(source_format.get('frameDuration'))) if source_format is not None else None,audio_sources=asset.get('audioSources'),audio_channels=asset.get('audioChannels'),audio_rate=asset.get('audioRate'),frame_sampling=time_map.get('frameSampling','floor') if time_map is not None else 'floor',position=position,scale=scale,conform=conform.get('type','fit') if conform is not None else 'fit',
            audio_enabled=clip.get('srcEnable','all')!='video',gain_samples_db=gain_samples(clip,start,duration),gain_curve=gain_curve(clip,start,duration)))
        for item in clip:
            if item.tag=='audio' or (item.tag=='asset-clip' and resources[item.get('ref')].get('hasVideo','0')=='0'):
                a=resources[item.get('ref')];d=q(item.get('duration'));o=q(item.get('offset','0s'))-start+offset;source=q(item.get('start','0s'))
                music.append(dict(media=uri(a),timeline_offset=str(o),duration=str(d),source_start=str(source),gain_samples_db=gain_samples(item,source,d),gain_curve=gain_curve(item,source,d)))
    return dict(duration=str(q(seq.get('duration'))),width=int(fmt.get('width')),height=int(fmt.get('height')),frame_duration=str(q(fmt.get('frameDuration'))),clips=clips,music=music)


def compare(original,returned):
    before=snapshot(original);after=snapshot(returned);differences=[]
    def walk(a,b,path):
        if isinstance(a,dict) and isinstance(b,dict):
            for key in sorted(set(a)|set(b)):walk(a.get(key),b.get(key),path+'/'+key)
        elif isinstance(a,(list,tuple)) and isinstance(b,(list,tuple)):
            if len(a)!=len(b):differences.append(dict(path=path,expected_length=len(a),actual_length=len(b)))
            for i,(x,y) in enumerate(zip(a,b)):walk(x,y,path+'/'+str(i))
        elif isinstance(a,float) and isinstance(b,(int,float)):
            if abs(a-b)>1e-4:differences.append(dict(path=path,expected=a,actual=b))
        elif a!=b:differences.append(dict(path=path,expected=a,actual=b))
    walk(before,after,'')
    return dict(status='match' if not differences else 'differences_require_review',differences=differences,manual_roundtrip_proven=False,
        note='Only the user can attest actual import/reexport. Unsupported structures/envelopes fail explicitly; file equality alone is not a real round-trip.')
