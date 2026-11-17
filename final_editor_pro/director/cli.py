"""Local Creative Director. Remote CLI uploads are intentionally fail-closed."""
import argparse,json
from pathlib import Path
from ave.core import json_bytes
from ..analysis.pipeline import within_project
from ..analysis.runtime import local_server
from ..ai.config import ProcessingConfig,ProviderSettings,load_config
from ..ai.adapters import build_providers
from ..ai.privacy import PrivacyPolicy
from ..ai.router import ProcessingRouter,OperationJournal
from ..ai.schemas import Task
from .schemas import CreativeBrief,BriefRequest
from .pipeline import run_director


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['build','parse-brief'])
    p.add_argument('--brief');p.add_argument('--text-file');p.add_argument('--reports',nargs='+');p.add_argument('--proposals')
    p.add_argument('--output',required=True);p.add_argument('--model',choices=['qwen3-vl-8b-instruct','gemma3-12b'])
    p.add_argument('--global-config');p.add_argument('--project-config')
    args=p.parse_args()
    brief=CreativeBrief.model_validate_json(within_project(args.brief).read_text()) if args.brief else None
    model_id=args.model or (brief.model_id if brief else None)
    if not model_id:p.error('Explicit model required')
    if brief and args.model and brief.model_id!=args.model:p.error('Model override conflicts with brief')
    specs=json.loads(within_project('config/evaluation-models.json').read_text());spec=next(s for s in specs if s['model_id']==model_id)
    manifest=json.loads(within_project(spec['runtime_manifest']).read_text())
    if manifest['manifest_sha256']!=spec['model_digest']:raise ValueError('Model manifest binding mismatch')
    config=load_config(within_project(args.global_config),within_project(args.project_config) if args.project_config else None) if args.global_config else ProcessingConfig(providers={model_id:ProviderSettings(kind='local',adapter='llama-server',model=manifest['model_name'],enabled=True,capabilities=[Task.DIRECTION,Task.BRIEF],model_digest=spec['model_digest'])},routes={Task.DIRECTION:model_id,Task.BRIEF:model_id})
    logs=within_project('logs');logs.mkdir(exist_ok=True)
    router=ProcessingRouter(config,build_providers(config,PrivacyPolicy()),OperationJournal(logs/'director-ai.jsonl'))
    task=Task.DIRECTION if args.command=='build' else Task.BRIEF
    if router.select(task).remote:raise PermissionError('CLI has no interactive upload consent flow; no remote data sent')
    with local_server(spec['runtime_manifest'],content_only=True):
        if args.command=='parse-brief':
            if not args.text_file:p.error('--text-file required')
            request=BriefRequest(instruction=within_project(args.text_file).read_text())
            result=router.run(Task.BRIEF,request).output
            dest=within_project(args.output)
            if dest.exists():raise FileExistsError('Brief output must be new')
            dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('xb') as f:f.write(json_bytes(dict(status='proposal_requires_review',brief=result.model_dump(mode='json'))))
            print('Brief proposal saved; review essential fields before build:',dest)
        else:
            if not brief or not args.reports:p.error('--brief and --reports required')
            edl=run_director(brief,args.reports,args.output,router,proposal_dir=args.proposals)
            print('Timeline prepared; manual Final Cut validation pending:',within_project(args.output)/'timeline.fcpxml')

if __name__=='__main__':main()
