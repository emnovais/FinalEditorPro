"""Validate executable additions beyond the stable EDL/XML mapping."""
from fractions import Fraction
import xml.etree.ElementTree as ET
from ..director.validation import validate_xml


def validate_package_xml(package,xml):
    validate_xml(package.base_edl,xml)
    root=ET.fromstring(xml);clips=root.findall('.//spine/asset-clip')
    def curve(node,envelope):
        adjust=node.find('adjust-volume')
        if envelope is None:return
        if adjust is None:raise ValueError('Missing gain envelope')
        keys=adjust.findall("param[@name='amount']/keyframeAnimation/keyframe")
        origin=Fraction(node.get('start','0s').removesuffix('s'))
        if len(keys)!=len(envelope.points):raise ValueError('Incomplete gain automation')
        for key,(t,gain) in zip(keys,envelope.points):
            if 'interp' in key.attrib or 'curve' in key.attrib:raise ValueError('Volume keyframes do not support explicit interpolation attributes in Final Cut')
            if Fraction(key.get('time').removesuffix('s'))-origin!=Fraction(t) or abs(float(key.get('value').removesuffix('dB'))-gain)>1e-5:raise ValueError('XML gain differs from mix plan')
    for clip,r,envelope in zip(clips,package.reframing,package.mix.original_envelopes):
        transform=clip.find('adjust-transform')
        if transform is None or any(abs(float(a)-b)>1e-6 for a,b in zip(transform.get('position').split(),r.transform_position)):raise ValueError('XML crop transform differs')
        if package.base_edl.decisions[clips.index(clip)].audio_policy=='mute_slow_motion':
            adjust=clip.find('adjust-volume')
            if adjust is None or float(adjust.get('amount','0dB').removesuffix('dB'))> -96:raise ValueError('Missing slow-motion gain-floor fallback')
        curve(clip,envelope)
    if package.mix.music_envelope:
        audio=root.find('.//spine/asset-clip/audio')
        if audio is None:raise ValueError('Music missing')
        asset=root.find("./resources/asset[@id='"+audio.get('ref')+"']")
        expected=Fraction(package.base_edl.music.get('source_start_seconds','0'))
        if asset is None or Fraction(asset.get('start','0s').removesuffix('s'))!=expected or Fraction(audio.get('start','0s').removesuffix('s'))!=expected:raise ValueError('Music BWF source clocks differ')
        curve(audio,package.mix.music_envelope)
    return True
