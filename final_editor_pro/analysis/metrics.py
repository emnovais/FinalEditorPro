"""Small-proxy heuristics. Values are observations, never automatic rejection."""
from math import exp, isfinite
from statistics import mean, pvariance
from .schemas import TechnicalMetrics, ShotScore, ScoreComponent

COMPONENTS = ('technical_quality', 'visual_relevance', 'action_presence',
              'narrative_potential', 'transition_potential', 'confidence')
PROFILES = {
    'restaurant': (2, 3, 1, 1, 2, 1), 'wedding': (1, 2, 2, 4, 1, 2),
    'event': (2, 2, 3, 2, 1, 2), 'travel': (2, 3, 2, 2, 2, 1),
    'social': (2, 2, 3, 1, 3, 1),
}


def gray(rgb):
    return bytes((77 * rgb[i] + 150 * rgb[i+1] + 29 * rgb[i+2]) >> 8
                 for i in range(0, len(rgb), 3))


def histogram(g):
    bins = [0] * 32
    for x in g: bins[x // 8] += 1
    return [x / len(g) for x in bins]


def hist_distance(a, b):
    return sum(abs(x-y) for x,y in zip(a,b)) / 2


def difference(a, b):
    return sum(abs(x-y) for x,y in zip(a,b)) / (255 * len(a))


def measure(rgb, width, height):
    g = gray(rgb)
    lap = [4*g[y*width+x] - g[y*width+x-1] - g[y*width+x+1]
           - g[(y-1)*width+x] - g[(y+1)*width+x]
           for y in range(1,height-1) for x in range(1,width-1)]
    return dict(sharpness=pvariance(lap), luma=mean(g)/255,
                dark=sum(v <= 12 for v in g)/len(g), bright=sum(v >= 243 for v in g)/len(g)), g, histogram(g)


def aggregate(metrics, differences):
    return TechnicalMetrics(sampled_frames=len(metrics),
        sharpness_laplacian_variance=mean(m['sharpness'] for m in metrics),
        mean_luma=mean(m['luma'] for m in metrics),
        dark_fraction=mean(m['dark'] for m in metrics), bright_fraction=mean(m['bright'] for m in metrics),
        interframe_difference=mean(differences) if differences else 0,
        instability_proxy=mean(abs(a-b) for a,b in zip(differences,differences[1:])) if len(differences)>1 else 0,
        caveats=['Proxy-space metrics; no camera Log/HDR normalization.',
                 'Darkness, highlights and blur may be intentional; no automatic discard.',
                 'Interframe difference mixes camera/object motion and lighting; not optical flow.',
                 'Laplacian variance depends on proxy scale, noise and subject texture.'])


def score(technical, visual, profile, overrides=None):
    weights = dict(zip(COMPONENTS, PROFILES[profile]))
    if overrides is not None:
        if set(overrides) - set(weights) or any(not isfinite(w) or w < 0 for w in overrides.values()):
            raise ValueError('Unknown or invalid scoring weight')
        weights.update(overrides)
    if not sum(weights.values()): raise ValueError('Scoring weights cannot all be zero')
    sharp = 1-exp(-technical.sharpness_laplacian_variance/2000)
    exposure = 1-(technical.dark_fraction+technical.bright_fraction)
    values = {'technical_quality': ((sharp+exposure)/2,
                'Equal proxy sharpness/exposure indicators; stylistic intent is unknown.')}
    for name in COMPONENTS[1:-1]:
        value = visual.assessments.get(name) if visual else None
        reason = visual.assessment_reasons.get(name, 'Insufficient semantic evidence') if visual else 'Semantic analysis not available'
        values[name] = (value, reason)
    values['confidence'] = (visual.confidence if visual else None, 'Model self-reported, uncalibrated confidence' if visual else 'No semantic model result')
    components = {name: ScoreComponent(value=values[name][0], weight=weights[name], reason=values[name][1]) for name in COMPONENTS}
    available = sum(c.weight for c in components.values() if c.value is not None)
    combined = sum(c.value*c.weight for c in components.values() if c.value is not None)/available if available else None
    return ShotScore(profile=profile, components=components, weighted_score=combined,
                     available_weight_fraction=available/sum(weights.values()))
