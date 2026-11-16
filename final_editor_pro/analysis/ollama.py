"""Optional local VLM adapter; no model pulling, external URLs, tools or retries."""
import json
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler
from ..ai.adapters import _NoRedirect
from .schemas import VisualAnalysis


class OllamaTemporal:
    def __init__(self, model, endpoint, digest):
        url=urlsplit(endpoint)
        if (url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port
            or url.username or url.password or url.path not in ('','/') or url.query or url.fragment):
            raise ValueError('Local inference requires an explicit IPv4 loopback endpoint')
        if not digest or len(digest.removeprefix('sha256:')) != 64 or 'cloud' in model.lower():
            raise ValueError('Approved local model manifest digest required; cloud models forbidden')
        self.model,self.endpoint,self.digest=model,endpoint.rstrip('/'),digest.removeprefix('sha256:')
        self.last_usage={}

    def request(self, path, data=None):
        body=json.dumps(data).encode() if data is not None else None
        req=Request(self.endpoint+path, data=body, headers={'Content-Type':'application/json'})
        opener=build_opener(ProxyHandler({}),_NoRedirect())
        with opener.open(req,timeout=300) as response:
            raw=response.read(4_000_001)
        if len(raw)>4_000_000: raise ValueError('Local model response too large')
        return json.loads(raw)

    def __call__(self, request):
        models=self.request('/api/tags')['models']
        if not any(m.get('name')==self.model and m.get('digest','').removeprefix('sha256:')==self.digest for m in models):
            raise PermissionError('Local model is absent or differs from approved manifest')
        metadata=request.model_dump(mode='json')
        for f in metadata['frames']: del f['data_base64']
        prompt=('Analyze ONLY the supplied chronological frames from one video interval. '
                'Do not infer speech, identities, unseen events, intent or facts outside frames. '
                'Actions/movement require comparison of multiple frames. Distinguish apparent camera '
                'and object motion only when visible; otherwise say uncertain. A single frame cannot '
                'establish action. List uncertainties even when confident. Evidence indices must be '
                'from the supplied frame_index list. Opportunities are speculative suggestions, never '
                'implemented effects. Optional assessments are subjective 0..1 or null with reasons. '
                'Return the JSON schema provided. Context: '+json.dumps(metadata))
        response=self.request('/api/chat', dict(model=self.model,stream=False,
            format=VisualAnalysis.model_json_schema(),keep_alive='2m',
            options={'temperature':0,'num_ctx':8192,'num_predict':1536},
            messages=[{'role':'user','content':prompt,'images':[f.data_base64 for f in request.frames]}]))
        if response.get('done_reason') == 'length': raise ValueError('Semantic output was truncated')
        self.last_usage={k:response.get(k) for k in ('total_duration','load_duration','prompt_eval_count','eval_count')}
        return VisualAnalysis.model_validate_json(response['message']['content'])


class LlamaServerTemporal(OllamaTemporal):
    """llama.cpp server bundled in approved Ollama archive; no Ollama identity files."""
    def __call__(self, request):
        metadata=request.model_dump(mode='json')
        for f in metadata['frames']: del f['data_base64']
        prompt=('Analyze these chronological video frames. First describe the concrete visible '
                'people, clothing, objects and setting. Be concise: ONE short sentence per text '
                'field (at most 25 words); lists at most three short items. Never repeat phrases. '
                'Compare frames for apparent action/motion, but do not invent speech, identities, '
                'intent or unseen events. State specific uncertainty briefly. Evidence indices '
                'must come from supplied frame_index values; cite at least TWO different frames '
                'for actions. Opportunities are speculative '
                'suggestions only. Subjective scores may be null; briefly explain each score. '
                'Return every required schema field. Context: '+json.dumps(metadata))
        content=[{'type':'text','text':prompt}]+[
            {'type':'image_url','image_url':{'url':'data:image/png;base64,'+f.data_base64}} for f in request.frames]
        schema=VisualAnalysis.model_json_schema()
        evidence_indices=[f.frame_index for f in request.frames]
        schema['properties']['evidence_frame_indices']['items']['enum']=evidence_indices
        schema['properties']['evidence_frame_indices']['minItems']=min(2,len(evidence_indices))
        schema['properties']['evidence_frame_indices']['uniqueItems']=True
        schema['$defs']['TransitionOpportunity']['properties']['evidence_frame_indices']['items']['enum']=evidence_indices
        names=('visual_relevance','action_presence','narrative_potential','transition_potential')
        schema['properties']['assessments']={'type':'object','properties':{n:{'type':['number','null'],'minimum':0,'maximum':1} for n in names},'required':list(names),'additionalProperties':False}
        schema['properties']['assessment_reasons']={'type':'object','properties':{n:{'type':'string'} for n in names},'required':list(names),'additionalProperties':False}
        schema['required']=list(dict.fromkeys(schema['required']+['assessments','assessment_reasons']))
        result=self.request('/v1/chat/completions',dict(model=self.model,stream=False,
            messages=[{'role':'user','content':content}],temperature=0,max_tokens=1800,
            repeat_penalty=1.1,frequency_penalty=.2,
            response_format={'type':'json_schema','json_schema':{'name':'visual_analysis',
                'schema':schema}}))
        choice=result['choices'][0]
        if choice.get('finish_reason')=='length': raise ValueError('Semantic output truncated')
        self.last_usage=result.get('usage',{})
        return VisualAnalysis.model_validate_json(choice['message']['content'])
