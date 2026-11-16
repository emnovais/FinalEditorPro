import base64
from decimal import Decimal
import json
import socket
import subprocess
import urllib.request
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from final_editor_pro.ai.config import Mode, ProcessingConfig, ProjectOverride, resolve_config, load_config
from final_editor_pro.ai.schemas import (Task, PlanningInput, CreativePlan, AssetSummary,
                                         VisualInput, Frame, VisualOutput, CONTRACTS,
                                         SegmentationInput, SegmentationOutput, EffectsInput, EffectsOutput)
from final_editor_pro.ai.providers import AIProvider, LocalProvider, CloudProvider
from final_editor_pro.ai.privacy import PrivacyPolicy
from final_editor_pro.ai.router import ProcessingRouter, OperationJournal
from final_editor_pro.ai.adapters import LlamaCppPlanner, OpenAICompatibleTransport, openai_payload, build_providers
from ave.core import sha256


@pytest.fixture
def request_data():
    return PlanningInput(brief='Use the first ten frames', assets=[AssetSummary(asset_id='a', total_frames=100)])


@pytest.fixture
def output():
    return CreativePlan(cuts=[{'asset_id': 'a', 'in_frames': 0, 'duration_frames': 10}], rationale='Opening')


@pytest.fixture
def journal(tmp_path):
    return OperationJournal(tmp_path / 'operations.jsonl')


def local(output, provider_id='local'):
    return LocalProvider(provider_id, 'test-only', {Task.PLANNING: lambda request: output})


def cloud(policy, output, provider_id='remote'):
    transport = Mock(return_value={'output': output.model_dump(), 'usage': {'input_tokens': 10, 'output_tokens': 20}})
    p = CloudProvider(provider_id, 'test-only', 'https://example.invalid/v1', [Task.PLANNING], policy,
                      transport, 1, 2)
    return p, transport


def test_configuration_merge_and_secret_rejection(tmp_path):
    base = ProcessingConfig(routes={Task.PLANNING: 'local', Task.VISUAL: 'vision'})
    override = ProjectOverride(mode=Mode.HYBRID, routes={Task.PLANNING: 'remote'})
    merged = resolve_config(base, override)
    assert merged.routes == {Task.PLANNING: 'remote', Task.VISUAL: 'vision'}
    assert base.mode == Mode.LOCAL and base.routes[Task.PLANNING] == 'local'
    assert not merged.allow_uploads
    for cls in (ProcessingConfig, ProjectOverride):
        with pytest.raises(ValidationError): cls.model_validate({'api_key': 'forbidden'})
    p = tmp_path / 'global.json'
    p.write_text(base.model_dump_json())
    assert load_config(p) == base


@pytest.mark.parametrize('task', [Task.PROBE, Task.EXPORT, Task.TRANSCODE])
def test_mandatory_local_operations(task, journal, request_data, output):
    with pytest.raises(ValidationError): ProcessingConfig(routes={task: 'remote'})
    router = ProcessingRouter(ProcessingConfig(mode=Mode.CLOUD), [local(output)], journal)
    with pytest.raises(ValueError, match='Mandatory local'): router.run(task, request_data)


def test_local_absence_of_network(monkeypatch, journal, request_data, output):
    def forbidden(*args, **kwargs):
        pytest.fail('Network attempted in LOCAL')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(urllib.request, 'urlopen', forbidden)
    remote, send = cloud(PrivacyPolicy(), output)
    router = ProcessingRouter(ProcessingConfig(), [remote, local(output)], journal)
    assert router.run(Task.PLANNING, request_data).output == output
    send.assert_not_called()
    router = ProcessingRouter(ProcessingConfig(routes={Task.PLANNING: 'remote'}), [remote], journal)
    with pytest.raises(PermissionError): router.run(Task.PLANNING, request_data)
    send.assert_not_called()


def test_local_failure_does_not_fallback(journal, request_data, output):
    def broken(request): raise RuntimeError('Model unavailable')
    failing = LocalProvider('local', 'missing', {Task.PLANNING: broken})
    remote, send = cloud(PrivacyPolicy(), output)
    router = ProcessingRouter(ProcessingConfig(), [failing, remote], journal)
    with pytest.raises(RuntimeError): router.run(Task.PLANNING, request_data)
    send.assert_not_called()


@pytest.mark.parametrize('mode,expected', [(Mode.LOCAL, 'local'), (Mode.HYBRID, 'local'), (Mode.CLOUD, 'remote')])
def test_mode_preferences(mode, expected, journal, output):
    remote, _ = cloud(PrivacyPolicy(), output)
    router = ProcessingRouter(ProcessingConfig(mode=mode), [remote, local(output)], journal)
    assert router.select(Task.PLANNING).id == expected


def test_distinct_routes_capabilities_and_unknown_provider(journal, output):
    vision = LocalProvider('vision', 'test', {Task.VISUAL: lambda request: VisualOutput(observations=[])})
    config = ProcessingConfig(routes={Task.PLANNING: 'planner', Task.VISUAL: 'vision'})
    router = ProcessingRouter(config, [local(output, 'planner'), vision], journal)
    assert router.select(Task.VISUAL).id == 'vision'
    assert router.select(Task.PLANNING).id == 'planner'
    with pytest.raises(ValueError): router.select(Task.SEGMENTATION)
    with pytest.raises(ValueError): ProcessingRouter(config, [vision], journal).select(Task.PLANNING)
    assert isinstance(vision, AIProvider)


def test_remote_consent_exact_single_use_and_cost(journal, request_data, output):
    policy = PrivacyPolicy()
    remote, send = cloud(policy, output)
    router = ProcessingRouter(ProcessingConfig(mode=Mode.HYBRID, allow_uploads=True), [remote], journal)
    with pytest.raises(PermissionError): router.run(Task.PLANNING, request_data)
    send.assert_not_called()
    upload = router.preview_upload(Task.PLANNING, request_data)
    with pytest.raises(PermissionError): policy.approve(upload)
    token = policy.approve(upload, confirmed=True)
    result = router.run(Task.PLANNING, request_data, token)
    assert result.estimated_cost_usd == Decimal('0.00005')
    assert send.call_count == 1
    with pytest.raises(PermissionError): router.run(Task.PLANNING, request_data, token)
    assert send.call_count == 1
    log = journal.path.read_text()
    assert '0.00005' in log and 'remote' in log
    assert request_data.brief not in log and token not in log and 'Opening' not in log


def test_consent_changed_payload_model_destination_and_expiration(request_data, output):
    now = [1]
    policy = PrivacyPolicy(clock=lambda: now[0])
    remote, send = cloud(policy, output)
    upload = remote.upload_preview(Task.PLANNING, request_data)
    for mutate in ['payload', 'model', 'endpoint', 'expired']:
        token = policy.approve(upload, confirmed=True)
        request = request_data
        if mutate == 'payload': request = request_data.model_copy(update={'brief': 'changed'})
        if mutate == 'model': remote.model = 'different'
        if mutate == 'endpoint': remote.endpoint = 'https://other.invalid'
        if mutate == 'expired': now[0] = 999
        with pytest.raises(PermissionError): remote.run(Task.PLANNING, request, token)
        remote.model, remote.endpoint = 'test-only', 'https://example.invalid/v1'
        now[0] = 1
    send.assert_not_called()


def test_remote_upload_setting_and_bad_response(journal, request_data, output):
    policy = PrivacyPolicy()
    remote, send = cloud(policy, output)
    router = ProcessingRouter(ProcessingConfig(mode=Mode.CLOUD), [remote], journal)
    with pytest.raises(PermissionError): router.preview_upload(Task.PLANNING, request_data)
    with pytest.raises(PermissionError): router.run(Task.PLANNING, request_data)
    send.assert_not_called()
    send.return_value = {'output': {'cuts': [{'asset_id': 'a', 'in_frames': 0, 'duration_frames': 101}], 'rationale': ''}}
    token = policy.approve(remote.upload_preview(Task.PLANNING, request_data), confirmed=True)
    with pytest.raises(ValueError, match='outside'): remote.run(Task.PLANNING, request_data, token)


def test_model_contracts(request_data, output):
    for input_schema, output_schema in CONTRACTS.values():
        assert input_schema.model_json_schema() and output_schema.model_json_schema()
    with pytest.raises(ValidationError): CreativePlan(cuts=[{'asset_id': 'a', 'in_frames': 0.5, 'duration_frames': 1}], rationale='')
    assert CreativePlan.model_validate_json(output.model_dump_json()) == output


def test_visual_wire_format_and_observation_validation(journal):
    frame = Frame(asset_id='a', frame_index=4, mime='image/png', data_base64='dGVzdA==')
    request = VisualInput(instruction='Describe this frame', frames=[frame])
    body = json.loads(openai_payload(Task.VISUAL, request, 'chosen-vision-model'))
    content = body['messages'][1]['content']
    assert content[1]['image_url']['url'] == 'data:image/png;base64,dGVzdA=='
    assert 'data_base64' not in content[0]['text']
    invalid = {'observations': [{'asset_id': 'a', 'frame_index': 5, 'description': 'unseen', 'confidence': 1}]}
    provider = LocalProvider('vision', 'fake-for-tests', {Task.VISUAL: lambda request: invalid})
    router = ProcessingRouter(ProcessingConfig(), [provider], journal)
    with pytest.raises(ValueError, match='unsubmitted'): router.run(Task.VISUAL, request)


def test_reserved_segmentation_and_effect_routes_with_test_providers_only(journal):
    frame = Frame(asset_id='a', frame_index=0, mime='image/png', data_base64='dGVzdA==')
    segmentation = LocalProvider('segment-test-only', 'fake', {
        Task.SEGMENTATION: lambda request: SegmentationOutput(mask_png_base64='dGVzdA==')})
    effects = LocalProvider('effects-test-only', 'fake', {
        Task.EFFECTS: lambda request: EffectsOutput(recipe='Test-only unexecuted recipe')})
    router = ProcessingRouter(ProcessingConfig(routes={Task.SEGMENTATION: segmentation.id, Task.EFFECTS: effects.id}),
                              [segmentation, effects], journal)
    assert router.run(Task.SEGMENTATION, SegmentationInput(frame=frame, object_description='object')).output
    result = router.run(Task.EFFECTS, EffectsInput(instruction='test', duration_frames=10))
    assert result.output.executable is False


def test_optional_disabled_adapters_no_keychain(monkeypatch):
    from final_editor_pro.ai.config import ProviderSettings
    spec = ProviderSettings(kind='cloud', model='chosen', enabled=True, capabilities=[Task.PLANNING],
                            endpoint='https://example.invalid', keychain_account='test')
    assert build_providers(ProcessingConfig(providers={'remote': spec}), PrivacyPolicy()) == []


def test_openai_payload_is_exact_approved_payload_and_no_credentials(request_data, output):
    policy = PrivacyPolicy()
    send = Mock(return_value={'output': output.model_dump()})
    remote = CloudProvider('openai', 'configured', 'https://example.invalid', [Task.PLANNING], policy,
                           send, payload_builder=openai_payload)
    body = remote.payload(Task.PLANNING, request_data)
    assert json.loads(body)['model'] == 'configured'
    assert 'cuts' in json.loads(body)['messages'][0]['content']
    token = policy.approve(remote.upload_preview(Task.PLANNING, request_data), confirmed=True)
    remote.run(Task.PLANNING, request_data, token)
    assert send.call_args.args[1] == body


def test_https_and_keychain_only():
    keychain = Mock()
    transport = OpenAICompatibleTransport(keychain, 'account-name')
    for endpoint in ['http://example.invalid', 'https://user:pass@example.invalid', 'https://example.invalid?key=secret']:
        with pytest.raises(ValueError): transport(endpoint, b'{}')
    keychain.get.assert_not_called()


def test_local_real_adapter_command_is_sandboxed_without_running_model(tmp_path, request_data):
    executable = tmp_path / 'llama-cli'
    model = tmp_path / 'test.gguf'
    executable.write_text('placeholder binary, never executed')
    model.write_text('placeholder model, never loaded')
    runner = LlamaCppPlanner(executable, model, sha256(executable), sha256(model))
    with patch('final_editor_pro.ai.adapters.subprocess.run') as run:
        run.return_value.returncode = 0
        run.return_value.stdout = '{"cuts": [{"asset_id":"a","in_frames":0,"duration_frames":1}],"rationale":"test"}'
        assert runner(request_data)['cuts'][0]['duration_frames'] == 1
        args = run.call_args.args[0]
        assert args[0] == '/usr/bin/sandbox-exec' and '(deny network*)' in args[2]
        assert '--offline' in args and '--single-turn' in args
        assert request_data.brief not in ' '.join(args)
        assert 'HOME' not in run.call_args.kwargs['env']
    model.write_text('changed')
    with pytest.raises(PermissionError): runner(request_data)
