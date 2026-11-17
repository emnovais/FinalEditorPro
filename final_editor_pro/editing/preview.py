"""Local preview with the actual static crop and gain curves; no originals changed."""
from fractions import Fraction
from pathlib import Path
import subprocess
from ave.core import sha256
from ave.cli import journal,probe
from ..analysis.pipeline import within_project
from .schemas import EditingPackage
from .mixing import sample_peak


def volume_expression(envelope):
    points=[(float(Fraction(t)),g) for t,g in envelope.points]
    expression=str(points[-1][1])
    for (a,ga),(b,gb) in reversed(list(zip(points,points[1:]))):
        segment=f'({ga}+({gb-ga})*(t-{a})/{b-a})'
        expression=f'if(lt(t,{b}),{segment},{expression})'
    return f"volume='pow(10,({expression})/20)':eval=frame"


def render(package,output,ffmpeg='/opt/homebrew/bin/ffmpeg'):
    p=EditingPackage.model_validate(package);edl=p.base_edl;out=within_project(output)
    if out.exists():raise FileExistsError('Preview output must be new')
    out.mkdir(parents=True,mode=0o700);media={m['sha256']:m for m in edl.media}
    paths=[within_project(m['path']) for m in edl.media]+([within_project(edl.music['path'])] if edl.music else [])
    before={str(path):(sha256(path),path.stat().st_size,path.stat().st_mtime_ns) for path in paths}
    ratio=Fraction(edl.brief.output_width,edl.brief.output_height)
    width=512 if ratio>=1 else round(512*float(ratio)/2)*2;height=512 if ratio<1 else round(512/float(ratio)/2)*2
    fragments=[]
    for i,(d,reframing,env) in enumerate(zip(edl.decisions,p.reframing,p.mix.original_envelopes)):
        m=media[d.asset_id];x,y,w,h=reframing.crop
        vf=f'[0:v:0]setpts=(PTS-STARTPTS)/({d.speed}),crop=iw*{w}:ih*{h}:iw*{x}:ih*{y},scale={width}:{height},fps={d.fps}:round=down,setsar=1[v]'
        duration=str(float(Fraction(d.duration_seconds)))
        if env:
            n=m.get('audio_sources',1);inputs=''.join(f'[0:a:{j}]' for j in range(n))
            af=f'{inputs}amix=inputs={n}:normalize=0,aresample=48000,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS,{volume_expression(env)},apad,atrim=duration={duration}[a]'
        else:af=f'anullsrc=r=48000:cl=stereo,atrim=duration={duration}[a]'
        dest=out/f'clip-{i:03d}.mov'
        command=[ffmpeg,'-v','error','-nostdin','-n','-threads','1','-filter_complex_threads','1','-protocol_whitelist','file','-ss',str(float(Fraction(d.source_in_seconds))),'-i',m['path'],
            '-filter_complex',vf+';'+af,'-map','[v]','-map','[a]','-frames:v',str(d.duration_frames),'-t',duration,'-c:v','libx264','-preset','fast','-crf','24','-pix_fmt','yuv420p','-c:a','pcm_s16le','-ar','48000',str(dest)]
        subprocess.run(command,check=True,capture_output=True,timeout=300)
        fragments.append(dest);journal(out,'created',file=dest.name,sha256=sha256(dest))
    listing=out/'clips.txt';listing.write_text(''.join(f"file '{f.name}'\n" for f in fragments))
    final=out/'preview.mp4';total=str(float(Fraction(edl.total_frames)/Fraction(edl.brief.fps)))
    command=[ffmpeg,'-v','error','-nostdin','-n','-filter_complex_threads','1','-protocol_whitelist','file','-f','concat','-safe','1','-i',str(listing)]
    if edl.music:
        command+=['-i',edl.music['path'],'-filter_complex',f'[1:a:0]aresample=48000,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS,{volume_expression(p.mix.music_envelope)}[music];[0:a:0][music]amix=inputs=2:normalize=0,atrim=duration={total}[mix]','-map','0:v:0','-map','[mix]']
    else:command+=['-map','0:v:0','-map','0:a:0']
    command+=['-c:v','copy','-c:a','aac','-b:a','192k','-t',total,'-movflags','+faststart',str(final)]
    subprocess.run(command,check=True,capture_output=True,timeout=180)
    facts=probe(final,'/opt/homebrew/bin/ffprobe');v=next(s for s in facts['streams'] if s['codec_type']=='video')
    if int(v['nb_frames'])!=edl.total_frames or Fraction(v['r_frame_rate'])!=Fraction(edl.brief.fps):raise ValueError('Preview timeline differs')
    peak=sample_peak(final)
    for path,state in before.items():
        path=Path(path)
        if (sha256(path),path.stat().st_size,path.stat().st_mtime_ns)!=state:raise ValueError('Original changed')
    journal(out,'preview_complete',file=final.name,sha256=sha256(final),sample_peak_dbfs=peak,frames=int(v['nb_frames']),camera_audio='all declared source streams downmixed to stereo; Final Cut pan routing may differ')
    return dict(path=str(final),sample_peak_dbfs=peak,frames=int(v['nb_frames']),width=width,height=height)
