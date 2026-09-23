"""Run against a disposable PostgreSQL database specified in NOMAD_TEST_DATABASE_URL."""
import os
from dataclasses import replace
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.demo import DEMO_DATASET, DEMO_CALCULATION
from app.main import create_app
from test_workflow import draft, patch, approve, test_concurrent_save_uses_compare_and_swap as check_concurrent


@pytest.fixture
def pg(tmp_path):
    url = os.getenv('NOMAD_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set NOMAD_TEST_DATABASE_URL to a disposable PostgreSQL database')
    schema = 'test_' + uuid4().hex
    with psycopg.connect(url, autocommit=True) as db:
        db.execute(psycopg.sql.SQL('CREATE SCHEMA {}').format(psycopg.sql.Identifier(schema)))
    test_url = psycopg.conninfo.make_conninfo(url, options=f'-c search_path={schema}')
    settings = Settings(tmp_path/'unused.sqlite3', True, tmp_path/'dist', database_url=test_url)
    app = create_app(settings)
    app.state.service.seed_demo()
    yield TestClient(app), app.state.service, settings
    with psycopg.connect(url, autocommit=True) as db:
        db.execute(psycopg.sql.SQL('DROP SCHEMA {} CASCADE').format(psycopg.sql.Identifier(schema)))


def test_postgres_order_persistence_zero_and_concurrency(pg):
    client, service, settings = pg
    order = draft(client)
    assert patch(client, order, -1).status_code == 422
    changed = patch(client, order, 0).json()
    assert approve(client, order).status_code == 409
    approved = approve(client, changed).json()
    restarted = TestClient(create_app(settings))
    url = '/api/orders/' + order['id']
    assert restarted.get(url).json() == approved
    assert ';0;' in restarted.get(url+'/export?revision=3').content.decode('utf-8-sig')
    assert patch(restarted, approved, 12).json()['approved_revision'] is None
    assert restarted.get(url+'/export?revision=3').status_code == 409
    with service.repo.connection() as db:
        assert db.execute('SELECT count(*) FROM order_versions WHERE order_id=%s', (order['id'],)).fetchone()[0] == 4
    check_concurrent(pg)
    service.seed_demo()
    assert len(service.datasets()) == 1


def test_public_mode_blocks_import_and_private_objects(pg):
    client, service, settings = pg
    dataset = service.repo.get('dataset', DEMO_DATASET)
    from app.contracts import Dataset, CalculationResult
    private = Dataset.model_validate(dataset).model_copy(update={'id':'private', 'is_synthetic':False})
    calc = CalculationResult.model_validate(service.repo.get('calculation', DEMO_CALCULATION))
    calc = calc.model_copy(update={'id':'private-calc', 'is_synthetic':False})
    service.repo.save_bundle([('dataset', private.id, private), ('calculation', calc.id, calc)])
    public = TestClient(create_app(replace(settings, public_demo=True)))
    assert [d['id'] for d in public.get('/api/datasets').json()] == [DEMO_DATASET]
    assert public.get('/api/calculations/private-calc').status_code == 404
    response = public.post('/api/datasets', data={'supplier':'systeme'}, files={'files':('private.xlsx', b'no data')})
    assert response.status_code == 403
    assert response.json()['error']['code'] == 'PUBLIC_IMPORT_DISABLED'


def test_public_mode_requires_permanent_database(tmp_path):
    with pytest.raises(ValueError, match='DATABASE_URL'):
        Settings(tmp_path/'db', True, tmp_path, public_demo=True)
