"""Semantic checks beyond the DTD; Final Cut manual import remains necessary."""
from fractions import Fraction
from pathlib import Path
import xml.etree.ElementTree as ET
from ave.core import seconds,sha256


def validate_xml(edl,xml):
    root=ET.fromstring(xml);seq=root.find('.//sequence');clips=seq.findall('./spine/asset-clip')
    if len(clips)!=len(edl.decisions) or seq.get('duration')!=seconds(Fraction(edl.total_frames)/Fraction(edl.brief.fps)):raise ValueError('XML timeline differs from EDL')
    assets={a.get('id'):a for a in root.findall('./resources/asset')}
    for clip,d in zip(clips,edl.decisions):
        media=next(m for m in edl.media if m['sha256']==d.asset_id)
        asset=assets[clip.get('ref')]
        if asset.find('media-rep').get('src')!=Path(media['path']).as_uri():raise ValueError('Wrong media reference')
        if clip.get('offset')!=seconds(d.timeline_start_seconds) or clip.get('duration')!=seconds(d.duration_seconds):raise ValueError('Cut clock mismatch')
        if d.speed!='1':
            points=clip.findall('./timeMap/timept')
            values=[seconds(Fraction(media['start'])+Fraction(v)) for v in (d.source_in_seconds,d.source_out_seconds)]
            if len(points)!=2 or [p.get('value') for p in points]!=values or points[-1].get('time')!=seconds(d.duration_seconds):raise ValueError('Retime differs from EDL')
            if clip.get('srcEnable')!='video':raise ValueError('Slow audio not disabled')
        elif clip.get('start')!=seconds(Fraction(media['start'])+Fraction(d.source_in_seconds)):raise ValueError('Source timecode mismatch')
    ids={e.get('id') for e in root.findall('./resources/*')}
    if any(node.get(attr) not in ids for node in root.iter() for attr in ('ref','format') if node.get(attr)):raise ValueError('Unresolved resource')
    return True
