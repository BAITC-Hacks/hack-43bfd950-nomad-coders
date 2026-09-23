"""HTTP check for a public demo. Creates one clearly labelled synthetic order."""
import argparse
import csv
import io
import json
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--verify-restart', action='store_true')
    args = parser.parse_args()
    with httpx.Client(base_url=args.url.rstrip('/'), timeout=120) as client:
        def data(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        assert data('GET', '/api/health')['demo_enabled']
        assert client.get('/').status_code == 200
        assert client.get('/orders/saved').headers['content-type'].startswith('text/html')
        unknown = client.get('/api/unknown')
        assert unknown.status_code == 404 and unknown.headers['content-type'].startswith('application/json')
        if args.verify_restart:
            expected = json.loads(args.state.read_text(encoding='utf-8'))
            assert data('GET', '/api/orders/'+expected['id']) == expected
            print('Order survived restart:', expected['id'])
            return
        datasets = data('GET', '/api/datasets')
        assert len({d['id'] for d in datasets}) == len(datasets)
        assert all(d['is_synthetic'] for d in datasets)
        result = data('POST', '/api/calculations', json={'dataset_id':'a-engine-demo-v1', 'settings':{
            'as_of':'2026-09-22','lead_time_days':14,'review_days':7,'buffer_days':7,'demand_source':'transactions'}})
        assert result['engine_version'] == 'statistical-v1'
        assert [r['quantity'] for r in result['recommendations']] == [144,0,None]
        item = result['recommendations'][0]['id']
        assert data('GET',f"/api/calculations/{result['id']}/items/{item}")['history']
        order = data('POST','/api/orders',json={'calculation_id':result['id'],'supplier':'demo','recommendation_ids':[item]})
        url = '/api/orders/'+order['id']
        order = data('PATCH',url,json={'expected_revision':order['revision'],'overrides':[
            {'recommendation_id':item,'quantity':0,'reason':'Синтетическая проверка публикации'}]})
        order = data('POST',url+'/approve',json={'expected_revision':order['revision'],'confirmed':True})
        exported = client.get(url+f"/export?revision={order['revision']}")
        exported.raise_for_status()
        rows = list(csv.DictReader(io.StringIO(exported.content.decode('utf-8-sig')),delimiter=';'))
        assert rows[0]['Согласовано'] == '0'
        assert client.post('/api/datasets',data={'supplier':'systeme'},files={'files':('synthetic.xlsx',b'not private data')}).status_code == 403
        args.state.parent.mkdir(parents=True,exist_ok=True)
        args.state.write_text(json.dumps(order,ensure_ascii=False),encoding='utf-8')
        print('HTTP -> actual engine -> order -> zero -> approval -> CSV passed. Order:',order['id'])


if __name__ == '__main__':
    main()
