"""Additional XML layer; the validated 0.3 exporter stays unchanged."""
from fractions import Fraction
import xml.etree.ElementTree as ET
from ave.core import seconds
from ..director.export import export_edl
from .schemas import EditingPackage


def apply_envelope(parent,envelope,origin='0'):
    adjust=parent.find('adjust-volume')
    if adjust is None:
        adjust=ET.Element('adjust-volume');parent.append(adjust)
    adjust.clear();adjust.set('amount',f'{max(g for t,g in envelope.points):.6f}dB')
    param=ET.SubElement(adjust,'param',name='amount')
    animation=ET.SubElement(param,'keyframeAnimation')
    for t,gain in envelope.points:
        ET.SubElement(animation,'keyframe',time=seconds(Fraction(origin.removesuffix('s'))+Fraction(t)),value=f'{gain:.6f}dB')
    return adjust


def export_package(package):
    package=EditingPackage.model_validate(package);edl=package.base_edl
    root=ET.fromstring(export_edl(edl));root.find('.//project').set('name',package.settings.project_name)
    clips=root.findall('.//spine/asset-clip')
    for i,(clip,crop,d) in enumerate(zip(clips,package.reframing,edl.decisions)):
        x,y=crop.transform_position
        transform=ET.Element('adjust-transform',position=f'{x:.8f} {y:.8f}',scale='1 1',anchor='0 0')
        conform=clip.find('adjust-conform');clip.insert(list(clip).index(conform)+1,transform)
        if d.audio_policy=='mute_slow_motion':
            # Native round-trip dropped srcEnable=video; keep an explicit gain-floor fallback.
            adjust=ET.Element('adjust-volume',amount='-96dB');clip.insert(list(clip).index(transform)+1,adjust)
        if package.mix.original_envelopes[i]:
            adjust=apply_envelope(clip,package.mix.original_envelopes[i],clip.get('start'))
            clip.remove(adjust)
            # intrinsic audio adjustments must precede anchored items.
            clip.insert(list(clip).index(transform)+1,adjust)
    audio=root.find('.//spine/asset-clip/audio')
    if audio is not None and package.mix.music_envelope:apply_envelope(audio,package.mix.music_envelope,audio.get('start','0'))
    ET.indent(root)
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)
