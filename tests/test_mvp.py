import copy
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from ave.core import export_xml, metadata, plan, sha256, timecode, validate
from ave.cli import probe, publish, undo

DTD = Path(__file__).resolve().parents[1] / 'audit/FCPXMLv1_10.dtd'


class MVPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / 'vídeo & #1.mov'
        # Deliberately not real video: these unit tests exercise metadata contracts.
        self.source.write_bytes(b'controlled-test-media-bytes')
        self.facts = {'streams': [dict(codec_type='video', r_frame_rate='24000/1001',
                                      avg_frame_rate='24000/1001', time_base='1/24000',
                                      duration_ts=240240, nb_frames='240',
                                      width=3840, height=2160, tags={'timecode': '01:00:00:00'}),
                                  dict(codec_type='audio', sample_rate='48000', channels=2)]}
        self.media = metadata(self.source, self.facts)
        self.project = plan([self.media])

    def test_xml_dtd_and_references(self):
        out = publish(self.project, self.root / 'run')
        xml = out / 'timeline.fcpxml'
        subprocess.run(['/usr/bin/xmllint', '--nonet', '--noout', '--dtdvalid',
                        DTD.as_uri(), str(xml)], check=True, capture_output=True, timeout=10)
        tree = ET.parse(xml)
        self.assertEqual(tree.find('.//media-rep').get('src'), self.source.as_uri())
        ids = {x.get('id') for x in tree.findall('.//resources/*')}
        for node in tree.iter():
            for key in ('ref', 'format'):
                if key in node.attrib:
                    self.assertIn(node.get(key), ids)
        self.assertEqual(tree.find('.//sequence').get('duration'), '1001/100s')
        self.assertEqual(tree.find('.//asset-clip').get('start'), '18018/5s')
        self.assertEqual(tree.find('.//format').get('frameDuration'), '1001/24000s')

    def test_cut_offsets_exact_and_bounds(self):
        self.project['clips'] *= 3
        tree = ET.fromstring(export_xml(self.project))
        self.assertEqual([n.get('offset') for n in tree.findall('.//asset-clip')],
                         ['0/1s', '1001/100s', '1001/50s'])
        self.project['clips'][0]['in_frames'] = 1
        with self.assertRaises(ValueError): validate(self.project)

    def test_timecodes(self):
        self.assertEqual(timecode('01:00:00;00', Fraction(30000, 1001)), Fraction(107999892, 30000))
        self.assertEqual(timecode('00:01:00;02', Fraction(30000, 1001)), Fraction(3003, 50))
        for label in ['00:01:00;00', '25:00:00:00', '00:60:00:00', 'bad']:
            with self.assertRaises(ValueError): timecode(label, Fraction(30000, 1001))

    def test_original_and_no_overwrite(self):
        before = sha256(self.source)
        out = publish(self.project, self.root / 'run')
        with self.assertRaises(FileExistsError): publish(self.project, out)
        undo(out)
        self.assertEqual(sha256(self.source), before)
        self.assertTrue((out / 'undone/timeline.fcpxml').is_file())
        self.assertEqual(json.loads((out / 'operations.jsonl').read_text().splitlines()[-1])['action'], 'undo_complete')

    def test_modified_sources_and_artifacts(self):
        out = publish(self.project, self.root / 'run')
        (out / 'timeline.fcpxml').write_bytes(b'changed')
        with self.assertRaises(ValueError): undo(out)
        self.source.write_bytes(b'changed')
        with self.assertRaises(ValueError): export_xml(self.project)

    def test_missing_media_invalid_ref_and_fractional_cut(self):
        self.project['clips'][0]['media'] = -1
        with self.assertRaises(ValueError): export_xml(self.project)
        self.project['clips'][0]['media'] = 0
        self.project['clips'][0]['duration_frames'] = 1.5
        with self.assertRaises(ValueError): export_xml(self.project)
        self.source.unlink()
        with self.assertRaises(FileNotFoundError): export_xml(plan([self.media]))

    def test_unsupported_metadata(self):
        for updates in [dict(avg_frame_rate='24/1'), dict(start_time='1'),
                        dict(side_data_list=[{'rotation': 90}]), dict(duration_ts=1)]:
            facts = copy.deepcopy(self.facts)
            facts['streams'][0].update(updates)
            with self.assertRaises(ValueError): metadata(self.source, facts)
        self.project['decisions']['effects'] = ['speed-ramp']
        with self.assertRaises(ValueError): export_xml(self.project)

    def test_libraries_and_symlink_output(self):
        library = self.root / 'Test.fcpbundle'
        library.mkdir()
        with self.assertRaises(ValueError): publish(self.project, library / 'run')
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError): publish(self.project, alias / 'run')

    def test_probe_command_contract_only(self):
        # No ffprobe execution: verify argv/timeout/protocol restriction explicitly.
        with patch('ave.cli.subprocess.run') as run:
            run.return_value.stdout = json.dumps(self.facts).encode()
            self.assertEqual(probe(self.source, '/usr/bin/true'), self.facts)
            self.assertIn('file', run.call_args.args[0])
            self.assertNotIn('shell', run.call_args.kwargs)


if __name__ == '__main__':
    unittest.main()
