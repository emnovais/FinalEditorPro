"""Controlled XML startup experiments; hypotheses, never claimed playback fixes."""
from copy import deepcopy
from fractions import Fraction
import xml.etree.ElementTree as ET
from ave.core import seconds


def variants(xml,music_origin):
    origin=Fraction(music_origin)
    if origin<0:raise ValueError('Negative BWF source origin')
    base=ET.fromstring(xml)
    if base.find('.//sequence/spine/asset-clip') is None:raise ValueError('No primary video')
    original_music=base.find('.//sequence/spine/asset-clip/audio')
    if original_music is None:raise ValueError('No connected music for this experiment')
    def project(root,label):root.find('.//project').set('name','Final Editor Pro — Startup Test '+label)
    clock=deepcopy(base);project(clock,'A • Music Source Clock')
    music=clock.find('.//sequence/spine/asset-clip/audio')
    resource=clock.find("./resources/asset[@id='"+music.get('ref')+"']")
    if resource is None:raise ValueError('Music resource absent')
    old_origin=Fraction(resource.get('start','0s').removesuffix('s'));delta=origin-old_origin
    resource.set('start',seconds(origin))
    music.set('start',seconds(Fraction(music.get('start','0s').removesuffix('s'))+delta))
    for key in music.findall('./adjust-volume/param/keyframeAnimation/keyframe'):
        key.set('time',seconds(Fraction(key.get('time').removesuffix('s'))+delta))
    disabled=deepcopy(base);project(disabled,'B • No Music')
    first=disabled.find('.//sequence/spine/asset-clip');audio=first.find('audio');reference=audio.get('ref');first.remove(audio)
    resource=disabled.find("./resources/asset[@id='"+reference+"']")
    if resource is not None and not any(e.get('ref')==reference for e in disabled.iter()):disabled.find('resources').remove(resource)
    no_curves=deepcopy(base);project(no_curves,'C • Static Volume')
    for adjust in no_curves.findall('.//adjust-volume'):
        for param in list(adjust):
            if param.tag=='param':adjust.remove(param)
    result={}
    for name,root in [('A-music-source-clock',clock),('B-music-disabled',disabled),('C-static-volume',no_curves)]:
        ET.indent(root);result[name]=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    return result
