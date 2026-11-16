import ctypes as C
import json
from pathlib import Path
import subprocess
from unittest.mock import Mock, patch

import pytest

from final_editor_pro.ai.keychain import MacOSKeychain
from final_editor_pro.ai.adapters import OpenAICompatibleTransport, _NoRedirect
from final_editor_pro.ai.schemas import CreativePlan
from final_editor_pro.timeline import apply_plan, planning_input
from ave.core import metadata, plan, export_xml, sha256


def test_keychain_native_bridge_without_accessing_real_keychain():
    keychain = MacOSKeychain.__new__(MacOSKeychain)
    keychain._security, keychain._core = Mock(), Mock()
    value = C.create_string_buffer(b'test-only-secret')
    keychain._find = Mock(return_value=(0, C.c_uint32(16), C.cast(value, C.c_void_p), C.c_void_p(1)))
    assert keychain.get('test') == 'test-only-secret'
    keychain._security.SecKeychainItemFreeContent.assert_called_once()
    keychain._core.CFRelease.assert_called_once()
    keychain._find.return_value = (-25300, None, None, None)
    keychain._security.SecKeychainAddGenericPassword.return_value = 0
    keychain.set('test', 'new-test-secret')
    assert keychain._security.SecKeychainAddGenericPassword.call_args.args[2] == b'FinalEditorPro'


def test_remote_transport_no_redirect_and_normalized_response():
    keychain = Mock()
    keychain.get.return_value = 'test-only-secret'
    opener, response = Mock(), Mock()
    response.read.return_value = json.dumps({'choices': [{'message': {'content': '{"observations":[]}'}}],
                                           'usage': {'prompt_tokens': 1, 'completion_tokens': 2}}).encode()
    opener.open.return_value.__enter__ = Mock(return_value=response)
    opener.open.return_value.__exit__ = Mock(return_value=False)
    with patch('urllib.request.build_opener', return_value=opener):
        result = OpenAICompatibleTransport(keychain, 'account')('https://example.invalid/v1', b'{}')
    assert result['output'] == {'observations': []}
    assert result['usage']['input_tokens'] == 1
    request = opener.open.call_args.args[0]
    assert request.get_header('Authorization') == 'Bearer test-only-secret'
    with pytest.raises(PermissionError): _NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid')


def test_ai_plan_does_not_change_engine_or_sources(tmp_path):
    source = tmp_path / 'fixture.mov'
    source.write_bytes(b'not-real-video-contract-test')
    facts = {'streams': [dict(codec_type='video', r_frame_rate='25/1', avg_frame_rate='25/1',
                              time_base='1/25', duration_ts=100, width=1920, height=1080)]}
    project = plan([metadata(source, facts)])
    before = sha256(source)
    request = planning_input(project, 'Opening')
    assert str(source) not in request.model_dump_json()
    creative = CreativePlan(cuts=[dict(asset_id='asset-0', in_frames=25, duration_frames=50)], rationale='Opening')
    changed = apply_plan(project, creative)
    assert changed['clips'][0]['in_frames'] == 25
    assert project['clips'][0]['in_frames'] == 0
    assert b'duration="2/1s"' in export_xml(changed)
    assert sha256(source) == before


def test_gitignore_preserves_development_dotfiles():
    root = Path(__file__).resolve().parents[1]
    ignored = ['.DS_Store', 'nested/.DS_Store', '._video', '.AppleDouble/a', 'temp/a', '.venv/a',
               '.env', 'models/a.gguf', 'media/a.mov', 'proxies/a', 'renders/a', 'exports/a']
    kept = ['.gitignore', '.editorconfig', '.github/workflows/tests.yml', '.env.example']
    result = subprocess.run(['git', 'check-ignore', '--stdin'], cwd=root,
                            input='\n'.join(ignored + kept) + '\n', text=True,
                            capture_output=True, check=False, timeout=10)
    assert result.returncode == 0
    assert set(result.stdout.splitlines()) == set(ignored)
