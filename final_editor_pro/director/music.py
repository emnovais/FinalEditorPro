"""Local mono energy-envelope heuristics; no claim of stable musical tempo."""
from array import array
from fractions import Fraction
import math
import subprocess
import sys
from ave.core import sha256
from ..analysis.pipeline import within_project


def envelope_analysis(energy, rate=50):
    if not energy: raise ValueError('Empty audio')
    # Positive log-energy novelty: detects amplitude attacks, not every musical beat.
    novelty=[0.0]+[max(0,math.log1p(energy[i]*100)-math.log1p(energy[i-1]*100)) for i in range(1,len(energy))]
    mean=sum(novelty)/len(novelty); variance=sum((x-mean)**2 for x in novelty)/len(novelty)
    threshold=mean+math.sqrt(variance)*.75
    peaks=[]
    for i in range(1,len(novelty)-1):
        if novelty[i]>max(threshold,1e-6) and novelty[i]>=novelty[i-1] and novelty[i]>novelty[i+1]:
            if not peaks or i-peaks[-1]>=round(rate*.18): peaks.append(i)
            elif novelty[i]>novelty[peaks[-1]]: peaks[-1]=i
    def tempo(start,end):
        segment=novelty[start:end]
        power=sum(x*x for x in segment)
        if len(segment)<rate*4 or power<1e-8: return None
        scores=[]
        for lag in range(math.ceil(rate*60/180),math.floor(rate*60/60)+1):
            corr=sum(segment[i]*segment[i-lag] for i in range(lag,len(segment)))/power
            scores.append((corr,lag))
        corr,lag=max(scores)
        return dict(bpm=60*rate/lag,correlation=corr)
    windows=[tempo(i,min(len(energy),i+rate*10)) for i in range(0,len(energy),rate*10)]
    windows=[w for w in windows if w]
    global_tempo=tempo(0,len(energy))
    stable=bool(windows) and max(w['bpm'] for w in windows)-min(w['bpm'] for w in windows)<8
    bpm=global_tempo['bpm'] if global_tempo and global_tempo['correlation']>.1 else None
    beats=[]
    if bpm is not None and peaks:
        period=60*rate/bpm; phase=max(peaks,key=lambda i:novelty[i])%period
        beats=[str(Fraction(round(phase+k*period),rate)) for k in range(math.ceil(len(energy)/period)) if 0<=round(phase+k*period)<len(energy)]
    blocks=[(sum(energy[i:i+rate])/len(energy[i:i+rate]),i) for i in range(0,len(energy),rate)]
    intense=sorted(blocks,reverse=True)[:min(10,len(blocks))]
    return dict(schema_version='0.3.0',method='log-energy-novelty-autocorrelation-v1',estimated_bpm=bpm,stable_tempo_supported=stable,
        tempo_windows=windows,onsets_seconds=[str(Fraction(i,rate)) for i in peaks],estimated_beats_seconds=beats,
        intensity_peaks_seconds=[str(Fraction(i,rate)) for _,i in intense],
        warnings=['Amplitude heuristics; beat phase, half/double tempo and onsets can be wrong.','No mandatory beat cuts; unstable tempo is not a single verified BPM.'])


def analyze_music(path,ffmpeg='/opt/homebrew/bin/ffmpeg'):
    p=within_project(path); before=(sha256(p),p.stat().st_size,p.stat().st_mtime_ns)
    # Bound decode to 15 minutes; never transcode the original file.
    raw=subprocess.run([ffmpeg,'-v','error','-nostdin','-protocol_whitelist','file','-i',str(p),'-map','0:a:0','-t','900','-vn','-ac','1','-ar','8000','-f','s16le','pipe:1'],capture_output=True,check=True,timeout=180).stdout
    pcm=array('h'); pcm.frombytes(raw)
    if sys.byteorder!='little': pcm.byteswap()
    energy=[math.sqrt(sum((x/32768)**2 for x in pcm[i:i+160])/len(pcm[i:i+160])) for i in range(0,len(pcm),160)]
    result=envelope_analysis(energy)
    result.update(path=str(p),sha256=before[0],duration_seconds=str(Fraction(len(pcm),8000)),decoded_duration_seconds=str(Fraction(len(pcm),8000)),decoded_limit_seconds=900)
    if (sha256(p),p.stat().st_size,p.stat().st_mtime_ns)!=before: raise ValueError('Music changed')
    from .schemas import MusicAnalysis
    return MusicAnalysis.model_validate(result).model_dump(mode='json')


def source_clock_metadata(probe_data):
    """BWF time_reference is an absolute sample clock, not a playback delay."""
    stream=next((s for s in probe_data.get('streams',[]) if s.get('codec_type')=='audio'),None)
    if stream is None:raise ValueError('Audio source missing')
    reference=probe_data.get('format',{}).get('tags',{}).get('time_reference')
    if reference is None:return dict(source_start_seconds='0',source_clock_kind='zero',bwf_time_reference_samples=None)
    text=str(reference)
    if not text.isascii() or not text.isdecimal():raise ValueError('Invalid BWF sample reference')
    rate=int(stream['sample_rate'])
    if rate<=0:raise ValueError('Invalid BWF sample rate')
    return dict(source_start_seconds=str(Fraction(int(text),rate)),source_clock_kind='bwf_sample_reference',bwf_time_reference_samples=int(text))
