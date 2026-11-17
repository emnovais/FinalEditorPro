import argparse,json
from ave.core import json_bytes
from ..analysis.pipeline import within_project
from .schemas import EditingSettings,EditingPackage
from .pipeline import enhance
from .preview import render
from .roundtrip import compare


def main():
    p=argparse.ArgumentParser(description='Local continuity/editing refinement; no model downloads or FCP automation')
    commands=p.add_subparsers(dest='command',required=True)
    e=commands.add_parser('enhance');e.add_argument('edl');e.add_argument('--output',required=True);e.add_argument('--settings');e.add_argument('--subjects');e.add_argument('--proposals');e.add_argument('--reference');e.add_argument('--cache',default='workspace/editing-cache')
    r=commands.add_parser('preview');r.add_argument('package');r.add_argument('--output',required=True)
    subjects=commands.add_parser('prepare-subjects');subjects.add_argument('edl');subjects.add_argument('--helper-manifest',required=True);subjects.add_argument('--output',required=True);subjects.add_argument('--images',default='workspace/subject-images');subjects.add_argument('--cache',default='workspace/editing-cache')
    rt=commands.add_parser('roundtrip');rt.add_argument('original');rt.add_argument('returned');rt.add_argument('--output',required=True)
    a=p.parse_args()
    if a.command=='enhance':
        settings=EditingSettings.model_validate_json(within_project(a.settings).read_text()) if a.settings else EditingSettings()
        result=enhance(a.edl,a.output,settings,subjects_path=a.subjects,cache=a.cache,proposal_dir=a.proposals,reference_edl=a.reference)
        print('Prepared:',within_project(a.output)/'timeline.fcpxml')
    elif a.command=='prepare-subjects':
        from .subjects import prepare
        print(prepare(a.edl,a.helper_manifest,a.output,a.images,a.cache))
    elif a.command=='preview':
        result=render(EditingPackage.model_validate_json(within_project(a.package).read_text()),a.output);print(json.dumps(result))
    else:
        result=compare(a.original,a.returned);dest=within_project(a.output)
        if dest.exists():raise FileExistsError('Comparison output must be new')
        dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('xb') as f:f.write(json_bytes(result))
        print(result['status'])

if __name__=='__main__':main()
