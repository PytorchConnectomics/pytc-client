import json
from unittest.mock import patch

import numpy as np
import pytest
import tifffile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server_api.auth import database
from server_api.main import app
from server_api.workflows.agent_team import AgentTeamRun, recover_interrupted_runs


@pytest.fixture
def team(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTC_TEAM_MODEL", "")
    engine = create_engine(f"sqlite:///{tmp_path / 'team.db'}", connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    def db_override():
        with sessions() as db:
            yield db
    app.dependency_overrides[database.get_db] = db_override
    client = TestClient(app)
    workflow = client.get('/api/workflows/current').json()['workflow']
    image = tmp_path / 'image.tif'
    labels = tmp_path / 'labels.tif'
    tifffile.imwrite(image, np.ones((5, 8, 8), dtype=np.uint8), photometric='minisblack')
    volume = np.zeros((5, 8, 8), dtype=np.uint16)
    volume[:, :2] = 7
    volume[:, 4:6] = 13
    tifffile.imwrite(labels, volume, photometric='minisblack')
    client.patch(f"/api/workflows/{workflow['id']}", json={'image_path': str(image), 'label_path': str(labels), 'metadata': {'project_context': {'target_structure': 'nuclei'}}})
    yield client, workflow['id'], labels, sessions, engine
    app.dependency_overrides.clear()
    engine.dispose()


def check(client, workflow_id, **body):
    result = client.post(f'/api/workflows/{workflow_id}/team-runs', json=body)
    assert result.status_code == 202, result.text
    return client.get(f'/api/workflows/{workflow_id}/team-runs').json()[0]


def test_real_delegation_persists_scoped_context_and_leaves_labels_unchanged(team):
    client, wid, labels, sessions, _ = team
    before = labels.read_bytes()
    run = check(client, wid, request_key='one')
    assert run['executor'] == 'tool_backed_scaffold'
    assert run['status'] == 'completed'
    assert [task['role'] for task in run['tasks']] == ['data', 'annotation', 'model']
    data, annotation, model = run['tasks']
    assert data['result']['facts']['label_path']['nonzero_label_ids'] == 2
    assert data['result']['facts']['image_path']['shape'] == [5, 8, 8]
    assert set(data['context']['artifacts']) == {'image_path', 'label_path'}
    assert 'image_path' not in annotation['context']['artifacts']
    assert data['context']['objective'] == {'target_structure': 'nuclei'}
    assert labels.read_bytes() == before
    assert not run['stale']
    assert len([action for action in run['actions'] if action['query'] == 'Start proofreading']) == 1
    assert run['actions'][0]['source_task_id'] == annotation['id']
    events = client.get(f'/api/workflows/{wid}/events').json()
    assert {'agent_team.delegated', 'agent_team.completed'} <= {e['event_type'] for e in events}
    with sessions() as db:
        assert db.get(AgentTeamRun, run['id']).status == 'completed'
    assert check(client, wid, request_key='one')['id'] == run['id']
    assert len(client.get(f'/api/workflows/{wid}/team-runs').json()) == 1


def test_missing_data_is_blocked_and_failure_does_not_fabricate_success(team):
    client, wid, labels, _, _ = team
    labels.unlink()
    run = check(client, wid, scope='data')
    assert run['status'] == 'needs_attention'
    assert run['tasks'][0]['status'] == 'blocked'
    assert 'label_path' not in run['tasks'][0]['result']['facts']
    assert all(action['label'] != 'Open proofreading' for action in run['tasks'][0]['result']['actions'])
    with patch('server_api.workflows.agent_team.run_specialist', side_effect=RuntimeError('worker unavailable')):
        failed = check(client, wid, scope='model')
    assert failed['status'] == 'needs_attention'
    assert failed['tasks'][0]['status'] == 'failed'
    assert 'worker unavailable' in failed['tasks'][0]['error']


def test_changed_input_marks_persisted_result_stale(team):
    client, wid, labels, _, _ = team
    check(client, wid)
    tifffile.imwrite(labels, np.ones((5, 8, 8), dtype=np.uint16), photometric='minisblack')
    assert client.get(f'/api/workflows/{wid}/team-runs').json()[0]['stale']


def test_restart_marks_unfinished_tasks_interrupted(team):
    client, wid, _, sessions, engine = team
    run = check(client, wid)
    with sessions() as db:
        row = db.get(AgentTeamRun, run['id'])
        row.status = 'running'
        payload = json.loads(row.payload_json)
        payload['tasks'][0]['status'] = 'running'
        row.payload_json = json.dumps(payload)
        db.commit()
    recover_interrupted_runs(engine)
    restarted = client.get(f'/api/workflows/{wid}/team-runs').json()[0]
    assert restarted['status'] == 'interrupted'
    assert restarted['tasks'][0]['status'] == 'interrupted'
    assert restarted['tasks'][1]['status'] == 'completed'


def test_unknown_project_and_unregistered_role_are_rejected(team):
    client, wid, _, _, _ = team
    assert client.get('/api/workflows/99999/team-runs').status_code == 404
    assert client.post('/api/workflows/99999/team-runs', json={}).status_code == 404
    assert client.post(f'/api/workflows/{wid}/team-runs', json={'scope': 'shell'}).status_code == 422


def test_other_user_cannot_read_or_start_team_tasks(team):
    from types import SimpleNamespace
    from server_api.auth.router import get_current_user
    client, wid, _, _, _ = team
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=99999)
    assert client.get(f'/api/workflows/{wid}/team-runs').status_code == 404
    assert client.post(f'/api/workflows/{wid}/team-runs', json={}).status_code == 404


def test_chat_delegates_and_preserves_the_user_goal(team):
    client, wid, _, _, _ = team
    query = 'Ask the data specialist to inspect the current project and report image dimensions and label IDs.'
    reply = client.post(f'/api/workflows/{wid}/agent/query', json={'query': query})
    assert reply.status_code == 200, reply.text
    result = reply.json()
    assert result['intent'] == 'delegation'
    run = client.get(f'/api/workflows/{wid}/team-runs').json()[0]
    assert run['id'] == result['team_run_id']
    assert run['goal'] == query
    assert [t['role'] for t in run['tasks']] == ['data']
    assert run['tasks'][0]['result']['facts']['label_path']['nonzero_label_ids'] == 2


def test_team_actions_are_typed_scoped_and_reject_stale_results(team):
    client, wid, labels, _, _ = team
    run = check(client, wid)
    view_index = next(i for i, a in enumerate(run['actions']) if a['kind'] == 'visualize')
    endpoint = f"/api/workflows/{wid}/team-runs/{run['id']}/actions/{view_index}"
    action = client.post(endpoint).json()
    assert action['client_effects']['runtime_action']['kind'] == 'load_visualization'
    assert action['client_effects']['set_visualization_label_path'] == str(labels)
    assert not action['requires_approval']
    proof = client.post(f"/api/workflows/{wid}/team-runs/{run['id']}/actions/0").json()
    assert proof['requires_approval']
    assert proof['client_effects']['navigate_to'] == 'mask-proofreading'
    assert client.post(f"/api/workflows/{wid}/team-runs/{run['id']}/actions/999").status_code == 404
    labels.unlink()
    assert client.post(endpoint).status_code == 409


def test_delegation_does_not_capture_negations_or_plain_job_requests():
    from server_api.workflows.agent_team import delegation_scope
    assert delegation_scope('Ask the model specialist to check readiness') == 'model'
    assert delegation_scope('Review the whole project') == 'project'
    assert delegation_scope('Do not ask the data specialist to inspect anything') is None
    assert delegation_scope('Start training') is None


def test_manager_answers_followup_from_saved_specialist_evidence(team):
    client, wid, _, _, _ = team
    run = check(client, wid, scope='data')
    answer = client.post(f'/api/workflows/{wid}/agent/query', json={'query': 'What did the data specialist find?'}).json()
    assert answer['intent'] == 'specialist_results'
    assert answer['team_run_id'] == run['id']
    assert '2 nonzero IDs' in answer['response']
    assert len(client.get(f'/api/workflows/{wid}/team-runs').json()) == 1


def test_view_action_uses_the_label_pair_the_data_specialist_inspected(team):
    client, wid, labels, _, _ = team
    corrected = labels.with_name('corrected.tif')
    tifffile.imwrite(corrected, np.ones((5, 8, 8), dtype=np.uint16), photometric='minisblack')
    client.patch(f'/api/workflows/{wid}', json={'corrected_mask_path': str(corrected)})
    run = check(client, wid, scope='data')
    index = next(i for i, a in enumerate(run['actions']) if a['kind'] == 'visualize')
    action = client.post(f"/api/workflows/{wid}/team-runs/{run['id']}/actions/{index}").json()
    assert action['client_effects']['set_visualization_label_path'] == str(labels)


def model_reply(request):
    """Provider double; tools and database still execute normally."""
    from unittest.mock import Mock
    context = json.loads(request['messages'][1]['content'])['context']
    properties = request['format']['properties']
    if 'tasks' in properties:
        value = {'message': 'Inspect the data before choosing a next step.', 'tasks': [{'role': 'data', 'goal': 'Verify image and label geometry.'}]}
    elif 'tool' in properties:
        evidence = context['evidence']
        value = {'tool': 'finish' if evidence else 'inspect_tiff', 'summary': 'Two IDs are present; geometry matches.' if evidence else '',
                 'evidence_ids': [evidence[0]['id']] if evidence else [], 'action_kinds': ['visualize'] if evidence else []}
    else:
        value = {'summary': 'The inspected pair matches. View it next.', 'task_ids': [context['tasks'][0]['id']],
                 'action_ids': [action['id'] for action in context['available_actions']]}
    response = Mock()
    response.json.return_value = {'done': True, 'done_reason': 'stop', 'message': {'content': json.dumps(value)}, 'prompt_eval_count': 80, 'eval_count': 30}
    return response


def test_model_manager_delegates_tools_and_synthesizes_with_provenance(team, monkeypatch):
    client, wid, labels, _, _ = team
    monkeypatch.setenv('PYTC_TEAM_MODEL', 'test-model')
    before = labels.read_bytes()
    with patch('server_api.workflows.team_llm.requests.post', side_effect=lambda *a, **kw: model_reply(kw['json'])) as provider:
        run = check(client, wid)
    assert run['status'] == 'completed'
    assert run['executor'] == 'local_llm'
    assert len(run['model_calls']) == provider.call_count == 4
    assert all(call['model'] == 'test-model' for call in run['model_calls'])
    task = run['tasks'][0]
    assert task['tool_calls'][0]['result']['facts']['label_path']['nonzero_label_ids'] == 2
    assert task['result']['evidence_ids'] == [task['tool_calls'][0]['id']]
    assert run['actions'][0]['kind'] == 'visualize'
    assert labels.read_bytes() == before


def test_model_outage_is_a_failure_not_scripted_success(team, monkeypatch):
    import requests
    client, wid, _, _, _ = team
    monkeypatch.setenv('PYTC_TEAM_MODEL', 'test-model')
    with patch('server_api.workflows.team_llm.requests.post', side_effect=requests.Timeout('offline')):
        run = check(client, wid)
    assert run['status'] == 'failed'
    assert run['actions'] == []
    assert run['model_calls'][0]['status'] == 'failed'
    assert 'offline' in run['error']


def test_model_cannot_propose_arbitrary_actions(team, monkeypatch):
    client, wid, _, _, _ = team
    monkeypatch.setenv('PYTC_TEAM_MODEL', 'test-model')
    def invalid_action(*a, **kw):
        response = model_reply(kw['json'])
        data = response.json.return_value
        value = json.loads(data['message']['content'])
        if value.get('tool') == 'finish':
            value['action_kinds'] = ['run_shell']
            data['message']['content'] = json.dumps(value)
        return response
    with patch('server_api.workflows.team_llm.requests.post', side_effect=invalid_action):
        run = check(client, wid)
    assert run['status'] == 'needs_attention'
    assert run['tasks'][0]['status'] == 'failed'
    assert run['actions'] == []
    assert 'not supported by its tools' in run['tasks'][0]['error']


def test_cancel_stops_after_the_inflight_model_call(team, monkeypatch):
    client, wid, _, _, _ = team
    monkeypatch.setenv('PYTC_TEAM_MODEL', 'test-model')
    def cancel_during_call(*a, **kw):
        active = client.get(f'/api/workflows/{wid}/team-runs').json()[0]
        assert client.post(f"/api/workflows/{wid}/team-runs/{active['id']}/cancel").status_code == 200
        return model_reply(kw['json'])
    with patch('server_api.workflows.team_llm.requests.post', side_effect=cancel_during_call) as provider:
        run = check(client, wid)
    assert run['status'] == 'cancelled'
    assert provider.call_count == 1
    assert run['actions'] == []


def test_model_chat_persists_final_reply_and_only_current_project_memory(team, monkeypatch):
    from server_api.auth.models import ChatMessage
    client, wid, _, sessions, _ = team
    monkeypatch.setenv('PYTC_TEAM_MODEL', 'test-model')
    with patch('server_api.workflows.team_llm.requests.post', side_effect=lambda *a, **kw: model_reply(kw['json'])):
        response = client.post(f'/api/workflows/{wid}/agent/query', json={'query': 'Can you assess what I should do with these labels?'}).json()
    run = client.get(f'/api/workflows/{wid}/team-runs').json()[0]
    assert response['team_run_id'] == run['id']
    with sessions() as db:
        message = db.query(ChatMessage).filter_by(conversation_id=response['conversation_id'], role='assistant').first()
        assert message.content == run['summary']
    assert run['memory'] == []


@pytest.mark.parametrize("violation", ["tool", "evidence", "duplicate_role"])
def test_model_rejects_invalid_tool_evidence_and_delegation(team, monkeypatch, violation):
    client, wid, _, _, _ = team
    monkeypatch.setenv('PYTC_TEAM_MODEL', 'test-model')
    def invalid_response(*a, **kw):
        response = model_reply(kw['json'])
        body = response.json.return_value
        value = json.loads(body['message']['content'])
        if violation == 'duplicate_role' and 'tasks' in value:
            value['tasks'] *= 2
        elif violation == 'tool' and value.get('tool') == 'inspect_tiff':
            value['tool'] = 'run_shell'
        elif violation == 'evidence' and value.get('tool') == 'finish':
            value['evidence_ids'] = ['another-project:invented']
        body['message']['content'] = json.dumps(value)
        return response
    with patch('server_api.workflows.team_llm.requests.post', side_effect=invalid_response):
        run = check(client, wid)
    assert run['status'] in {'failed', 'needs_attention'}
    assert run['actions'] == []
    if violation == 'tool':
        assert run['tasks'][0].get('tool_calls', []) == []


def test_project_change_during_model_call_stops_stale_run(team, monkeypatch):
    client, wid, _, _, _ = team
    monkeypatch.setenv('PYTC_TEAM_MODEL', 'test-model')
    def change_project(*a, **kw):
        client.patch(f'/api/workflows/{wid}', json={'metadata': {'project_context': {'target_structure': 'changed'}}})
        return model_reply(kw['json'])
    with patch('server_api.workflows.team_llm.requests.post', side_effect=change_project) as provider:
        run = check(client, wid)
    assert run['status'] == 'failed'
    assert run['actions'] == []
    assert provider.call_count == 1
    assert 'inputs changed' in run['error']
