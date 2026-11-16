"""Regression: DTD-valid custom format was not fully resolved as a project format.

Expected attributes transcribed from the user-supplied FCP 1.14 round-trip.
No bookmarks, library paths, UIDs or private media are part of this fixture.
"""
from fractions import Fraction
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import pytest

from ave.core import export_xml, metadata, plan, video_format_attributes


def test_sequence_matches_native_format_without_overriding_camera_color(tmp_path):
    source = tmp_path / 'sample.mxf'
    source.write_bytes(b'test-contract-only')
    facts = {'streams': [dict(codec_type='video', r_frame_rate='50', avg_frame_rate='50',
                              time_base='1/50', duration_ts=192, width=3840, height=2160)]}
    project = plan([metadata(source, facts)])
    data = export_xml(project)
    root = ET.fromstring(data)
    formats = {f.get('id'): f for f in root.findall('resources/format')}
    sequence = root.find('.//sequence')
    output = formats[sequence.get('format')]
    assert output.get('name') == 'FFVideoFormat3840x2160p50'
    assert Fraction(output.get('frameDuration')[:-1]) == Fraction(100, 5000)
    assert (output.get('width'), output.get('height')) == ('3840', '2160')
    assert output.get('colorSpace') == '1-1-1 (Rec. 709)'
    asset = root.find('.//asset')
    clip = root.find('.//asset-clip')
    assert asset.get('format') == clip.get('format') != sequence.get('format')
    assert 'colorSpace' not in formats[asset.get('format')].attrib
    assert 'colorSpaceOverride' not in asset.attrib
    assert not root.findall('.//adjust-colorConform')
    assert sequence.get('duration') == '96/25s'
    path = tmp_path / 'sequence.fcpxml'
    path.write_bytes(data)
    dtd = Path(__file__).resolve().parents[1] / 'audit/FCPXMLv1_10.dtd'
    subprocess.run(['/usr/bin/xmllint', '--nonet', '--noout', '--dtdvalid', dtd.as_uri(), str(path)],
                   check=True, capture_output=True, timeout=10)


@pytest.mark.parametrize('fps,suffix', [('24000/1001', '2398'), ('30000/1001', '2997'), ('50', '50')])
def test_preset_name_does_not_round_source_clock(fps, suffix):
    attrs = video_format_attributes(dict(fps=fps, width=3840, height=2160))
    assert attrs['name'] == 'FFVideoFormat3840x2160p' + suffix
    assert Fraction(attrs['frameDuration'][:-1]) == 1 / Fraction(fps)


def test_custom_dimensions_do_not_get_invented_preset():
    attrs = video_format_attributes(dict(fps='25', width=1234, height=678))
    assert 'name' not in attrs
    assert attrs['width'] == '1234'
