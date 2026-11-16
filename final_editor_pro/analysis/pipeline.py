"""Read-only analysis pipeline. Output/cache paths must stay inside the project."""
import base64
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import resource
import time
import uuid

from ave.cli import probe, journal
from ave.core import metadata, sha256, local_media, json_bytes
from ..ai.schemas import Task
from .schemas import (AnalysisConfig, AnalysisReport, MediaAsset, SceneSegment,
                      FrameSample, TemporalInput, TemporalFrame)
from .media import extract, boundaries
from .metrics import aggregate, score

ROOT = Path(__file__).resolve().parents[2]


def within_project(path):
    p=Path(path).expanduser().resolve()
    if not p.is_relative_to(ROOT): raise ValueError('Analysis paths must remain inside project')
    if any(part.lower().endswith(('.fcpbundle','.fcplibrary')) for part in p.parts):
        raise ValueError('Final Cut libraries are forbidden')
    return p


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def representative(samples, count):
    if len(samples)<=count: return samples
    return [samples[round(i*(len(samples)-1)/(count-1))] for i in range(count)]


def temporal_request(asset, start_frame, end_frame, samples, max_frames):
    """Shared deterministic request builder for preview/consent and execution."""
    selected=representative(samples,max_frames)
    return TemporalInput(asset_id=asset.asset_id,fps=asset.fps,start_frame=start_frame,end_frame=end_frame,
        frames=[TemporalFrame(frame_index=f['frame_index'],timestamp=f['timestamp'],
            data_base64=base64.b64encode(within_project(f['image_path']).read_bytes()).decode()) for f in selected])


def cached_samples(folder):
    rows=json.loads((folder/'samples.json').read_text())
    for s in rows['samples']:
        p=within_project(s['image_path'])
        if not p.is_relative_to(folder) or sha256(p)!=s['image_sha256']:
            raise ValueError('Cached frame integrity mismatch')
    return rows


def analyze(path, output, cache, config=None, *, ffprobe, ffmpeg, router=None, consent=None):
    config=config or AnalysisConfig()
    start=time.perf_counter()
    path=within_project(path); local_media(path)
    out=within_project(output); cache=within_project(cache)
    if out.exists(): raise FileExistsError('Output must be a new directory')
    if out==path or out.is_relative_to(path): raise ValueError('Output overlaps source')
    out.mkdir(parents=True,mode=0o700)
    cache.mkdir(parents=True,exist_ok=True,mode=0o700)
    before=sha256(path); stat=path.stat()
    provider=router.select(Task.TEMPORAL_VISUAL) if config.semantic and router else None
    if config.semantic and provider is None: raise ValueError('Semantic analysis requires a registered provider')
    identity={'provider':provider.id,'model':provider.model} if provider else None
    tools={'ffprobe':sha256(ffprobe),'ffmpeg':sha256(ffmpeg)}
    full_key=fingerprint(dict(source=before,path=str(path),config=config.model_dump(mode='json'),tools=tools,
                             provider=identity,pipeline='analyzer-2'))
    full_cache=cache/(full_key+'.json')
    journal(out,'analysis_started',asset=before,semantic=config.semantic,provider=identity)
    try:
        if full_cache.exists():
            if not full_cache.with_suffix('.sha256').is_file() or full_cache.with_suffix('.sha256').read_text()!=sha256(full_cache):
                raise ValueError('Cached report integrity mismatch')
            saved=json.loads(full_cache.read_text())
            report=AnalysisReport.model_validate(saved)
            for s in report.segments:
                for f in s.sampled_frames:
                    if sha256(within_project(f.image_path))!=f.image_sha256: raise ValueError('Cached image modified')
            elapsed=time.perf_counter()-start
            saved['benchmark']=dict(saved['benchmark'],cache_hit=True,decode_cache_hit=True,
                                    elapsed_seconds=elapsed,inference_seconds=0,
                                    seconds_per_video_minute=elapsed/saved['benchmark']['source_minutes'],
                                    process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                                    child_peak_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                                    frames_extracted=0,semantic_frames_submitted=0,
                                    measured_inference_calls=0,cached_inference=True)
            report=AnalysisReport.model_validate(saved)
        else:
            raw=probe(path,ffprobe); normalized=metadata(path,raw)
            (out/'probe.json').write_bytes(json_bytes(raw))
            fps=Fraction(normalized['fps']); count=int(Fraction(normalized['duration'])*fps)
            asset=MediaAsset(asset_id=before,original_path=str(path),sha256=before,size_bytes=stat.st_size,
                fps=str(fps),duration=normalized['duration'],source_start=normalized['start'],total_frames=count,
                width=normalized['width'],height=normalized['height'],codec=normalized['codec'],metadata=normalized)
            frame_config={k:config.model_dump(mode='json')[k] for k in ('sample_fps','max_frames','proxy_width')}
            key=fingerprint(dict(source=before,path=str(path),config=frame_config,tools=tools,pipeline='frames-1'))
            frame_dir=cache/key
            decode_hit=frame_dir.exists()
            if decode_hit:
                try: extracted=cached_samples(frame_dir)
                except (ValueError,OSError,KeyError):
                    frame_dir.rename(cache/(key+'.invalid-'+uuid.uuid4().hex)); decode_hit=False
            if not decode_hit:
                frame_dir.mkdir(mode=0o700)
                samples,stride=extract(asset,config,ffmpeg,frame_dir)
                extracted={'samples':samples,'stride':stride}
                (frame_dir/'samples.json').write_bytes(json_bytes(extracted))
            samples=extracted['samples']; stride=extracted['stride']
            edges=boundaries(samples,count,fps,config); segments=[]; inference=0; calls=0
            for i,(a,b) in enumerate(zip(edges,edges[1:])):
                selected=[s for s in samples if a<=s['frame_index']<b]
                technical=aggregate([s['metrics'] for s in selected],[s['difference'] for s in selected[1:]])
                visual=None; status='not_requested'
                if config.semantic:
                    request=temporal_request(asset,a,b,selected,config.max_semantic_frames)
                    tick=time.perf_counter(); calls+=1
                    try:
                        # Remote consent, when applicable, must be for this exact interval/payload.
                        grant=consent.get(f'{asset.asset_id[:16]}-{i}') if isinstance(consent,dict) else consent
                        visual=router.run(Task.TEMPORAL_VISUAL,request,consent=grant).output
                        status='complete'
                    except Exception as exc:
                        journal(out,'semantic_failed',segment=i,error=type(exc).__name__)
                        status='failed'
                    inference+=time.perf_counter()-tick
                segments.append(SceneSegment(segment_id=f'{asset.asset_id[:16]}-{i}',asset_id=asset.asset_id,
                    start_frame=a,end_frame=b,start_time=str(Fraction(a)/fps),end_time=str(Fraction(b)/fps),
                    boundary_uncertainty_frames=stride if a else 0,
                    sampled_frames=[FrameSample(**{k:s[k] for k in ('frame_index','timestamp','image_path','image_sha256')}) for s in selected],
                    technical=technical,visual=visual,score=score(technical,visual,config.profile,config.score_weights),
                    provider=provider.id if provider else None,model=provider.model if provider else None,semantic_status=status))
            elapsed=time.perf_counter()-start
            report=AnalysisReport(asset=asset,segments=segments,config=config.model_dump(mode='json'),
                benchmark=dict(elapsed_seconds=elapsed,source_minutes=float(Fraction(asset.duration)/60),
                    seconds_per_video_minute=elapsed/float(Fraction(asset.duration)/60),
                    process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                    child_peak_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                    memory_scope='macOS process high-water RSS; GPU/unified allocations not measured',
                    inference_seconds=inference,measured_inference_calls=calls,
                    frames_extracted=0 if decode_hit else len(samples),frames_available=len(samples),
                    semantic_frames_submitted=sum(min(len([s for s in samples if a<=s['frame_index']<b]),config.max_semantic_frames) for a,b in zip(edges,edges[1:])) if config.semantic else 0,
                    cache_hit=False,decode_cache_hit=decode_hit,cached_inference=False,
                    status='partial' if any(s.semantic_status=='failed' for s in segments) else 'complete'),
                limitations=['Scene detection is sampled and approximate, not frame-exact.',
                    'No audio transcription or acoustic analysis implemented; audio stream metadata only.',
                    'Motion metrics are proxies, not optical flow or tracking.',
                    'Semantic confidence/subjective scores are uncalibrated; review visual evidence.',
                    'Suggestions do not execute masks, effects or timeline edits.'])
        if sha256(path)!=before or path.stat().st_mtime_ns!=stat.st_mtime_ns: raise ValueError('Source changed during analysis')
        (out/'analysis.json').write_bytes(json_bytes(report.model_dump(mode='json')))
        # Only complete reports are reusable; remote grants are never persisted.
        if report.benchmark['status']=='complete' and not full_cache.exists():
            tmp=cache/(full_key+'.tmp-'+uuid.uuid4().hex)
            tmp.write_bytes(json_bytes(report.model_dump(mode='json'))); tmp.rename(full_cache)
            full_cache.with_suffix('.sha256').write_text(sha256(full_cache))
        journal(out,'analysis_'+report.benchmark['status'],report_sha256=sha256(out/'analysis.json'),
                cache_hit=report.benchmark['cache_hit'])
        return report
    except Exception as exc:
        journal(out,'analysis_failed',error=type(exc).__name__)
        raise
