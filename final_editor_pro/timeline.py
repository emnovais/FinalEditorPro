"""Translate provider-independent creative decisions to the existing timeline JSON."""
from copy import deepcopy
from ave.core import validate
from .ai.schemas import AssetSummary, PlanningInput, CreativePlan, validate_output, Task


def planning_input(project, brief):
    from fractions import Fraction
    return PlanningInput(brief=brief, assets=[AssetSummary(
        asset_id=f'asset-{i}', total_frames=int(Fraction(m['duration']) * Fraction(m['fps'])))
        for i, m in enumerate(project['media'])])


def apply_plan(project, creative_plan):
    request = planning_input(project, 'Validate existing creative decisions')
    creative_plan = validate_output(Task.PLANNING, request, CreativePlan.model_validate(creative_plan))
    indices = {a.asset_id: i for i, a in enumerate(request.assets)}
    result = deepcopy(project)
    result['clips'] = [dict(media=indices[c.asset_id], in_frames=c.in_frames,
                            duration_frames=c.duration_frames) for c in creative_plan.cuts]
    result['decisions'] = dict(strategy='creative-plan-v1', model=None, effects=[],
                               creative_plan=creative_plan.model_dump(mode='json'))
    validate(result)
    return result
