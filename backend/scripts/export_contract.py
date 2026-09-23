"""Run from backend: python scripts/export_contract.py."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import create_app
from app.contracts import NormalizedDataset, EngineOutput

target = Path(__file__).resolve().parents[2] / 'contracts'
target.mkdir(exist_ok=True)
schema = create_app().openapi()
# Internal engine models are also generated for a single contract vocabulary.
for model in (NormalizedDataset, EngineOutput):
    extra = model.model_json_schema(ref_template='#/components/schemas/{model}')
    definitions = extra.pop('$defs', {})
    schema['components']['schemas'].update(definitions)
    schema['components']['schemas'][model.__name__] = extra
(target / 'openapi.json').write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('contracts/openapi.json')
