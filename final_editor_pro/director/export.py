"""Explicit MVP 0.3 conform/retime/music adapter around the unchanged MVP 0.1 exporter."""
from fractions import Fraction
from pathlib import Path
import xml.etree.ElementTree as ET
from ave.core import plan,export_xml,validate,seconds,sha256
from .schemas import EditDecisionList


def timeline_project(edl):
    edl=EditDecisionList.model_validate(edl)
    project=plan(edl.media,'Final Editor Pro — Creative Director 0.3')
    indices={m['sha256']:i for i,m in enumerate(edl.media)}
    project['clips']=[dict(media=indices[d.asset_id],in_frames=d.source_in_frame,duration_frames=d.source_out_frame-d.source_in_frame) for d in edl.decisions]
    project['decisions']=dict(strategy='director-0.3',effects=[],edl_version=edl.version)
    validate(project)
    return project


def export_edl(edl):
    edl=EditDecisionList.model_validate(edl); project=timeline_project(edl)
    root=ET.fromstring(export_xml(project)); resources=root.find('resources')
    fmt=resources.find("format[@id='r_sequence']")
    fmt.attrib.pop('name',None) # Custom 4:3 geometry: never invent an Apple preset name.
    fmt.set('width',str(edl.brief.output_width)); fmt.set('height',str(edl.brief.output_height));fmt.set('frameDuration',seconds(1/Fraction(edl.brief.fps)))
    seq=root.find('.//sequence');seq.set('duration',seconds(Fraction(edl.total_frames)/Fraction(edl.brief.fps)))
    clips=seq.findall('./spine/asset-clip'); lookup={m['sha256']:m for m in edl.media}
    for clip,d in zip(clips,edl.decisions):
        media=lookup[d.asset_id]; source_start=Fraction(media['start'])+Fraction(d.source_in_seconds)
        clip.set('offset',seconds(d.timeline_start_seconds));clip.set('duration',seconds(d.duration_seconds))
        ET.SubElement(clip,'adjust-conform',type='fill')
        # Explicitly disable automatic rate scaling: normal playback drops alternate
        # frames; only the explicit linear timeMap changes playback speed.
        conform=ET.Element('conform-rate',scaleEnabled='0',srcFrameRate=str(Fraction(d.source_fps)),frameSampling='floor');clip.insert(0,conform)
        if d.speed!='1':
            clip.set('start','0s');clip.set('srcEnable','video')
            time_map=ET.Element('timeMap',frameSampling='floor',preservesPitch='1')
            ET.SubElement(time_map,'timept',time='0s',value=seconds(source_start),interp='linear')
            ET.SubElement(time_map,'timept',time=seconds(d.duration_seconds),value=seconds(Fraction(media['start'])+Fraction(d.source_out_seconds)),interp='linear')
            clip.insert(1,time_map)
        else: clip.set('start',seconds(source_start))
    if edl.music:
        music=edl.music; path=Path(music['path'])
        if sha256(path)!=music['sha256']: raise ValueError('Music changed')
        total=Fraction(edl.total_frames)/Fraction(edl.brief.fps)
        if Fraction(music['duration_seconds'])<total: raise ValueError('Music shorter than timeline')
        asset=ET.SubElement(resources,'asset',id='music0',name=path.name,start='0s',duration=seconds(music['duration_seconds']),hasVideo='0',hasAudio='1',audioSources='1',audioChannels=str(music['channels']),audioRate=str(music['sample_rate']))
        ET.SubElement(asset,'media-rep',kind='original-media',src=path.as_uri())
        # Connected offsets use the parent clip's local (retimed) timeline origin.
        audio=ET.SubElement(clips[0],'audio',ref='music0',name=path.stem,lane='-1',offset=clips[0].get('start'),start='0s',duration=seconds(total),role='music')
        ET.SubElement(audio,'adjust-volume',amount='-12dB')
    ET.indent(root)
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)
