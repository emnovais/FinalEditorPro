"""Dense local observations, cached by media/tool/settings hashes."""
import base64,json,subprocess
from fractions import Fraction
from pathlib import Path
from ave.core import sha256,json_bytes
from ..analysis.pipeline import within_project,fingerprint
from ..analysis.metrics import measure,difference
from ..analysis.media import png
from .schemas import FrameFeature,SubjectObservation,SubjectBox


def image_shift(a,b,width,height):
    if a is None:return (0,0),0
    def error(dx,dy):
        return sum(abs(a[y*width+x]-b[(y+dy)*width+x+dx]) for y in range(3,height-3,3) for x in range(3,width-3,3))
    baseline=error(0,0)
    candidates=[(error(dx,dy),abs(dx)+abs(dy),dx,dy) for dy in range(-2,3) for dx in range(-2,3)]
    best,_,dx,dy=min(candidates)
    confidence=(baseline-best)/max(1,baseline)
    return (dx,dy),confidence


def feature_packet(media,cache,ffmpeg='/opt/homebrew/bin/ffmpeg'):
    path=within_project(media['path']);cache=within_project(cache);cache.mkdir(parents=True,exist_ok=True)
    if sha256(path)!=media['sha256']:raise ValueError('Source changed')
    width=96;height=max(8,round(media['height']*width/media['width']/2)*2)
    stride=max(1,round(Fraction(media['fps'])/10));total=int(Fraction(media['duration'])*Fraction(media['fps']))
    key=fingerprint(dict(source=media['sha256'],tool=sha256(ffmpeg),width=width,height=height,stride=stride,version='features-04-v1'))
    dest=cache/(key+'.json');checksum=dest.with_suffix('.sha256')
    if dest.exists():
        if not checksum.exists() or checksum.read_text()!=sha256(dest):raise ValueError('Feature cache changed')
        rows=[FrameFeature.model_validate(v) for v in json.loads(dest.read_text())['features']]
        return rows,dict(cache_hit=True,key=key,stride_frames=stride)
    cmd=[ffmpeg,'-v','error','-nostdin','-protocol_whitelist','file','-i',str(path),'-map','0:v:0','-vf',f'select=not(mod(n\\,{stride})),scale={width}:{height}',
         '-fps_mode','passthrough','-an','-sn','-dn','-pix_fmt','rgb24','-f','rawvideo','pipe:1']
    raw=subprocess.run(cmd,capture_output=True,check=True,timeout=600).stdout;size=width*height*3
    indices=list(range(0,total,stride))
    if len(raw)!=len(indices)*size:raise ValueError('Dense frame count differs')
    rows=[];previous=None
    for n,index in enumerate(indices):
        metrics,g,hist=measure(raw[n*size:(n+1)*size],width,height)
        shift,confidence=image_shift(previous,g,width,height)
        thumbnail=[g[min(height-1,round(y*(height-1)/8))*width+min(width-1,round(x*(width-1)/15))]/255 for y in range(9) for x in range(16)]
        rows.append(FrameFeature(frame_index=index,luma=metrics['luma'],sharpness=metrics['sharpness'],histogram=hist,thumbnail=thumbnail,
            motion=difference(previous,g) if previous is not None else 0,image_shift=shift,shift_confidence=confidence));previous=g
    with dest.open('xb') as f:f.write(json_bytes(dict(features=[r.model_dump(mode='json') for r in rows])))
    checksum.write_text(sha256(dest))
    if sha256(path)!=media['sha256']:raise ValueError('Source changed during features')
    return rows,dict(cache_hit=False,key=key,stride_frames=stride)


def nearest(rows,index):return min(rows,key=lambda r:abs(r.frame_index-index))


def vision_observations(media,samples_file,manifest,cache):
    """Native reviewed helper only; failure means unavailable, never remote fallback."""
    spec=json.loads(within_project(manifest).read_text());binary=within_project(spec['binary']);work=within_project('temp/mvp04');work.mkdir(exist_ok=True)
    if sha256(binary)!=spec['sha256']:raise ValueError('Vision helper changed')
    source=within_project(media['path'])
    if sha256(source)!=media['sha256']:raise ValueError('Vision media changed')
    samples=json.loads(within_project(samples_file).read_text());paths=[]
    for s in samples:
        p=within_project(s['image_path'])
        if sha256(p)!=s['image_sha256']:raise ValueError('Vision image changed')
        paths.append(p)
    # Bind images to this source through an explicit original sample manifest.
    if not spec.get('source_manifests',{}).get(media['sha256'])==sha256(within_project(samples_file)):raise ValueError('Unapproved source/image binding')
    key=fingerprint(dict(source=media['sha256'],samples=sha256(within_project(samples_file)),helper=spec['sha256']))
    dest=within_project(cache)/(key+'-subjects.json');dest.parent.mkdir(exist_ok=True,parents=True)
    if dest.exists():
        if dest.with_suffix('.sha256').read_text()!=sha256(dest):raise ValueError('Subject cache changed')
        return [SubjectObservation.model_validate(r) for r in json.loads(dest.read_text())]
    quoted=str(work).replace('\\','\\\\').replace('"','\\"')
    profile='(version 1)(allow default)(deny network*)(deny file-write*)(allow file-write* (subpath "'+quoted+'"))'
    cmd=['/usr/bin/sandbox-exec','-p',profile,str(binary)]+[str(p) for p in paths]
    result=subprocess.run(cmd,capture_output=True,check=True,timeout=300,env={'PATH':'/usr/bin:/bin','TMPDIR':str(work),'LANG':'en_US.UTF-8'},cwd=within_project('.'))
    raw=json.loads(result.stdout)
    if len(raw)!=len(samples) or [r['path'] for r in raw]!=[str(p) for p in paths]:raise ValueError('Wrong Vision image response')
    rows=[]
    wire=dest.with_suffix('.wire.private.json')
    if not wire.exists():
        with wire.open('xb') as f:f.write(json_bytes(raw))
    for s,r in zip(samples,raw):
        boxes=[];rejected=0
        for box in r['boxes']:
            try:boxes.append(SubjectBox.model_validate(box))
            except ValueError:rejected+=1
        rows.append(SubjectObservation(asset_sha256=media['sha256'],frame_index=s['frame_index'],image_sha256=s['image_sha256'],detector=r.get('detector','unavailable'),boxes=boxes,rejected_box_count=rejected,warnings=['Out-of-frame detector boxes rejected without inventing/clamping coordinates'] if rejected else []))
    with dest.open('xb') as f:f.write(json_bytes([r.model_dump(mode='json') for r in rows]))
    dest.with_suffix('.sha256').write_text(sha256(dest))
    return rows


def subject_samples(media,cache,ffmpeg='/opt/homebrew/bin/ffmpeg'):
    """2 fps RGB proxies for native detections, retaining exact source indices."""
    source=within_project(media['path']);cache=within_project(cache);cache.mkdir(parents=True,exist_ok=True)
    if sha256(source)!=media['sha256']:raise ValueError('Subject source changed')
    width=320;height=max(8,round(media['height']*width/media['width']/2)*2)
    stride=max(1,round(Fraction(media['fps'])/2));count=int(Fraction(media['duration'])*Fraction(media['fps']))
    key=fingerprint(dict(source=media['sha256'],tool=sha256(ffmpeg),stride=stride,size=[width,height],version='subjects-04-v1'))
    folder=cache/key;dest=folder/'samples.json'
    if dest.exists():
        if dest.with_suffix('.sha256').read_text()!=sha256(dest):raise ValueError('Sample manifest changed')
        return dest
    folder.mkdir()
    command=[ffmpeg,'-v','error','-nostdin','-protocol_whitelist','file','-i',str(source),'-map','0:v:0','-vf',f'select=not(mod(n\\,{stride})),scale={width}:{height}',
             '-fps_mode','passthrough','-an','-sn','-dn','-pix_fmt','rgb24','-f','rawvideo','pipe:1']
    raw=subprocess.run(command,capture_output=True,check=True,timeout=600).stdout;indices=list(range(0,count,stride));size=width*height*3
    if len(raw)!=size*len(indices):raise ValueError('Subject proxy count differs')
    samples=[]
    for n,index in enumerate(indices):
        path=folder/f'frame-{index:09d}.png'
        with path.open('xb') as f:f.write(png(raw[n*size:(n+1)*size],width,height))
        samples.append(dict(frame_index=index,image_path=str(path),image_sha256=sha256(path),timestamp=str(Fraction(index)/Fraction(media['fps']))))
    with dest.open('xb') as f:f.write(json_bytes(samples))
    dest.with_suffix('.sha256').write_text(sha256(dest))
    return dest


def attach_subjects(rows,observations,fps):
    result=[]
    for row in rows:
        nearby=min(observations,key=lambda o:abs(o.frame_index-row.frame_index)) if observations else None
        if nearby and abs(nearby.frame_index-row.frame_index)<=round(Fraction(fps)/4):
            boxes=[b for b in nearby.boxes if b.confidence>=.6]
            if boxes:
                x=min(b.x for b in boxes);y=min(b.y for b in boxes);r=max(b.x+b.width for b in boxes);bottom=max(b.y+b.height for b in boxes)
                row=row.model_copy(update=dict(subject_position=((x+r)/2,(y+bottom)/2),subject_area=(r-x)*(bottom-y),subject_count=len(boxes)))
        result.append(row)
    return result


def inspect_boundaries(media,start,end,ffmpeg='/opt/homebrew/bin/ffmpeg'):
    indices=sorted({start,min(end-1,start+1),max(start,end-2),end-1});width=96;height=max(8,round(media['height']*width/media['width']/2)*2);size=width*height*3
    expression='+'.join(f'eq(n\\,{i})' for i in indices)
    command=[ffmpeg,'-v','error','-nostdin','-protocol_whitelist','file','-i',str(within_project(media['path'])),'-map','0:v:0','-vf',f'select={expression},scale={width}:{height}',
        '-frames:v',str(len(indices)),'-fps_mode','passthrough','-an','-sn','-dn','-pix_fmt','rgb24','-f','rawvideo','pipe:1']
    raw=subprocess.run(command,capture_output=True,check=True,timeout=180).stdout
    if len(raw)!=len(indices)*size:raise ValueError('Boundary inspection differs from source indices')
    return [dict(frame_index=index,metrics=measure(raw[n*size:(n+1)*size],width,height)[0]) for n,index in enumerate(indices)]
