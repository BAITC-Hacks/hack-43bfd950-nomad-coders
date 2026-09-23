import csv
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.errors import DomainError
from app.config import Settings
from app.contracts import CalculationResult, Dataset, ErrorResponse, ItemExplanation, NormalizedDataset, OrderPatch
from app.demo import DEMO_CALCULATION, DEMO_DATASET, demo_settings
from app.export.csv_export import safe_text
from app.main import create_app
from app.service import Service


@pytest.fixture
def context(tmp_path):
    settings = Settings(tmp_path / 'db.sqlite3', True, tmp_path / 'dist')
    app = create_app(settings)
    app.state.service.seed_demo()
    return TestClient(app), app.state.service, settings


def draft(client, ids=None):
    response = client.post('/api/orders', json={'calculation_id': DEMO_CALCULATION,
        'supplier': 'demo', 'recommendation_ids': ids or ['demo-item-1', 'demo-item-2']})
    assert response.status_code == 201, response.text
    return response.json()


def patch(client, order, value=0, reason='Проверка менеджера'):
    return client.patch('/api/orders/' + order['id'], json={'expected_revision': order['revision'],
        'overrides': [{'recommendation_id': 'demo-item-1', 'quantity': value, 'reason': reason}]})


def approve(client, order):
    return client.post('/api/orders/' + order['id'] + '/approve',
                       json={'expected_revision': order['revision'], 'confirmed': True})


def test_full_workflow_persistence_and_zero_csv(context):
    client, service, settings = context
    result = client.post('/api/calculations', json={'dataset_id': DEMO_DATASET,
        'settings': demo_settings().model_dump(mode='json')})
    assert result.status_code == 201
    calculation = result.json()
    assert [r['quantity'] for r in calculation['recommendations']] == [144, 0, None]
    explanation = client.get('/api/calculations/' + calculation['id'] + '/items/demo-item-1')
    assert explanation.json()['calculation_id'] == calculation['id']
    order = draft(client)
    url = '/api/orders/' + order['id']
    assert client.get(url + '/export?revision=1').status_code == 409
    changed = patch(client, order, reason='=SUM(1+1)').json()
    assert changed['revision'] == 2
    assert changed['lines'][0]['override_quantity'] == 0
    assert changed['lines'][0]['recommended_quantity'] == 144
    assert approve(client, order).status_code == 409
    approved = approve(client, changed).json()
    assert approved['approved_revision'] == approved['revision'] == 3
    restarted = TestClient(create_app(settings))
    assert restarted.get(url).json() == approved
    export = restarted.get(url + '/export?revision=3')
    assert export.status_code == 200
    assert export.content.startswith(b'\xef\xbb\xbf')
    rows = list(csv.DictReader(io.StringIO(export.content.decode('utf-8-sig')), delimiter=';'))
    assert rows[0]['Согласовано'] == '0'
    assert rows[0]['Причина правки'] == "'=SUM(1+1)"
    assert rows[0]['Рекомендовано'] == '144'
    new = patch(client, approved, 12).json()
    assert new['revision'] == 4 and new['approved_revision'] is None
    assert new['status'] == 'draft'
    assert client.get(url + '/export?revision=3').status_code == 409
    assert client.get(url + '/export?revision=4').status_code == 409
    assert service.calculation(DEMO_CALCULATION).recommendations[0].quantity == 144
    with service.repo.connection() as db:
        assert db.execute('SELECT count(*) FROM order_versions WHERE order_id=?', (order['id'],)).fetchone()[0] == 4


@pytest.mark.parametrize(('value', 'reason'), [(-1, 'Причина'), (1, 'Причина'), (12, '   '), (1e30, 'Большое число')])
def test_invalid_edit_is_atomic(context, value, reason):
    client, _, _ = context
    order = draft(client)
    assert patch(client, order, value, reason).status_code == 422
    assert client.get('/api/orders/' + order['id']).json() == order


def test_missing_duplicate_and_blocked_items(context):
    client, _, _ = context
    for ids in [['demo-item-3'], ['demo-item-1', 'demo-item-1'], ['unknown']]:
        assert client.post('/api/orders', json={'calculation_id': DEMO_CALCULATION, 'supplier': 'demo',
                                               'recommendation_ids': ids}).status_code == 422
    for path in ['/api/orders/missing', '/api/calculations/missing',
                 '/api/calculations/' + DEMO_CALCULATION + '/items/missing']:
        assert client.get(path).status_code == 404


def test_concurrent_save_uses_compare_and_swap(context):
    client, service, _ = context
    order = draft(client)
    body = OrderPatch(expected_revision=1, overrides=[{'recommendation_id': 'demo-item-1', 'quantity': 0, 'reason': 'Конкурентная правка'}])
    def save(_):
        try:
            return service.patch_order(order['id'], body).revision
        except DomainError as exc:
            return exc.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(save, range(2))) == [2, 409]


def test_seed_repeat_and_explicit_demo_mode(context):
    client, service, settings = context
    order = draft(client)
    service.seed_demo()
    assert len(client.get('/api/datasets').json()) == 1
    assert client.get('/api/orders/' + order['id']).json() == order
    off = TestClient(create_app(Settings(settings.database, False, settings.frontend_dist)))
    assert off.get('/api/datasets').json() == []
    assert off.get('/api/orders/' + order['id']).status_code == 404
    assert off.get('/api/calculations/' + DEMO_CALCULATION).status_code == 404


def test_unimplemented_adapters_return_501(context):
    client, service, _ = context
    response = client.post('/api/datasets', data={'supplier': 'systeme'}, files={'files': ('test.xlsx', b'placeholder')})
    assert response.status_code == 501
    settings = demo_settings().model_copy(update={'lead_time_days': 30})
    assert client.post('/api/calculations', json={'dataset_id': DEMO_DATASET,
        'settings': settings.model_dump(mode='json')}).status_code == 501
    normalized = NormalizedDataset.model_validate(service.repo.get('normalized', DEMO_DATASET))
    normalized.dataset.id = 'real-adapter-boundary'
    normalized.dataset.is_synthetic = False
    service.repo.save_bundle([('dataset', normalized.dataset.id, normalized.dataset),
                             ('normalized', normalized.dataset.id, normalized)])
    response = client.post('/api/calculations', json={'dataset_id': normalized.dataset.id,
        'settings': demo_settings().model_dump(mode='json')})
    assert response.status_code == 501
    assert response.json()['error']['code'] == 'ENGINE_NOT_IMPLEMENTED'


@pytest.mark.parametrize('text', ['=1+1', '+1', '-1', '@SUM(A1)', '  =1', '\t1', '\n1', '\r1'])
def test_csv_text_formula_guard(text):
    assert safe_text(text) == "'" + text


def test_static_fallback_keeps_api_json(context):
    client, _, settings = context
    settings.frontend_dist.mkdir()
    (settings.frontend_dist / 'index.html').write_text('<html>Application</html>', encoding='utf-8')
    assert client.get('/orders/saved').text == '<html>Application</html>'
    assert client.get('/api/unknown').status_code == 404
    assert client.get('/api/unknown').headers['content-type'].startswith('application/json')
    assert client.get('/missing.js').status_code == 404


def test_shared_examples_validate():
    root = Path(__file__).resolve().parents[2] / 'contracts' / 'fixtures'
    mapping = {'dataset': Dataset, 'normalized': NormalizedDataset, 'calculation': CalculationResult, 'error': ErrorResponse}
    for path in root.glob('*.json'):
        model = ItemExplanation if path.stem.startswith('explanation') else mapping[path.stem]
        model.model_validate(json.loads(path.read_text(encoding='utf-8')))
