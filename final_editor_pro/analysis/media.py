"""Local frame extraction and coarse scene boundaries; no source media writes."""
from fractions import Fraction
import math
from pathlib import Path
import struct
import subprocess
import zlib
from ave.core import sha256
from .metrics import measure, difference, hist_distance


def png(rgb, width, height):
    def chunk(kind, body):
        return struct.pack('>I',len(body))+kind+body+struct.pack('>I',zlib.crc32(kind+body)&0xffffffff)
    stride=width*3
    data=b''.join(b'\0'+rgb[i:i+stride] for i in range(0,len(rgb),stride))
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))
            +chunk(b'IDAT',zlib.compress(data))+chunk(b'IEND',b''))


def sample_indices(total_frames, fps, config):
    stride=max(1, math.ceil(Fraction(fps)/Fraction(config.sample_fps)), math.ceil(total_frames/config.max_frames))
    return list(range(0,total_frames,stride)), stride


def extract(asset, config, executable, folder):
    indices,stride=sample_indices(asset.total_frames,asset.fps,config)
    width=config.proxy_width
    height=max(2,round(asset.height*width/asset.width/2)*2)
    if height > 1280: raise ValueError('Proxy aspect ratio exceeds processing budget')
    size=width*height*3
    # select uses source frame numbers, not fps resampling/duplicated frames.
    command=[str(Path(executable).resolve(strict=True)),'-v','error','-nostdin',
             '-protocol_whitelist','file','-i',asset.original_path,'-map','0:v:0',
             '-vf',f'select=not(mod(n\\,{stride})),scale={width}:{height}',
             '-frames:v',str(len(indices)),'-fps_mode','passthrough','-an','-sn','-dn',
             '-pix_fmt','rgb24','-f','rawvideo','pipe:1']
    result=subprocess.run(command,capture_output=True,timeout=600)
    if result.returncode: raise RuntimeError('FFmpeg frame extraction failed; source content not logged')
    if len(result.stdout) != size*len(indices): raise ValueError('Decoded frame count disagrees with source clock')
    samples=[]; previous=None
    for i,index in enumerate(indices):
        rgb=result.stdout[i*size:(i+1)*size]
        metrics,g,hist=measure(rgb,width,height)
        path=folder/f'frame-{index:09d}.png'
        with path.open('xb') as f: f.write(png(rgb,width,height))
        samples.append(dict(frame_index=index,timestamp=str(Fraction(index)/Fraction(asset.fps)),
                            image_path=str(path.resolve()),image_sha256=sha256(path),
                            metrics=metrics,histogram=hist,difference=difference(previous,g) if previous is not None else 0))
        previous=g
    return samples,stride


def boundaries(samples, total_frames, fps, config):
    """Persistent histogram change + pixel delta, rather than motion alone.

    Boundary location is the first changed SAMPLE, not a claim of frame-exact cut.
    """
    cuts=[0]; minimum=math.ceil(Fraction(config.min_scene_seconds)*Fraction(fps))
    for i in range(1,len(samples)-1):
        previous,current,following=samples[i-1:i+2]
        index=current['frame_index']
        change=hist_distance(previous['histogram'],current['histogram'])
        persistent=hist_distance(current['histogram'],following['histogram'])
        if (change >= config.histogram_threshold and current['difference'] >= config.difference_threshold
            and persistent < change/2 and index-cuts[-1]>=minimum and total_frames-index>=minimum):
            cuts.append(index)
    return cuts+[total_frames]
