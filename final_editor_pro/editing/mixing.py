"""Editable gain/envelopes with conservative sample-peak headroom, no source writes."""
import math,re,subprocess
from fractions import Fraction
from .schemas import AudioEnvelope,MixPlan
from ..analysis.pipeline import within_project


def sample_peak(path,start='0',duration=None,ffmpeg='/opt/homebrew/bin/ffmpeg'):
    path=within_project(path)
    command=[ffmpeg,'-hide_banner','-nostdin','-protocol_whitelist','file','-ss',str(float(Fraction(start))),'-i',str(path),'-vn','-map','0:a']
    if duration is not None:command+=['-t',str(float(Fraction(duration)))]
    command+=['-af','astats=metadata=0:reset=0','-f','null','-']
    result=subprocess.run(command,capture_output=True,check=True,timeout=180)
    matches=re.findall(r'Peak level dB:\s*(-?inf|[-+\d.]+)',result.stderr.decode(errors='replace'))
    if not matches:raise ValueError('Audio sample peak not measured')
    return max([-120 if 'inf' in v else float(v) for v in matches])


def envelope(duration,gain,fade,priority=(),duck=0):
    duration=Fraction(duration);fade=min(Fraction(fade),duration/2)
    points={Fraction(0),duration}
    if fade:points|={fade,duration-fade}
    ranges=[]
    for a,b in priority:
        a=max(Fraction(0),Fraction(a));b=min(duration,Fraction(b))
        if a>=b:continue
        ranges.append((a,b))
        points|={max(Fraction(0),a-fade),a,b,min(duration,b+fade)}
    def amount(t):
        value=gain
        if fade and t<fade:value=-96+(gain+96)*float(t/fade)
        if fade and t>duration-fade:value=min(value,-96+(gain+96)*float((duration-t)/fade))
        depth=0
        for a,b in ranges:
            if a<=t<=b:depth=1
            elif fade and a-fade<t<a:depth=max(depth,float((t-(a-fade))/fade))
            elif fade and b<t<b+fade:depth=max(depth,float((b+fade-t)/fade))
        return max(-96,value+duck*depth)
    return AudioEnvelope(points=[(str(t),amount(t)) for t in sorted(points)])


def plan_mix(edl,settings,peak_reader=sample_peak):
    media={m['sha256']:m for m in edl.media};measurements={};bounds=[]
    for i,d in enumerate(edl.decisions):
        if d.audio_policy!='preserve' or not media[d.asset_id]['audio_channels']:
            bounds.append(0);continue
        m=media[d.asset_id];peak=peak_reader(m['path'],d.source_in_seconds,d.duration_seconds)
        # Worst-case simultaneous sum of every source channel, independent of pan.
        channels=m['audio_channels']*m.get('audio_sources',1)
        measurements[str(i)]=dict(sample_peak_dbfs=peak,channel_count=channels,source='original_not_classified_as_dialogue')
        bounds.append(10**(peak/20)*channels)
    music_peak=peak_reader(edl.music['path'],'0',str(Fraction(edl.total_frames)/Fraction(edl.brief.fps))) if edl.music else -120
    music_bound=10**(music_peak/20)*edl.music['channels'] if edl.music else 0
    original=settings.original_gain_db;music=settings.music_gain_db
    linear=max(bounds,default=0)*10**(original/20)+music_bound*10**(music/20)
    ceiling=10**(-3/20);attenuation=min(0,20*math.log10(ceiling/max(linear,1e-9)))
    original=max(-96,original+attenuation);music=max(-96,music+attenuation)
    resulting=max(bounds,default=0)*10**(original/20)+music_bound*10**(music/20)
    total=str(Fraction(edl.total_frames)/Fraction(edl.brief.fps))
    return MixPlan(music_gain_db=music,original_gain_db=original,
        music_envelope=envelope(total,music,settings.fade_seconds,settings.priority_ranges if settings.ducking else (),settings.duck_db) if edl.music else None,
        original_envelopes=[envelope(d.duration_seconds,original,min(Fraction(settings.fade_seconds),Fraction(d.duration_seconds)/4)) if d.audio_policy=='preserve' and media[d.asset_id]['audio_channels'] else None for d in edl.decisions],
        estimated_peak_bound_dbfs=max(-120,20*math.log10(max(resulting,1e-9))),
        peak_measurements=dict(original=measurements,music_peak_dbfs=music_peak,method='FFmpeg astats full-rate decoded sample peaks; worst-case channel sum; -3 dBFS target'),
        ducking_applied=settings.ducking,warnings=['Sample-peak bound is conservative, not a verified true-peak/loudness normalization or guarantee of Final Cut channel routing.',
        'No automatic dialogue recognition; ducking only follows explicit original-audio priority intervals.',
        'Per-clip fades soften joins without overlapping handles; true audio crossfades are not implemented.'])
