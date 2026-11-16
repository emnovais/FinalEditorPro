"""Regression for the real MXF stream layout; no private media fixtures needed."""
import xml.etree.ElementTree as ET

import pytest

from ave.core import metadata, plan, export_xml


@pytest.fixture
def source_and_facts(tmp_path):
    p = tmp_path / 'multistream.mxf'
    p.write_bytes(b'unit-test-only-not-a-video')
    video = dict(index=0, codec_type='video', r_frame_rate='50/1', avg_frame_rate='50/1',
                 time_base='1/50', duration_ts=192, width=3840, height=2160)
    audios = [dict(index=i, codec_type='audio', codec_name='pcm_s24le', sample_rate='48000',
                   channels=1, start_time='0', duration_ts=184320, time_base='1/48000')
              for i in range(1, 5)]
    data = dict(index=5, codec_type='data', codec_name='smpte_436m_anc')
    return p, {'streams': [video, *audios, data], 'format': {'tags': {'timecode': '16:48:03:00'}}}


def test_preserves_four_mono_sources(source_and_facts):
    p, facts = source_and_facts
    m = metadata(p, facts)
    assert m['audio_sources'] == 4 and m['audio_channels'] == 1
    assert [a['index'] for a in m['audio_streams']] == [1, 2, 3, 4]
    assert m['ancillary_streams'][0]['codec_name'] == 'smpte_436m_anc'
    root = ET.fromstring(export_xml(plan([m])))
    asset = root.find('.//asset')
    assert asset.get('audioSources') == '4'
    assert asset.get('audioChannels') == '1'
    assert asset.get('audioRate') == '48000'
    assert root.find('.//asset-clip').get('start') == '60483/1s'


@pytest.mark.parametrize('change', [
    {'channels': 2}, {'sample_rate': '44100'}, {'start_time': '0.02'},
    {'duration_ts': 184319}, {'time_base': '1/44100'},
])
def test_refuses_ambiguous_audio_sources(source_and_facts, change):
    p, facts = source_and_facts
    facts['streams'][2].update(change)
    with pytest.raises(ValueError): metadata(p, facts)


def test_requires_duration_for_multiple_sources(source_and_facts):
    p, facts = source_and_facts
    del facts['streams'][1]['duration_ts']
    with pytest.raises(ValueError): metadata(p, facts)


def test_legacy_json_single_source_stays_supported(source_and_facts):
    p, facts = source_and_facts
    facts['streams'] = facts['streams'][:2]
    m = metadata(p, facts)
    del m['audio_sources']
    asset = ET.fromstring(export_xml(plan([m]))).find('.//asset')
    assert asset.get('audioSources') == '1'
