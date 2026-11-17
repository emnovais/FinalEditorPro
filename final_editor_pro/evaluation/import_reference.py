"""Import user-provided Portuguese clip descriptions without inventing timestamps."""
import re
from pathlib import Path
from ave.core import sha256,json_bytes
from ..analysis.pipeline import within_project
from ..analysis import pipeline
from .schemas import HumanReference,EvaluationDataset


def import_descriptions(dataset,source,output):
    source=within_project(source); out=within_project(output)
    if out.exists(): raise FileExistsError('Reference import cannot overwrite an artifact')
    text=source.read_text(); digest=sha256(source)
    pattern=r'^Arquivo\s+\d+\.\s+([^\n]+)\n'
    headers=list(re.finditer(pattern,text,re.M))
    if not headers: raise ValueError('No explicitly named clip descriptions found')
    descriptions={}
    for i,h in enumerate(headers):
        name=h.group(1).strip()
        if name in descriptions: raise ValueError('Duplicate human description for media')
        body=text[h.end():headers[i+1].start() if i+1<len(headers) else len(text)].strip()
        # Keep audio sentence verbatim, not silently discard or present as visual evidence.
        match=re.search(r'(?m)^No áudio',body)
        visual=body[:match.start()].strip() if match else body
        audio=body[match.start():].strip() if match else ''
        descriptions[name]=(visual,audio)
    cases=[]; matched=[]
    for case in dataset.cases:
        name=Path(case.original_path).name
        if name in descriptions:
            visual,audio=descriptions[name]
            reference=HumanReference(status='pending',annotator='provided-by-user; identity not stated',
                source_path=str(source.relative_to(pipeline.ROOT)),source_sha256=digest,
                visual_description=visual,audio_notes=audio,
                evidence_notes='Human-supplied full-clip description; event timestamps and exhaustive labels not provided.',
                pending_fields=['annotator_identity','verification_date','event_frame_intervals','exhaustive_labels','split_and_group_confirmation'])
            case=case.model_copy(update={'reference':reference}); matched.append(name)
        cases.append(case)
    unknown=set(descriptions)-{Path(c.original_path).name for c in dataset.cases}
    if unknown: raise ValueError('Descriptions refer to media absent from dataset')
    result=EvaluationDataset.model_validate(dict(dataset.model_dump(mode='json'),cases=[c.model_dump(mode='json') for c in cases],frozen=False))
    out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(json_bytes(result.model_dump(mode='json')))
    if sha256(source)!=digest: raise ValueError('Human reference changed while importing')
    return result,dict(matched=len(matched),source_sha256=digest,verified_references=0,
                       limitation='Descriptions preserved; no timestamps, labels or categories fabricated.')
