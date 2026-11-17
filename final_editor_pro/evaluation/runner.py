"""Equivalent-input local model trials. Never silently substitutes an inference cache."""
from contextlib import contextmanager
import json
from pathlib import Path
import re
import secrets
import subprocess
import threading
import time
import urllib.error

from ave.core import json_bytes, sha256
from ..analysis.pipeline import within_project, fingerprint
from ..analysis.runtime import local_server
from ..analysis.ollama import LlamaServerTemporal
from ..ai.schemas import Task, validate_output
from .schemas import Trial,case_signature
from .dataset import load_input


class MeasuredTemporal(LlamaServerTemporal):
    def __init__(self,*args):
        super().__init__(*args); self.protocol_sha256=None; self.response=None; self.format_normalized=False

    def request(self,path,data=None):
        if data is not None:
            data=json.loads(json.dumps(data))
            schema=data.get('response_format',{}).get('json_schema',{}).get('schema')
            if schema:
                data['messages'][0]['content'][0]['text'] += ('\nOUTPUT CONTRACT: return ONLY one JSON object matching the following schema. '
                    'Do NOT echo the input/context. Do NOT use Markdown or code fences. Schema: '+json.dumps(schema,sort_keys=True))
            normalized=dict(data); normalized['model']='<MODEL>'
            self.protocol_sha256=fingerprint(dict(payload=normalized,runtime_protocol='content-only-schema-prompt-envelope-v3',context_tokens=8192))
        self.response=super().request(path,data)
        result=json.loads(json.dumps(self.response)); self.format_normalized=False
        if path=='/v1/chat/completions':
            content=result['choices'][0]['message']['content']
            envelope=re.fullmatch(r'```(?:json)?\s*\n(.*?)\n```',content.strip(),re.S)
            if envelope:
                result['choices'][0]['message']['content']=envelope.group(1)
                self.format_normalized=True
        return result


@contextmanager
def rss_observer(pid):
    peak=[0]; errors=[0]; stop=threading.Event()
    def sample():
        while not stop.is_set():
            try:
                result=subprocess.run(['/bin/ps','-o','rss=','-p',str(pid)],capture_output=True,text=True,timeout=2)
                if result.returncode==0 and result.stdout.strip(): peak[0]=max(peak[0],int(result.stdout.strip())*1024)
                else: errors[0]+=1
            except (OSError,ValueError,subprocess.TimeoutExpired): errors[0]+=1
            stop.wait(.25)
    observer=threading.Thread(target=sample,daemon=True); observer.start()
    try: yield peak,errors
    finally: stop.set(); observer.join(timeout=3)


def run_model(dataset, spec, input_dir, output, repetitions=3, case_ids=None, exploratory=False):
    if repetitions<3: raise ValueError('At least three independent sessions required')
    if spec.status!='ready': raise ValueError('Model must pass compatibility preflight before evaluation')
    out=within_project(output)
    if out.exists(): raise FileExistsError('Run output must be new')
    chosen=[c for c in dataset.cases if (case_ids is None or c.case_id in case_ids)]
    if not chosen: raise ValueError('No evaluation cases selected')
    if case_ids and set(case_ids)-{c.case_id for c in chosen}: raise ValueError('Unknown requested case ID')
    if not exploratory and (not dataset.frozen or any(c.split!='evaluation' for c in chosen)):
        raise ValueError('Final evaluation requires frozen held-out cases; use explicit exploratory mode otherwise')
    manifest=json.loads(within_project(spec.runtime_manifest).read_text())
    if manifest['manifest_sha256']!=spec.model_digest: raise ValueError('ModelSpec digest differs from runtime manifest')
    out.mkdir(parents=True)
    trials=[]
    for case in chosen:
        request,input_sha=load_input(within_project(input_dir)/(case.case_id+'.json'),case)
        for repetition in range(repetitions):
            session=out/(case.case_id+'-'+str(repetition)); session.mkdir()
            tick=time.perf_counter()
            try:
                runtime_metrics={}
                with local_server(spec.runtime_manifest,metrics=runtime_metrics,content_only=True) as process:
                    setup=time.perf_counter()-tick
                    adapter=MeasuredTemporal(manifest['model_name'],'http://127.0.0.1:11435',spec.model_digest)
                    metadata=adapter.request('/v1/models')
                    (session/'backend-metadata.json').write_bytes(json_bytes(metadata))
                    for condition in ('cold_inference','warm_inference'):
                        start=time.perf_counter(); result=None; error=None; details=[]; status='success'
                        adapter.response=None
                        with rss_observer(process.pid) as (peak,errors):
                            try:
                                result=validate_output(Task.TEMPORAL_VISUAL,request,adapter(request))
                            except (TimeoutError,urllib.error.URLError) as exc:
                                status='timeout' if isinstance(exc,TimeoutError) or isinstance(getattr(exc,'reason',None),TimeoutError) else 'failed'; error=type(exc).__name__
                            except Exception as exc:
                                status='failed'; error=type(exc).__name__
                                if hasattr(exc,'errors'): details=[{'type':e['type'],'loc':e['loc']} for e in exc.errors()]
                            latency=time.perf_counter()-start
                        usage=(adapter.response or {}).get('usage',{}); timing=(adapter.response or {}).get('timings',{})
                        tps=timing.get('predicted_per_second')
                        trial=Trial(trial_id=secrets.token_hex(16),model_id=spec.model_id,case_id=case.case_id,
                            repetition=repetition,condition=condition,input_sha256=input_sha,
                            protocol_sha256=adapter.protocol_sha256 or 'unavailable',status=status,latency_seconds=latency,
                            case_signature=case_signature(case),
                            setup_seconds=setup,load_ready_seconds=runtime_metrics.get('load_ready_seconds'),
                            format_normalized=adapter.format_normalized,
                            integrity_seconds=runtime_metrics.get('integrity_seconds'),server_rss_bytes=peak[0] or None,input_tokens=usage.get('prompt_tokens'),
                            output_tokens=usage.get('completion_tokens'),generation_tokens_per_second=tps if tps and tps>0 else None,
                            output=result,error_type=error,error_details=details,memory_sampling_errors=errors[0],
                            response_sha256=fingerprint(result.model_dump(mode='json')) if result else None)
                        trials.append(trial)
                        (session/(condition+'.json')).write_bytes(json_bytes(trial.model_dump(mode='json')))
                        if adapter.response is not None:
                            (session/(condition+'-wire-response.private.json')).write_bytes(json_bytes(adapter.response))
                        if result is not None:
                            cache=session/(condition+'-response-cache.json'); cache.write_bytes(json_bytes(result.model_dump(mode='json')))
                            cache_start=time.perf_counter()
                            from ..analysis.schemas import VisualAnalysis
                            restored=VisualAnalysis.model_validate_json(cache.read_text())
                            assert fingerprint(restored.model_dump(mode='json'))==trial.response_sha256
                            cached=trial.model_copy(update=dict(trial_id=secrets.token_hex(16),condition='report_cache',
                                latency_seconds=time.perf_counter()-cache_start,setup_seconds=0,
                                load_ready_seconds=None,integrity_seconds=None,server_rss_bytes=None,
                                input_tokens=None,output_tokens=None,generation_tokens_per_second=None))
                            trials.append(cached)
            except Exception as exc:
                # Keep previous observations; startup failures are actual failed attempts, not invented outputs.
                trials.append(Trial(trial_id=secrets.token_hex(16),model_id=spec.model_id,case_id=case.case_id,
                    repetition=repetition,condition='cold_inference',input_sha256=input_sha,protocol_sha256='unavailable',
                    case_signature=case_signature(case),
                    status='failed',latency_seconds=None,setup_seconds=time.perf_counter()-tick,error_type='startup_or_session_'+type(exc).__name__))
            if sha256(within_project(case.original_path))!=case.sha256: raise ValueError('Original changed during benchmark')
            (out/'trials.json').write_bytes(json_bytes([t.model_dump(mode='json') for t in trials]))
    (out/'provenance.json').write_bytes(json_bytes(dict(schema_version='0.2.1',model=spec.model_dump(mode='json'),
        dataset_sha256=fingerprint(dataset.model_dump(mode='json')),exploratory=exploratory,
        modality='ordered_timestamped_frames',context_tokens=8192,parallel_slots=1,
        runtime_protocol='content-only-schema-prompt-envelope-v3',
        generation='Analyzer-derived prompt plus explicit output schema; temperature=0, max_tokens=1800, repeat_penalty=1.1, frequency_penalty=.2; exact whole-JSON-fence normalization; no report cache in inference conditions',
        limitations=['Internal tokenizers/image encoders and prompt caches differ across architectures.',
                      'Cold means new server process, not an OS file-cache purge.',
                      'Startup includes integrity verification; RSS is sampled resident, not GPU/unified total.'])))
    return trials
