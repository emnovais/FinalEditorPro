"""Global take reuse audit, including non-neighboring clips."""


def audit(edl):
    groups={}
    for i,d in enumerate(edl.decisions):groups.setdefault(d.asset_id,[]).append(i)
    repeats=[dict(asset_id=asset,decisions=[i+1 for i in indices]) for asset,indices in groups.items() if len(indices)>1]
    overlap=[];exact=[]
    for indices in groups.values():
        for n,i in enumerate(indices):
            a=edl.decisions[i]
            for j in indices[n+1:]:
                b=edl.decisions[j];common=max(0,min(a.source_out_frame,b.source_out_frame)-max(a.source_in_frame,b.source_in_frame))
                if common:overlap.append(dict(decisions=[i+1,j+1],source_overlap_frames=common))
                if (a.source_in_frame,a.source_out_frame)==(b.source_in_frame,b.source_out_frame):exact.append([i+1,j+1])
    return dict(unique_sources=len(groups),segments=len(edl.decisions),reused_sources=repeats,overlapping_intervals=overlap,exact_repeats=exact,
        meaning='Different intervals from one file still repeat a take; visual similarity across different files is not proven by hashes.')
