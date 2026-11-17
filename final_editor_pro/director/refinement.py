"""Local additional boundary-frame inspection; aesthetic safety remains unverified."""
from fractions import Fraction
import subprocess
from ..analysis.metrics import measure
from ..analysis.pipeline import within_project


def refine(media,candidate,duration,folder,ffmpeg='/opt/homebrew/bin/ffmpeg'):
    if duration<=0 or duration>candidate.end_frame-candidate.start_frame: raise ValueError('Invalid refinement duration')
    fps=Fraction(media['fps']); center=(candidate.start_frame+candidate.end_frame-duration)//2
    radius=round(fps/5)
    starts=sorted({max(candidate.start_frame,min(candidate.end_frame-duration,center+delta)) for delta in (-radius,0,radius)})
    indices=sorted({i for start in starts for i in (start,start+duration-1)})
    expression='+'.join(f'eq(n\\,{i})' for i in indices)
    source=within_project(media['path']); width=160; height=max(2,round(media['height']*width/media['width']/2)*2); size=width*height*3
    cmd=[ffmpeg,'-v','error','-nostdin','-protocol_whitelist','file','-i',str(source),'-map','0:v:0','-vf',f'select={expression},scale={width}:{height}',
         '-frames:v',str(len(indices)),'-fps_mode','passthrough','-an','-sn','-dn','-pix_fmt','rgb24','-f','rawvideo','pipe:1']
    raw=subprocess.run(cmd,capture_output=True,check=True,timeout=180).stdout
    if len(raw)!=size*len(indices): raise ValueError('Refinement decoded unexpected frames')
    metrics={i:measure(raw[n*size:(n+1)*size],width,height)[0] for n,i in enumerate(indices)}
    def value(i):
        m=metrics[i]
        return m['sharpness']/(1+m['sharpness'])-.25*(m['dark']+m['bright'])
    chosen=max(starts,key=lambda start:(value(start)+value(start+duration-1),-abs(start-center)))
    return chosen,dict(method='additional-boundary-frame-grid-v1',tested_start_frames=starts,inspected_frames=[dict(frame_index=i,metrics=metrics[i]) for i in indices],
        chosen_start_frame=chosen,semantic_boundaries_used=False,caveat='Local heuristic boundary check; not a guarantee of complete action or aesthetic quality.')
