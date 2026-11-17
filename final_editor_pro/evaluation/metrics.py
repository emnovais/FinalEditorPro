"""Objective descriptors and explicitly incomplete, human-informed comparisons."""
import math
from statistics import median,quantiles
from .schemas import CRITERIA, EvaluationWeights,case_signature


def summary(values):
    values=[v for v in values if v is not None]
    if not values: return dict(n=0,median=None,iqr=None,min=None,max=None)
    if any(not math.isfinite(v) for v in values): raise ValueError('Nonfinite observation')
    q=quantiles(values,n=4,method='inclusive') if len(values)>1 else None
    return dict(n=len(values),median=median(values),iqr=q[2]-q[0] if q else None,min=min(values),max=max(values))


def interval_iou(a,b):
    intersection=max(0,min(a[1],b[1])-max(a[0],b[0]))
    union=max(a[1],b[1])-min(a[0],b[0])
    return intersection/union if union else 0


def label_metrics(predictions,facts,exhaustive=False):
    """Exact human-supplied labels/aliases only. A nonmatch is not proof of hallucination."""
    normalized={p.casefold().strip() for p in predictions}
    matched=sum(bool(normalized & {f.label.casefold().strip(),*[a.casefold().strip() for a in f.aliases]}) for f in facts)
    supported=sum(any(p in {f.label.casefold().strip(),*[a.casefold().strip() for a in f.aliases]} for f in facts) for p in normalized)
    return dict(reference_labels=len(facts),prediction_labels=len(normalized),matched_references=matched,
                recall=matched/len(facts) if facts else None,
                precision=supported/len(normalized) if exhaustive and normalized else None,
                caveat='Exact annotated aliases; unmatched text is not automatically a hallucination.')


def compare(dataset, trials, reviews_by_trial, weights=None, speed_reference_seconds=10, memory_reference_bytes=36_000_000_000):
    weights=weights or EvaluationWeights()
    if speed_reference_seconds<=0 or memory_reference_bytes<=0: raise ValueError('Normalization references must be positive')
    cases={c.case_id:c for c in dataset.cases}; candidates=[]; reasons=[]
    compared_cases={t.case_id for t in trials if t.condition!='report_cache'}
    from ..analysis.pipeline import within_project
    from ave.core import sha256
    for c in dataset.cases:
        if c.reference.source_path and sha256(within_project(c.reference.source_path))!=c.reference.source_sha256:
            raise ValueError('Human reference source changed after import')
    if len({t.trial_id for t in trials})!=len(trials): raise ValueError('Duplicate trial IDs')
    inference_keys=[(t.model_id,t.case_id,t.repetition,t.condition) for t in trials if t.condition!='report_cache']
    if len(set(inference_keys))!=len(inference_keys): raise ValueError('Duplicate session/condition observations')
    if any(t.case_id not in cases for t in trials): raise ValueError('Trial refers to an unknown dataset case')
    for t in trials:
        if t.case_signature is None: reasons.append('Trial lacks source/interval provenance')
        elif t.case_signature!=case_signature(cases[t.case_id]): raise ValueError('Dataset source or interval changed since trial')
    for model_id in sorted({t.model_id for t in trials}):
        own=[t for t in trials if t.model_id==model_id and t.condition!='report_cache']
        successful=[t for t in own if t.status=='success']
        warm=[t for t in successful if t.condition=='warm_inference']
        reviews=[reviews_by_trial[t.trial_id] for t in successful if t.trial_id in reviews_by_trial]
        if len({t.protocol_sha256 for t in own})>len({t.case_id for t in own}):
            reasons.append('Protocol differs within a case')
        for t in successful:
            if t.trial_id in reviews_by_trial and reviews_by_trial[t.trial_id].response_sha256!=t.response_sha256:
                raise ValueError('Review refers to a different response')
        ratio=len(successful)/len(own) if own else 0
        all_reviewed=bool(successful) and len(reviews)==len(successful)
        complete_case_coverage={t.case_id for t in successful}==compared_cases
        complete_warm_coverage={t.case_id for t in warm}==compared_cases
        values={k:None for k in CRITERIA}
        if all_reviewed:
            for criterion in CRITERIA[:4]:
                if complete_case_coverage or criterion=='reliability':
                    values[criterion]=sum(getattr(r,criterion)/4 for r in reviews)/len(reviews)
            if values['reliability'] is not None: values['reliability']*=ratio
        latency=summary([t.latency_seconds for t in warm])
        memory=summary([t.server_rss_bytes for t in own])
        if latency['median'] is not None and complete_warm_coverage: values['speed']=1/(1+latency['median']/speed_reference_seconds)
        if memory['median'] is not None: values['memory_efficiency']=1/(1+memory['median']/memory_reference_bytes)
        complete=all(v is not None for v in values.values())
        aggregate=sum(values[k]*getattr(weights,k) for k in CRITERIA) if complete else None
        task_metrics=[]
        for t in successful:
            ref=cases[t.case_id].reference
            if ref.status=='verified':
                task_metrics.append(dict(trial_id=t.trial_id,objects=label_metrics(t.output.objects,ref.objects,ref.objects_exhaustive),
                                         actions=label_metrics(t.output.actions,ref.actions)))
        adequate=all(len({t.repetition for t in own if t.case_id==case and t.condition=='cold_inference'})>=3
                     for case in {t.case_id for t in own})
        candidates.append(dict(model_id=model_id,criteria=values,weighted_score=aggregate,
            success_rate=ratio,failures=len(own)-len(successful),reviewed=len(reviews),successful_responses=len(successful),
            complete_valid_case_coverage=complete_case_coverage,
            case_results=[dict(case_id=c,attempts=sum(t.case_id==c for t in own),valid=sum(t.case_id==c for t in successful),
                cold_latency_seconds=summary([t.latency_seconds for t in successful if t.case_id==c and t.condition=='cold_inference']),
                warm_latency_seconds=summary([t.latency_seconds for t in warm if t.case_id==c])) for c in sorted(compared_cases)],
            unique_human_judgments=len({r.blind_id for r in reviews}),human_reviewers=len({r.reviewer for r in reviews}),
            distinct_valid_response_hashes=len({t.response_sha256 for t in successful}),
            failure_types={e:sum(t.error_type==e for t in own if t.status!='success') for e in sorted({t.error_type for t in own if t.status!='success' and t.error_type})},
            json_envelopes_normalized=sum(t.format_normalized for t in own),
            warm_latency_seconds=latency,cold_latency_seconds=summary([t.latency_seconds for t in successful if t.condition=='cold_inference']),
            report_cache_latency_seconds=summary([t.latency_seconds for t in trials if t.model_id==model_id and t.condition=='report_cache']),
            failed_latency_seconds=summary([t.latency_seconds for t in own if t.status!='success']),
            setup_seconds=summary([t.setup_seconds for t in own if t.condition=='cold_inference']),
            load_ready_seconds=summary([t.load_ready_seconds for t in own if t.condition=='cold_inference']),
            integrity_seconds=summary([t.integrity_seconds for t in own if t.condition=='cold_inference']),
            observed_server_rss_bytes=memory,tokens_per_second=summary([t.generation_tokens_per_second for t in successful]),
            repetition_requirement_met=adequate,objective_label_checks=task_metrics))
    # Comparable entries for each case must use exactly the same inputs/protocols.
    for case in {t.case_id for t in trials}:
        signatures={(t.input_sha256,t.protocol_sha256) for t in trials if t.case_id==case and t.condition!='report_cache'}
        if len(signatures)>1: reasons.append('Different input/protocol signatures for '+case)
    if len(candidates)<2: reasons.append('Fewer than two evaluated models')
    if not dataset.frozen: reasons.append('Dataset lacks final frozen human references/splits')
    if not any(c.split=='evaluation' for c in dataset.cases): reasons.append('No held-out evaluation cases')
    from .dataset import coverage
    dataset_coverage=coverage(dataset)
    if dataset_coverage['missing_categories']: reasons.append('Requested categories remain unrepresented')
    expected_cases={c.case_id for c in dataset.cases if c.split=='evaluation'}
    if expected_cases and any({t.case_id for t in trials if t.model_id==m['model_id'] and t.condition!='report_cache'}!=expected_cases for m in candidates):
        reasons.append('Models did not evaluate the same complete held-out cases')
    if any(c['weighted_score'] is None for c in candidates): reasons.append('Human reviews or measurements missing; weights not redistributed')
    if any(not c['complete_valid_case_coverage'] for c in candidates): reasons.append('Valid output coverage differs; do not rank on an easier successful subset')
    if any(not c['repetition_requirement_met'] for c in candidates): reasons.append('Insufficient independent repetitions')
    return dict(schema_version='0.2.1',weights=weights.model_dump(),models=candidates,
                dataset_coverage=dataset_coverage,
                conclusion='inconclusive' if reasons else 'review_required',reasons=sorted(set(reasons)),
                automatic_winner=None,
                normalization=dict(speed_reference_seconds=speed_reference_seconds,memory_reference_bytes=memory_reference_bytes,
                    formula='speed=1/(1+warm_median/reference); memory=1/(1+RSS_median/reference); reliability=human_mean*success_rate'),
                tradeoffs='Compare individual criteria, uncertainty, dataset coverage and failures before assigning models to tasks.')
