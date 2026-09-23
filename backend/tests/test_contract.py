from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings


def test_health_and_api_errors(tmp_path):
    client = TestClient(create_app(Settings(tmp_path / 'db.sqlite3', False, tmp_path / 'dist')))
    assert client.get('/api/health').json()['demo_enabled'] is False
    response = client.get('/api/no-such-route')
    assert response.status_code == 404
    assert response.json()['error']['code'] == 'NOT_FOUND'


def test_negative_manager_quantity_is_rejected(tmp_path):
    client = TestClient(create_app(Settings(tmp_path / 'db.sqlite3', False, tmp_path / 'dist')))
    response = client.patch('/api/orders/unknown', json={
        'expected_revision': 1,
        'overrides': [{'recommendation_id': 'a', 'quantity': -1, 'reason': 'Проверка'}],
    })
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'VALIDATION_ERROR'
