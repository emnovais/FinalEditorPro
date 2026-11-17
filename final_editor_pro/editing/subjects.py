"""Prepare native subject evidence with an explicitly reviewed helper; no compilation/install."""
import json
from ave.core import sha256,json_bytes
from ave.cli import journal
from ..analysis.pipeline import within_project
from ..director.schemas import EditDecisionList
from .features import subject_samples,vision_observations


def prepare(edl_path,helper_manifest,output,images='workspace/subject-images',cache='workspace/editing-cache'):
    edl=EditDecisionList.model_validate_json(within_project(edl_path).read_text());spec=json.loads(within_project(helper_manifest).read_text())
    binary=within_project(spec['binary'])
    if sha256(binary)!=spec['sha256']:raise ValueError('Reviewed helper changed')
    out=within_project(output)
    if out.exists():raise FileExistsError('Subject output must be new')
    out.mkdir(parents=True,mode=0o700);journal(out,'subjects_started',helper_sha256=spec['sha256'])
    try:
        samples={m['sha256']:subject_samples(m,images) for m in edl.media}
        spec['source_manifests']={key:sha256(path) for key,path in samples.items()}
        manifest=out/'bound-manifest.json'
        with manifest.open('xb') as f:f.write(json_bytes(spec))
        observations=[]
        for m in edl.media:
            observations.extend(vision_observations(m,samples[m['sha256']],manifest,cache))
        dest=out/'subjects.json'
        with dest.open('xb') as f:f.write(json_bytes([o.model_dump(mode='json') for o in observations]))
        dest.with_suffix('.sha256').write_text(sha256(dest));journal(out,'subjects_complete',sha256=sha256(dest),observations=len(observations))
        return dest
    except Exception as exc:
        journal(out,'subjects_failed',error=type(exc).__name__);raise
