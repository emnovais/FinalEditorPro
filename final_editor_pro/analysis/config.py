"""Persistent analyzer defaults with explicit project overrides, no Home writes."""
import json
from .pipeline import within_project
from .schemas import AnalysisConfig


def load_analysis_config(global_path=None, project_path=None):
    data=AnalysisConfig().model_dump(mode='json')
    for path in (global_path,project_path):
        if path is None: continue
        patch=json.loads(within_project(path).read_text())
        if not isinstance(patch,dict): raise ValueError('Analysis config must be an object')
        if patch.get('score_weights') is not None:
            patch['score_weights']={**(data.get('score_weights') or {}),**patch['score_weights']}
        data.update(patch)
        # Validate every layer; a project override cannot hide an invalid global file.
        data=AnalysisConfig.model_validate(data).model_dump(mode='json')
    return AnalysisConfig.model_validate(data)
