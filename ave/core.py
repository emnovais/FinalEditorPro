"""Pure planning/export core. Time values are exact rational seconds."""
from fractions import Fraction
from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def local_media(path):
    p = Path(path).expanduser().resolve(strict=True)
    if not p.is_file() or p.stat().st_size == 0:
        raise ValueError('Media must be a nonempty regular file')
    if any(x.lower().endswith(('.fcpbundle', '.fcplibrary')) for x in p.parts):
        raise ValueError('Media inside Final Cut libraries is forbidden')
    return p


def seconds(value):
    q = Fraction(value)
    if abs(q.numerator) >= 2**63 or q.denominator >= 2**32:
        raise ValueError('Time exceeds FCPXML integer limits')
    return f'{q.numerator}/{q.denominator}s'


def timecode(tc, fps):
    """Convert NDF or SMPTE DF source label to exact seconds."""
    m = re.fullmatch(r'(\d{2}):(\d{2}):(\d{2})([:;])(\d{2})', tc)
    if not m:
        raise ValueError('Unsupported source timecode')
    h, minute, s, sep, frame = m.groups()
    h, minute, s, frame = map(int, (h, minute, s, frame))
    nominal = round(fps)
    if h >= 24 or minute >= 60 or s >= 60 or frame >= nominal:
        raise ValueError('Invalid timecode label')
    frames = ((h * 60 + minute) * 60 + s) * nominal + frame
    if sep == ';':
        if fps not in (Fraction(30000, 1001), Fraction(60000, 1001)):
            raise ValueError('DF requires 29.97 or 59.94 fps')
        drop = 2 if nominal == 30 else 4
        if minute % 10 and s == 0 and frame < drop:
            raise ValueError('Nonexistent DF label')
        total_minutes = h * 60 + minute
        frames -= drop * (total_minutes - total_minutes // 10)
    return Fraction(frames, 1) / fps


def metadata(path, probe):
    """Normalize ffprobe output; reject unsupported ambiguity rather than guess."""
    p = local_media(path)
    streams = probe.get('streams', [])
    videos = [s for s in streams if s.get('codec_type') == 'video']
    audios = [s for s in streams if s.get('codec_type') == 'audio']
    if len(videos) != 1:
        raise ValueError('MVP supports exactly one video stream')
    if len(audios) > 32:
        raise ValueError('MVP supports at most 32 audio sources')
    v = videos[0]
    fps = Fraction(v['r_frame_rate'])
    if fps <= 0 or fps > 240 or Fraction(v['avg_frame_rate']) != fps:
        raise ValueError('Unknown or potentially variable frame rate')
    if v.get('field_order', 'progressive') not in ('progressive', 'unknown'):
        raise ValueError('Interlaced video unsupported')
    if Fraction(v.get('start_time', '0')) != 0:
        raise ValueError('Nonzero stream PTS requires clock reconciliation')
    if v.get('side_data_list') or v.get('tags', {}).get('rotate'):
        raise ValueError('Side data/rotation requires explicit interpretation')
    duration = Fraction(int(v['duration_ts'])) * Fraction(v['time_base'])
    frames = duration * fps
    if duration <= 0 or frames.denominator != 1:
        raise ValueError('Duration must cover a positive whole number of frames')
    if v.get('nb_frames') not in (None, 'N/A') and int(v['nb_frames']) != frames:
        raise ValueError('Frame count disagrees with video clock')
    width, height = int(v['width']), int(v['height'])
    if min(width, height) <= 0 or v.get('sample_aspect_ratio', '1:1') not in ('1:1', 'N/A'):
        raise ValueError('Only square-pixel video supported')
    labels = {s.get('tags', {}).get('timecode') for s in streams}
    labels.add(probe.get('format', {}).get('tags', {}).get('timecode'))
    labels.discard(None)
    if len(labels) > 1:
        raise ValueError('Conflicting source timecodes')
    start = timecode(next(iter(labels)), fps) if labels else Fraction(0)
    channels = {int(a['channels']) for a in audios}
    if not channels <= {1, 2} or len(channels) > 1:
        raise ValueError('Audio sources require uniform mono/stereo channel layouts')
    for a in audios:
        if int(a['sample_rate']) != 48000:
            raise ValueError('MVP audio requires 48 kHz mono/stereo')
        if Fraction(a.get('start_time', '0')) != 0:
            raise ValueError('Audio offset unsupported')
        if len(audios) > 1 and ('duration_ts' not in a or 'time_base' not in a):
            raise ValueError('Multiple audio sources require exact source durations')
        if 'duration_ts' in a and 'time_base' in a:
            if int(a['duration_ts']) * Fraction(a['time_base']) != duration:
                raise ValueError('Audio duration differs from video')
    return dict(path=str(p), sha256=sha256(p), size=p.stat().st_size,
                fps=str(fps), duration=str(duration), start=str(start),
                width=width, height=height, audio_channels=next(iter(channels), 0),
                audio_sources=len(audios),
                audio_streams=[{k: a.get(k) for k in ('index', 'codec_name', 'channels',
                                                      'sample_rate', 'duration_ts', 'time_base')}
                               for a in audios],
                ancillary_streams=[{k: s.get(k) for k in ('index', 'codec_type', 'codec_name')}
                                   for s in streams if s.get('codec_type') not in ('video', 'audio')],
                source_timecode=next(iter(labels)) if labels else None,
                codec=v.get('codec_name'), pixel_format=v.get('pix_fmt'),
                color={k: v.get(k) for k in ('color_space', 'color_transfer', 'color_primaries')})


def plan(media, name='AI Rough Cut'):
    if not media:
        raise ValueError('At least one video required')
    signature = lambda m: (m['fps'], m['width'], m['height'], m['color'])
    if any(signature(m) != signature(media[0]) for m in media):
        raise ValueError('Mixed formats/color unsupported; no implicit conform')
    return dict(version=1, name=name, media=media,
                clips=[dict(media=i, in_frames=0,
                            duration_frames=int(Fraction(m['duration']) * Fraction(m['fps'])))
                       for i, m in enumerate(media)],
                decisions=dict(strategy='input-order', model=None, effects=[]))


def validate(project, integrity=True):
    if project['version'] != 1 or not project['clips']:
        raise ValueError('Unsupported/empty project')
    media = project['media']
    plan(media)  # format compatibility
    for m in media:
        p = local_media(m['path'])
        if integrity and (p.stat().st_size != m['size'] or sha256(p) != m['sha256']):
            raise ValueError('Original media changed')
        if Fraction(m['fps']) <= 0 or Fraction(m['duration']) <= 0:
            raise ValueError('Invalid media clock')
    for c in project['clips']:
        if type(c['media']) is not int or not 0 <= c['media'] < len(media):
            raise ValueError('Invalid media reference')
        m = media[c['media']]
        for key in ('in_frames', 'duration_frames'):
            if type(c[key]) is not int:
                raise ValueError('Cuts require integer frames')
        if c['in_frames'] < 0 or c['duration_frames'] <= 0 or (
            c['in_frames'] + c['duration_frames'] > Fraction(m['duration']) * Fraction(m['fps'])
        ):
            raise ValueError('Cut outside source range')
    if project['decisions'].get('effects'):
        raise ValueError('Effects are not implemented')


def video_format_attributes(media):
    """Exact source geometry/clock; only use documented Apple preset names."""
    fps = Fraction(media['fps'])
    attrs = dict(frameDuration=seconds(1 / fps), width=str(media['width']),
                 height=str(media['height']))
    rate = {Fraction(24000, 1001): '2398', Fraction(24): '24', Fraction(25): '25',
            Fraction(30000, 1001): '2997', Fraction(30): '30', Fraction(50): '50',
            Fraction(60000, 1001): '5994', Fraction(60): '60'}.get(fps)
    size = {(3840, 2160): '3840x2160', (1920, 1080): '1080', (1280, 720): '720'}.get(
        (media['width'], media['height']))
    if rate and size:
        attrs['name'] = f'FFVideoFormat{size}p{rate}'
    return attrs


def export_xml(project):
    validate(project)
    first = project['media'][0]
    fps = Fraction(first['fps'])
    root = ET.Element('fcpxml', version='1.10')
    resources = ET.SubElement(root, 'resources')
    attrs = video_format_attributes(first)
    ET.SubElement(resources, 'format', id='r1', **attrs)
    # Project output color is independent of camera color. Match the supplied
    # FCP round-trip's Rec.709 sequence without assigning that profile to media.
    output_color = project.get('sequence_color_space', '1-1-1 (Rec. 709)')
    if output_color not in ('1-1-1 (Rec. 709)', '9-1-9 (Rec. 2020)',
                            '9-16-9 (Rec. 2020 PQ)', '9-18-9 (Rec. 2020 HLG)'):
        raise ValueError('Unsupported sequence output color space')
    ET.SubElement(resources, 'format', id='r_sequence', colorSpace=output_color, **attrs)
    for i, m in enumerate(project['media']):
        attrs = dict(id=f'a{i}', name=Path(m['path']).name, format='r1',
                     start=seconds(m['start']), duration=seconds(m['duration']), hasVideo='1',
                     hasAudio=str(int(m['audio_channels'] > 0)))
        if m['audio_channels']:
            # FCPXML audioChannels is the number of channels PER source/track.
            # Older JSON v1 has no audio_sources and represents a single source.
            attrs.update(audioSources=str(m.get('audio_sources', 1)),
                         audioChannels=str(m['audio_channels']), audioRate='48000')
        asset = ET.SubElement(resources, 'asset', attrs)
        ET.SubElement(asset, 'media-rep', kind='original-media', src=Path(m['path']).as_uri())
    event = ET.SubElement(root, 'event', name='AI Test Event')
    proj = ET.SubElement(event, 'project', name=project['name'])
    total = sum(c['duration_frames'] for c in project['clips']) / fps
    seq = ET.SubElement(proj, 'sequence', format='r_sequence', duration=seconds(total),
                        tcStart='0s', tcFormat='NDF', audioLayout='stereo', audioRate='48k')
    spine = ET.SubElement(seq, 'spine')
    offset = Fraction(0)
    for c in project['clips']:
        m = project['media'][c['media']]
        duration = Fraction(c['duration_frames'], 1) / fps
        ET.SubElement(spine, 'asset-clip', ref=f"a{c['media']}", name=Path(m['path']).name,
                      offset=seconds(offset), start=seconds(Fraction(m['start']) + c['in_frames'] / fps),
                      duration=seconds(duration), format='r1',
                      tcFormat='DF' if ';' in (m.get('source_timecode') or '') else 'NDF')
        offset += duration
    ET.indent(root)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
