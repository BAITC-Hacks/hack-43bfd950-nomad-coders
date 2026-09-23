"""Wholly invented observations passed through the actual statistical engine."""
from datetime import date, datetime, timedelta, timezone

from app.contracts import (
    Dataset, Inbound, NormalizedDataset, OrderConstraint, Product, SeasonalFactor,
    SourceRef, StockSnapshot, StockoutInterval, Transaction, TransactionCoverage,
)

ENGINE_DEMO_ID = 'a-engine-demo-v1'


def engine_demo():
    end = date(2026, 9, 22)
    start = end - timedelta(days=269)
    source = SourceRef(file='synthetic-statistical-v1', note='Вымышленные наблюдения для проверки реального движка')
    products = [Product(sku=f'SYN-{i}', article=f'DEMO-{i:03}', name=name,
                        supplier='demo', unit='шт', category='DEMO', sources=[source])
                for i, name in enumerate(['Учебный автомат 16А', 'Учебный выключатель', 'Учебный контактор'], 1)]
    outage_start, outage_end = end-timedelta(days=65), end-timedelta(days=60)
    transactions = []
    for product in products:
        for offset in range(270):
            day = start + timedelta(days=offset)
            if product.sku == 'SYN-1' and outage_start <= day <= outage_end:
                continue
            transactions.append(Transaction(sku=product.sku, date=day, document_id=f'{product.sku}-{offset}',
                document_type='Продажа', quantity=10, unit='шт', warehouse='Учебный склад',
                customer_id='synthetic-regular', source=source))
    transactions.append(Transaction(sku='SYN-1', date=end-timedelta(days=50), document_id='synthetic-one-off',
        document_type='Продажа', quantity=10000, unit='шт', warehouse='Учебный склад',
        customer_id='synthetic-one-off-customer', source=source))
    return NormalizedDataset(
        dataset=Dataset(id=ENGINE_DEMO_ID, version='synthetic-statistical-v1', name='Расчёт закупки · синтетические наблюдения',
            suppliers=['demo'], is_synthetic=True, created_at=datetime(2026,9,22,tzinfo=timezone.utc), sources=[source]),
        products=products, transactions=transactions,
        transaction_coverage=TransactionCoverage(start=start, end=end, is_complete=True, source=source),
        stocks=[StockSnapshot(sku='SYN-1',as_of=end,available=100,unit='шт',is_current=True,source=source),
                StockSnapshot(sku='SYN-2',as_of=end,available=500,unit='шт',is_current=True,source=source)],
        inbound=[Inbound(sku='SYN-1',quantity=40,arrival_date=end+timedelta(days=1),unit='шт',source=source)],
        constraints=[OrderConstraint(sku=p.sku,multiple=12,unit='шт',source=source) for p in products],
        seasonality=[SeasonalFactor(supplier='demo',month=m,factor=1,source=source) for m in range(1,13)],
        stockouts=[StockoutInterval(sku='SYN-1',start=outage_start,end=outage_end,source=source)])


def seed_engine_demo(service):
    data = engine_demo()
    service.repo.save_bundle([('dataset', data.dataset.id, data.dataset),
                             ('normalized', data.dataset.id, data)], ignore=True)
