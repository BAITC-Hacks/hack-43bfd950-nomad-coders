import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.demo import demo_bundle
from app.contracts import ApiError, ErrorResponse

target = Path(__file__).resolve().parents[2] / 'contracts' / 'fixtures'
target.mkdir(parents=True, exist_ok=True)
normalized, calculation, explanations = demo_bundle()
objects = {'dataset': normalized.dataset, 'normalized': normalized, 'calculation': calculation,
           'error': ErrorResponse(error=ApiError(code='NOT_IMPLEMENTED', message='Импорт ещё не подключён'))}
objects.update({f'explanation-{i}': value for i, value in enumerate(explanations, 1)})
for name, value in objects.items():
    (target / f'{name}.json').write_text(value.model_dump_json(indent=2) + '\n', encoding='utf-8')
print('Синтетические примеры записаны в contracts/fixtures')
