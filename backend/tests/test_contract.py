from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings
from pathlib import Path


def test_default_paths_and_explicit_environment(monkeypatch, tmp_path):
    monkeypatch.delenv('NOMAD_DB', raising=False)
    monkeypatch.delenv('NOMAD_DEMO', raising=False)
    settings = Settings.from_env()
    project = Path(__file__).resolve().parents[2]
    assert settings.database == project / 'runtime' / 'nomad.sqlite3'
    assert settings.frontend_dist == project / 'frontend' / 'dist'
    assert not settings.demo_enabled
    monkeypatch.setenv('NOMAD_DB', str(tmp_path / 'custom.sqlite3'))
    monkeypatch.setenv('NOMAD_DEMO', '1')
    assert Settings.from_env().database == tmp_path / 'custom.sqlite3'
    assert Settings.from_env().demo_enabled


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
