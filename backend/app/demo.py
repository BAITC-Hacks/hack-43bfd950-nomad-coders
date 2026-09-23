"""Hand-authored synthetic examples. These are NOT forecasts of partner data."""
from datetime import date, datetime, timezone

from app.contracts import (
    CalculationComponents, CalculationResult, CalculationSettings, Dataset, HistoryPoint,
    Issue, ItemExplanation, NormalizedDataset, Product, Recommendation, SourceRef,
)

DEMO_DATASET = 'demo-dataset-v1'
DEMO_CALCULATION = 'demo-calculation-v1'
CREATED = datetime(2026, 9, 22, 0, 0, tzinfo=timezone.utc)


def demo_settings():
    return CalculationSettings(as_of=date(2026, 9, 22), assumptions=[
        'Синтетический пример соединения компонентов, не результат прогноза.',
        'Срок 14 дней, пересмотр 7 дней и буфер 7 дней — демонстрационные допущения.',
    ])


def demo_bundle():
    source = SourceRef(file='synthetic-demo-v1', note='Полностью вымышленные данные')
    dataset = Dataset(id=DEMO_DATASET, version='synthetic-v1', name='Учебный склад · синтетика',
                      suppliers=['demo'], is_synthetic=True, created_at=CREATED, sources=[source])
    items = []
    for index, (name, stock, quantity, status) in enumerate([
        ('Автомат демонстрационный 16А', 100, 144, 'order_now'),
        ('Кабель демонстрационный', 500, 0, 'covered'),
        ('Розетка демонстрационная', None, None, 'needs_input'),
    ], 1):
        issues = [] if stock is not None else [Issue(code='MISSING_STOCK', severity='blocking',
                   message='Нет подтверждённого остатка. Количество заказа неизвестно.')]
        components = CalculationComponents(daily_demand=10, horizon_days=21,
            forecast_demand=210, safety_stock=70, available_stock=stock, eligible_inbound=40,
            raw_need=None if stock is None else max(0, 280 - stock - 40),
            multiple=12, minimum=None, growth_factor=1, stockout_lost_demand=None)
        items.append(Recommendation(id=f'demo-item-{index}',
            product=Product(sku=f'DEMO-00{index}', article=f'SYN-{index:03}', name=name,
                            supplier='demo', unit='шт', category='DEMO', sources=[source]),
            stock_date=date(2026, 9, 22) if stock is not None else None,
            quantity=quantity, urgency=status, demand_source='demo_fixture', components=components,
            explanation=('210 + 70 − 100 − 40 = 140 шт; округление до кратности 12: 144 шт.' if index == 1
                         else 'Доступного остатка достаточно, новый заказ не требуется.' if index == 2
                         else 'Нельзя рассчитать заказ без подтверждённого остатка.'), issues=issues))
    calculation = CalculationResult(id=DEMO_CALCULATION, dataset_id=dataset.id,
        dataset_version=dataset.version, created_at=CREATED, is_synthetic=True,
        engine_version='fixture-only-v1', settings=demo_settings(), recommendations=items)
    explanations = [ItemExplanation(calculation_id=calculation.id, dataset_version=dataset.version,
        is_synthetic=True, recommendation=item, assumptions=demo_settings().assumptions,
        history=[HistoryPoint(date=date(2026, month, 1), raw=value, cleaned=value, adjusted=value)
                 for month, value in [(5, 290), (6, 300), (7, 310), (8, 300)]]) for item in items]
    normalized = NormalizedDataset(dataset=dataset, products=[item.product for item in items])
    return normalized, calculation, explanations
