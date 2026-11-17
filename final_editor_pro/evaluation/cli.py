"""Local reproducible evaluation CLI. Downloads/installations are never implicit."""
import argparse
import json
from ave.core import json_bytes
from ..analysis.pipeline import within_project
from .schemas import EvaluationDataset, EvaluationWeights, ModelSpec, Trial
from .dataset import inventory, coverage, freeze_input
from .runner import run_model
from .review import create_blind_packet, load_reviews
from .metrics import compare


def load_trials(paths):
    rows=[]
    for path in paths:
        rows += [Trial.model_validate(t) for t in json.loads(within_project(path).read_text())]
    if len({t.trial_id for t in rows})!=len(rows): raise ValueError('Duplicate trial IDs')
    return rows


def save(path,value):
    p=within_project(path)
    if p.exists(): raise FileExistsError('Refusing to overwrite an evaluation artifact')
    p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(json_bytes(value))


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    inv=sub.add_parser('inventory'); inv.add_argument('media'); inv.add_argument('--output',required=True)
    cov=sub.add_parser('coverage'); cov.add_argument('dataset')
    annotate=sub.add_parser('annotate'); annotate.add_argument('dataset'); annotate.add_argument('--output',required=True)
    imported=sub.add_parser('import-descriptions'); imported.add_argument('dataset'); imported.add_argument('source'); imported.add_argument('--output',required=True)
    check=sub.add_parser('preflight'); check.add_argument('dataset'); check.add_argument('model_spec'); check.add_argument('case_id'); check.add_argument('--input',required=True); check.add_argument('--output',required=True)
    freeze=sub.add_parser('freeze-input'); freeze.add_argument('dataset'); freeze.add_argument('case_id'); freeze.add_argument('report'); freeze.add_argument('--output',required=True)
    run=sub.add_parser('run'); run.add_argument('dataset'); run.add_argument('model_spec'); run.add_argument('--inputs',required=True); run.add_argument('--output',required=True)
    run.add_argument('--repetitions',type=int,default=3); run.add_argument('--cases',nargs='+'); run.add_argument('--exploratory',action='store_true')
    blind=sub.add_parser('blind'); blind.add_argument('trials',nargs='+'); blind.add_argument('--output',required=True)
    blind.add_argument('--dataset'); blind.add_argument('--inputs')
    rank=sub.add_parser('compare'); rank.add_argument('dataset'); rank.add_argument('trials',nargs='+'); rank.add_argument('--reviews'); rank.add_argument('--identity-map'); rank.add_argument('--weights',default='config/evaluation-weights.json'); rank.add_argument('--output',required=True)
    args=p.parse_args()
    if args.command=='inventory':
        result=coverage(inventory(args.media,args.output))
    elif args.command=='blind':
        dataset=EvaluationDataset.model_validate_json(within_project(args.dataset).read_text()) if args.dataset else None
        result=create_blind_packet(load_trials(args.trials),args.output,dataset,args.inputs)
    else:
        dataset=EvaluationDataset.model_validate_json(within_project(args.dataset).read_text())
        if args.command=='coverage': result=coverage(dataset)
        elif args.command=='annotate':
            from .annotation import create_annotation_form
            result={'form':str(create_annotation_form(dataset,args.output))}
        elif args.command=='import-descriptions':
            from .import_reference import import_descriptions
            _,result=import_descriptions(dataset,args.source,args.output)
        elif args.command=='preflight':
            from .preflight import preflight
            spec=ModelSpec.model_validate_json(within_project(args.model_spec).read_text())
            _,result=preflight(dataset,spec,args.input,args.case_id,args.output)
        elif args.command=='freeze-input':
            case=next(c for c in dataset.cases if c.case_id==args.case_id)
            packet=freeze_input(case,args.report,args.output)
            result={'case_id':case.case_id,'input_sha256':packet['input_sha256']}
        elif args.command=='run':
            spec=ModelSpec.model_validate_json(within_project(args.model_spec).read_text())
            trials=run_model(dataset,spec,args.inputs,args.output,args.repetitions,args.cases,args.exploratory)
            result={'trials':len(trials),'failures':sum(t.status!='success' for t in trials)}
        else:
            if bool(args.reviews)!=bool(args.identity_map): raise ValueError('Reviews and identity map must be supplied together')
            reviews=load_reviews(args.reviews,args.identity_map) if args.reviews else {}
            result=compare(dataset,load_trials(args.trials),reviews,EvaluationWeights.model_validate_json(within_project(args.weights).read_text()))
            save(args.output,result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
