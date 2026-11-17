"""Optional small review proxy. Camera audio remains in XML; proxy uses music only."""
from fractions import Fraction
from pathlib import Path
import subprocess
from ave.core import sha256
from ave.cli import journal
from ..analysis.pipeline import within_project
from .schemas import EditDecisionList


def preview(edl,output,ffmpeg='/opt/homebrew/bin/ffmpeg'):
    edl=EditDecisionList.model_validate(edl);out=within_project(output)
    if out.exists():raise FileExistsError('Preview output must be new')
    out.mkdir(parents=True,mode=0o700);lookup={m['sha256']:m for m in edl.media}
    before={m['path']:(sha256(m['path']),Path(m['path']).stat().st_mtime_ns) for m in edl.media}
    if edl.music:before[edl.music['path']]=(sha256(edl.music['path']),Path(edl.music['path']).stat().st_mtime_ns)
    paths=[]
    for i,d in enumerate(edl.decisions):
        source=within_project(lookup[d.asset_id]['path']); dest=out/f'clip-{i:03d}.mp4'
        duration=Fraction(d.source_out_seconds)-Fraction(d.source_in_seconds)
        filt=f'setpts=(PTS-STARTPTS)/({d.speed}),scale=512:384:force_original_aspect_ratio=increase,crop=512:384,fps={d.fps},setsar=1'
        subprocess.run([ffmpeg,'-v','error','-nostdin','-n','-threads','1','-protocol_whitelist','file','-ss',str(float(Fraction(d.source_in_seconds))),'-i',str(source),'-t',str(float(Fraction(d.duration_seconds))),'-vf',filt,'-frames:v',str(d.duration_frames),'-an','-c:v','libx264','-preset','fast','-crf','24','-pix_fmt','yuv420p',str(dest)],check=True,capture_output=True,timeout=300)
        paths.append(dest);journal(out,'created',file=dest.name,sha256=sha256(dest))
    listing=out/'clips.txt';listing.write_text(''.join(f"file '{p.name}'\n" for p in paths))
    final=out/'preview-music-only.mp4';command=[ffmpeg,'-v','error','-nostdin','-n','-protocol_whitelist','file','-f','concat','-safe','1','-i',str(listing)]
    if edl.music:command+=['-i',edl.music['path'],'-map','0:v:0','-map','1:a:0','-af','volume=-12dB','-c:a','aac','-b:a','160k']
    command+=['-c:v','copy','-t',str(float(Fraction(edl.total_frames)/Fraction(edl.brief.fps))),'-movflags','+faststart',str(final)]
    subprocess.run(command,check=True,capture_output=True,timeout=180)
    journal(out,'created',file=final.name,sha256=sha256(final));journal(out,'preview_complete',camera_audio_in_proxy=False)
    for path,state in before.items():
        if (sha256(path),Path(path).stat().st_mtime_ns)!=state:raise ValueError('Original changed during preview')
    return final
