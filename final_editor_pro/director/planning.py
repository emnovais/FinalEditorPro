"""Provider-independent direction contracts and local text adapter."""
import json,re
from fractions import Fraction
from ..analysis.ollama import OllamaTemporal
from .schemas import CreativeBrief,BriefInterpretation,NarrativePlan,validate_direction

class LocalDirectorAdapter(OllamaTemporal):
    def generate(self,request,schema,instruction):
        payload=request.model_dump(mode='json')
        if 'candidates' in payload:
            payload['candidates']=[dict(candidate_id=c.candidate_id,asset_id=c.asset_id[:16],available_normal_seconds=float(Fraction(c.end_frame-c.start_frame)/Fraction(c.fps)),available_half_speed_seconds=float(2*Fraction(c.end_frame-c.start_frame)/Fraction(c.fps)),start_frame=c.start_frame,end_frame=c.end_frame,fps=c.fps,description=c.description[:260],confidence=c.confidence,components={k:round(v,3) if v is not None else None for k,v in c.components.items()},technical={k:round(v,3) for k,v in c.technical.items() if k in ('mean_luma','sharpness_laplacian_variance','instability_proxy')},observed_actions=list(dict.fromkeys(e for row in c.interpretations for e in row.get('events',[])))[:2]) for c in request.candidates]
        content=instruction+'\nReturn ONLY JSON, no Markdown. Schema: '+json.dumps(schema.model_json_schema())+'\nInput: '+json.dumps(payload)
        raw=self.request('/v1/chat/completions',dict(model=self.model,temperature=0,max_tokens=2000,
            messages=[dict(role='user',content=content)],response_format=dict(type='json_schema',json_schema=dict(name='director',schema=schema.model_json_schema()))))
        self.last_wire=raw
        choice=raw['choices'][0]
        if choice.get('finish_reason')=='length': raise ValueError('Planning output truncated')
        text=choice['message']['content'].strip(); fence=re.fullmatch(r'```(?:json)?\s*\n(.*?)\n```',text,re.S)
        if fence: text=fence.group(1)
        return schema.model_validate_json(text)
    def plan(self,request):
        instruction=('Select and order candidates for a rough cut matching the brief. Use ONLY supplied candidate IDs once each. '
          'FIRST choice role MUST be opening; LAST choice role MUST be ending; middle choices development or highlight. '
          'Choose 5 to 7 candidates when available; cumulative available duration at chosen speed must reach target_seconds. '
          'Respect max_shots_per_asset across the ENTIRE sequence; different candidate IDs from the same asset are the same take. '
          'Avoid redundant descriptions; vary sources/framing/action where supported. '
          'Use speed 1/2 for at least one emotional moment when slow_motion_allowed is true, otherwise speed 1. '
          'Explain each choice and relation to brief. Do not invent events. Report unmet subjective constraints as warnings. '
          'Be concise: one short sentence each for reason and brief_relation, at most 8 choices.')
        self.attempts=[]
        for attempt in range(3):
            self.last_wire=None
            try:
                result=self.generate(request,NarrativePlan,instruction)
                from .selection import assign_boundary_roles
                result=assign_boundary_roles(result)
                validate_direction(request,result)
                self.attempts.append(dict(attempt=attempt,status='accepted',response=self.last_wire))
                return result
            except ValueError as exc:
                self.attempts.append(dict(attempt=attempt,status='rejected',error=str(exc)[:1000],response=self.last_wire))
                if attempt==2:raise
                previous=(self.last_wire or {}).get('choices',[{}])[0].get('message',{}).get('content','')
                instruction += ('\nPrevious proposal rejected: '+str(exc)[:700]+'. Correct this constraint without changing provider. '
                    'Previous JSON: '+previous[:4500])
        raise RuntimeError('Unreachable')
    def brief(self,request):
        return self.generate(request,BriefInterpretation,'Extract a brief ONLY from explicit instructions. If essential fields are absent, return brief null and list missing_fields. Never invent them. For a complete brief, field_evidence must quote exact substrings of input for project_type, objective, target_seconds, aspect_ratio, fps, output_width, output_height, visual_style, pace, model_id. Optional lists may be empty and music_path null. Model ID must be explicit. Result is a proposal for review, not an executable edit.')
