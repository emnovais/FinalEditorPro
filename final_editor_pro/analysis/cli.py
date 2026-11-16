"""Local video analyzer CLI. Does not install models or alter FCPXML."""
import argparse
from pathlib import Path
from .pipeline import analyze, within_project
from .schemas import AnalysisConfig
from .config import load_analysis_config
from ..ai.config import load_config, ProcessingConfig
from ..ai.adapters import build_providers
from ..ai.privacy import PrivacyPolicy
from ..ai.router import ProcessingRouter, OperationJournal


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('media')
    parser.add_argument('--output',required=True)
    parser.add_argument('--cache',default='workspace/analysis-cache')
    parser.add_argument('--analysis-config')
    parser.add_argument('--project-analysis-config')
    parser.add_argument('--global-config')
    parser.add_argument('--project-config')
    parser.add_argument('--ffmpeg',default='/opt/homebrew/bin/ffmpeg')
    parser.add_argument('--ffprobe',default='/opt/homebrew/bin/ffprobe')
    args=parser.parse_args()
    config=load_analysis_config(args.analysis_config,args.project_analysis_config)
    processing=load_config(within_project(args.global_config),within_project(args.project_config) if args.project_config else None) if args.global_config else ProcessingConfig()
    logs=within_project('logs'); logs.mkdir(exist_ok=True)
    policy=PrivacyPolicy()
    router=ProcessingRouter(processing,build_providers(processing,policy),OperationJournal(logs/'analysis-ai.jsonl')) if config.semantic else None
    # Remote execution via this CLI is intentionally fail-closed. Applications can
    # use router.preview_upload + human consent per segment through the Python API.
    if router and router.select('temporal_visual_analysis').remote:
        raise PermissionError('Remote analyzer CLI requires a future interactive consent flow; no upload performed')
    result=analyze(args.media,args.output,args.cache,config,ffprobe=args.ffprobe,ffmpeg=args.ffmpeg,router=router)
    print('Analysis status:',result.benchmark['status'])
    print('Report:',str(within_project(args.output)/'analysis.json'))
    if result.benchmark['status']!='complete': raise SystemExit(2)


if __name__=='__main__': main()
