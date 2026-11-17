"""Compatibility check for already approved weights. Never downloads or installs."""
import json
from ave.core import json_bytes
from ..analysis.pipeline import within_project
from ..analysis.runtime import local_server
from ..ai.schemas import Task,validate_output
from .runner import MeasuredTemporal
from .dataset import load_input


def preflight(dataset,spec,input_path,case_id,output):
    out=within_project(output)
    if out.exists(): raise FileExistsError('Preflight output must be new')
    out.mkdir(parents=True)
    case=next(c for c in dataset.cases if c.case_id==case_id)
    request,input_sha=load_input(input_path,case)
    manifest=json.loads(within_project(spec.runtime_manifest).read_text())
    if manifest['manifest_sha256']!=spec.model_digest: raise ValueError('Model digest mismatch')
    result=dict(model_id=spec.model_id,input_sha256=input_sha,loaded=False,validated_multimodal_response=False)
    phase='load'
    adapter=None
    try:
        with local_server(spec.runtime_manifest,content_only=True) as process:
            adapter=MeasuredTemporal(manifest['model_name'],'http://127.0.0.1:11435',spec.model_digest)
            info=adapter.request('/v1/models'); result['backend_metadata']=info; result['loaded']=True
            detected=info['data'][0].get('meta',{}).get('ftype')
            spec=spec.model_copy(update=dict(quantization=detected or spec.quantization))
            modalities=info['data'][0].get('architecture',{}).get('input_modalities',[])
            if 'image' not in modalities: raise ValueError('Runtime did not advertise image support')
            phase='structured_multimodal'
            analysis=validate_output(Task.TEMPORAL_VISUAL,request,adapter(request))
            result['validated_multimodal_response']=True
            (out/'response.json').write_bytes(json_bytes(analysis.model_dump(mode='json')))
            detected=info['data'][0].get('meta',{}).get('ftype')
            spec=spec.model_copy(update=dict(status='ready',quantization=detected or spec.quantization))
    except Exception as exc:
        result.update(error_phase=phase,error_type=type(exc).__name__)
        if hasattr(exc,'errors'):
            result['validation_errors']=[{'type':e['type'],'loc':e['loc']} for e in exc.errors()]
        response_received=adapter is not None and adapter.response is not None and 'choices' in adapter.response
        result['response_received']=response_received
        if response_received:
            (out/'raw-response.private.json').write_bytes(json_bytes(adapter.response))
        # Runtime incompatibility and model reliability are different outcomes.
        # Do not exclude a model merely because its first answer failed the contract.
        measurable=phase=='structured_multimodal' and response_received
        spec=spec.model_copy(update=dict(status='ready' if measurable else 'candidate',
            limitations=spec.limitations+['Preflight response failed at '+phase+': '+type(exc).__name__]))
    (out/'preflight.json').write_bytes(json_bytes(result))
    (out/'model-spec.json').write_bytes(json_bytes(spec.model_dump(mode='json')))
    return spec,result
