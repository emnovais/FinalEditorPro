"""Local dataset preparation. Never promotes AI descriptions to human references."""
from fractions import Fraction
import json
from pathlib import Path
from ave.core import sha256, json_bytes
from ..analysis.pipeline import within_project, fingerprint, temporal_request
from ..analysis.schemas import AnalysisReport, TemporalInput
from .schemas import EvaluationDataset, EvaluationCase, HumanReference, CATEGORIES


def inventory(media_dir, output):
    folder=within_project(media_dir); out=within_project(output)
    if out.exists(): raise FileExistsError('Dataset output already exists')
    from ave.cli import probe
    from ave.core import metadata
    cases=[]
    for i,p in enumerate(sorted(folder.iterdir())):
        if not p.is_file() or p.suffix.lower() not in ('.mov','.mp4','.mxf'): continue
        m=metadata(p,probe(p,'/opt/homebrew/bin/ffprobe'))
        cases.append(EvaluationCase(case_id=f'clip-{len(cases)+1:02d}',original_path=str(p.relative_to(within_project('.'))),
            sha256=m['sha256'],source_group='unverified-session-group',split='unassigned',categories=[],
            fps=m['fps'],start_frame=0,end_frame=int(Fraction(m['duration'])*Fraction(m['fps'])),reference=HumanReference()))
    dataset=EvaluationDataset(dataset_id='local-media-v1',cases=cases)
    out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(json_bytes(dataset.model_dump(mode='json')))
    return dataset


def coverage(dataset):
    counts={c:0 for c in CATEGORIES}
    for case in dataset.cases:
        for cat in case.categories: counts[cat]+=1
    return dict(categories=counts,missing_categories=[c for c,n in counts.items() if not n],
        verified_references=sum(c.reference.status=='verified' for c in dataset.cases),
        cases=len(dataset.cases),splits={s:sum(c.split==s for c in dataset.cases) for s in ('development','evaluation','unassigned')},
        unique_source_groups=len({c.source_group for c in dataset.cases}),frozen=dataset.frozen)


def freeze_input(case, analysis_report, output, max_frames=4):
    report=AnalysisReport.model_validate_json(within_project(analysis_report).read_text())
    source=within_project(case.original_path)
    if sha256(source)!=case.sha256 or report.asset.sha256!=case.sha256 or report.asset.fps!=case.fps:
        raise ValueError('Reference report/source differs from dataset case')
    if case.end_frame>report.asset.total_frames: raise ValueError('Dataset case extends beyond source')
    samples=[f.model_dump() for segment in report.segments for f in segment.sampled_frames
             if case.start_frame<=f.frame_index<case.end_frame]
    if len(samples)<2: raise ValueError('Temporal benchmark requires at least two sampled frames')
    from ..analysis.pipeline import representative
    samples=representative(samples,max_frames)
    for sample in samples:
        if sha256(within_project(sample['image_path']))!=sample['image_sha256']: raise ValueError('Frame integrity mismatch')
    request=temporal_request(report.asset,case.start_frame,case.end_frame,samples,max_frames)
    target=within_project(output)
    if target.exists(): raise FileExistsError('Frozen input cannot be overwritten')
    target.parent.mkdir(parents=True,exist_ok=True)
    packet=dict(schema_version='0.2.1',case_id=case.case_id,source_sha256=case.sha256,
                modality='ordered_timestamped_frames',request=request.model_dump(mode='json'))
    packet['input_sha256']=fingerprint(packet['request'])
    target.write_bytes(json_bytes(packet))
    return packet


def load_input(path, case):
    packet=json.loads(within_project(path).read_text())
    req=TemporalInput.model_validate(packet['request'])
    if (packet['input_sha256']!=fingerprint(req.model_dump(mode='json')) or packet['source_sha256']!=case.sha256
        or packet['case_id']!=case.case_id or req.fps!=case.fps or req.start_frame!=case.start_frame or req.end_frame!=case.end_frame
        or req.asset_id!=case.sha256 or packet['modality']!='ordered_timestamped_frames'):
        raise ValueError('Frozen input differs from dataset or checksum')
    if sha256(within_project(case.original_path))!=case.sha256: raise ValueError('Dataset media changed')
    return req,packet['input_sha256']
