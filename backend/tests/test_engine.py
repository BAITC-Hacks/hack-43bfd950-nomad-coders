from datetime import date, datetime, timedelta, timezone
import calendar

import pytest

from app.contracts import (
    CalculationSettings, Dataset, Inbound, MonthlyObservation, NormalizedDataset,
    OrderConstraint, PlanningOverride, Product, SeasonalFactor, SourceRef,
    StockSnapshot, StockoutInterval, Transaction, TransactionCoverage, Issue,
)
from app.engine import calculate


SOURCE=SourceRef(file='synthetic-engine-test')
ASOF=date(2026,8,31)


def sample(count=90):
    return NormalizedDataset(
        dataset=Dataset(id='synthetic',version='v1',name='Synthetic engine fixture',
                        suppliers=['demo'],is_synthetic=True,created_at=datetime(2026,1,1,tzinfo=timezone.utc)),
        products=[Product(sku='000-A',article='001-A',name='Synthetic A',supplier='demo',unit='шт')],
        transaction_coverage=TransactionCoverage(start=ASOF-timedelta(days=count-1),end=ASOF,is_complete=True,source=SOURCE),
        transactions=[Transaction(sku='000-A',date=ASOF-timedelta(days=i),document_id='sale-'+str(i),
            document_type='Продажа',quantity=10,unit='шт',warehouse='A',source=SOURCE) for i in range(count)],
        stocks=[StockSnapshot(sku='000-A',as_of=ASOF,available=100,unit='шт',warehouse='A',is_current=True,source=SOURCE)])


def run(data, **settings):
    output=calculate(data,CalculationSettings(as_of=ASOF,**settings))
    return output.recommendations[0],output.explanations[0]


def test_baseline_rounding_and_input_unchanged():
    data=sample()
    data.inbound=[Inbound(sku='000-A',quantity=40,arrival_date=ASOF+timedelta(days=1),unit='шт',source=SOURCE)]
    data.constraints=[OrderConstraint(sku='000-A',multiple=12,unit='шт',source=SOURCE)]
    before=data.model_dump()
    rec,_=run(data)
    assert rec.quantity==144 and rec.components.raw_need==140
    assert data.model_dump()==before
    assert run(data)[0]==rec


@pytest.mark.parametrize(('arrival','expected'), [(2,0),(5,30),(6,40),(0,40)])
def test_dated_inbound(arrival,expected):
    data=sample();data.stocks[0].available=10
    data.inbound=[Inbound(sku='000-A',quantity=40,arrival_date=ASOF+timedelta(days=arrival),unit='шт',source=SOURCE)]
    rec,_=run(data,lead_time_days=2,review_days=3,buffer_days=0)
    assert rec.quantity==expected


def test_zero_lead_and_independent_minimum_multiple():
    data=sample();data.stocks[0].available=17
    data.constraints=[OrderConstraint(sku='000-A',minimum=20,multiple=12,unit='шт',source=SOURCE)]
    assert run(data,lead_time_days=0,review_days=3,buffer_days=0)[0].quantity==24
    data.constraints[0].multiple=None
    assert run(data,lead_time_days=0,review_days=3,buffer_days=0)[0].quantity==20
    data.stocks[0].available=1000
    assert run(data)[0].quantity==0


def test_missing_stale_stock_and_explicit_zero_override():
    data=sample();data.stocks[0].available=None
    assert run(data)[0].quantity is None
    data.stocks[0].available=100;data.stocks[0].is_current=False
    assert run(data)[0].quantity is None
    rec,explanation=run(data,overrides=[PlanningOverride(sku='000-A',available_stock=0,reason='Проверено на складе')])
    assert rec.quantity==280
    assert data.stocks[0].available==100
    assert any('Проверено на складе' in a for a in explanation.assumptions)


def test_single_outlier_aggregates_document_and_does_not_raise_growth():
    data=sample(240);baseline=run(data)[0]
    for quantity in [5000,5000]:
        data.transactions.append(data.transactions[0].model_copy(update={'quantity':quantity,'document_id':'bulk'}))
    rec,explanation=run(data)
    assert rec.quantity==baseline.quantity
    assert rec.components.growth_factor==baseline.components.growth_factor
    assert len(explanation.anomalies)==1
    assert explanation.anomalies[0].quantity==10000
    assert explanation.anomalies[0].decision=='excluded'
    assert sum(h.raw or 0 for h in explanation.history)>sum(h.cleaned or 0 for h in explanation.history)


@pytest.mark.parametrize('customer',[None,'synthetic-customer'])
def test_recurring_large_sales_are_retained(customer):
    data=sample()
    for week in range(8):
        data.transactions.append(data.transactions[0].model_copy(update={
            'date':ASOF-timedelta(days=7*week),'quantity':100,'document_id':'weekly-'+str(week),'customer_id':customer}))
    rec,explanation=run(data)
    assert rec.components.daily_demand>10
    assert len(explanation.anomalies)==8
    assert all(a.decision=='recurring' for a in explanation.anomalies)


def test_confirmed_stockout_and_overlapping_intervals():
    data=sample(30)
    for t in data.transactions:
        if t.date>ASOF-timedelta(days=10):
            t.quantity=0
    raw=run(data)[0].components.daily_demand
    data.stockouts=[StockoutInterval(sku='000-A',start=ASOF-timedelta(days=9),end=ASOF,source=SOURCE)]
    rec,_=run(data)
    assert raw==pytest.approx(200/30)
    assert rec.components.daily_demand==10
    assert rec.components.stockout_lost_demand==100
    assert rec.quantity==180  # 280 future units - 100 stock; historical loss not added again.
    data.stockouts.append(StockoutInterval(sku='000-A',start=ASOF-timedelta(days=4),end=ASOF,source=SOURCE))
    assert run(data)[0]==rec
    data.stockouts=[StockoutInterval(sku='000-A',start=data.transaction_coverage.start,end=ASOF,source=SOURCE)]
    assert run(data)[0].quantity is None


def test_seasonality_normalization_and_growth_once():
    data=sample(243)
    values={m:(2 if m==9 else 1) for m in range(1,13)}
    data.seasonality=[SeasonalFactor(supplier='demo',month=m,factor=v,source=SOURCE) for m,v in values.items()]
    mean=sum(values.values())/12
    for t in data.transactions:
        t.quantity=10*values[t.date.month]/mean
    rec,_=run(data)
    assert rec.components.growth_factor==pytest.approx(1)
    assert rec.components.daily_demand==pytest.approx(10)
    assert rec.components.forecast_demand==pytest.approx(21*10*2/mean)
    for s in data.seasonality:
        s.factor*=5
    assert run(data)[0].components.forecast_demand==pytest.approx(rec.components.forecast_demand)


def test_sustained_growth_and_manual_replacement():
    data=sample(184)  # March through August, six complete months.
    for t in data.transactions:
        t.quantity=20 if t.date.month>=6 else 10
    rec,_=run(data)
    assert rec.components.growth_factor==2
    assert rec.components.daily_demand==20
    rec,_=run(data,overrides=[PlanningOverride(sku='000-A',growth_factor=1,reason='Рост не подтверждён')])
    assert rec.components.daily_demand==10


def test_monthly_source_is_independent_and_missing_is_not_zero():
    data=sample()
    data.monthly=[MonthlyObservation(sku='000-A',month=date(2026,m,1),quantity=20*calendar.monthrange(2026,m)[1],
        kind='sales',is_complete=True,source=SOURCE) for m in range(3,9)]
    data.monthly.append(MonthlyObservation(sku='000-A',month=date(2026,9,1),quantity=100000,kind='sales',is_complete=False,source=SOURCE))
    assert run(data,demand_source='monthly')[0].components.daily_demand==pytest.approx(20)
    assert run(data)[0].components.daily_demand==10
    for m in data.monthly:
        m.quantity=None
    assert run(data,demand_source='monthly')[0].quantity is None


def test_returns_keep_their_sign_and_missing_unit_blocks():
    data=sample()
    data.transactions.append(data.transactions[0].model_copy(update={'document_id':'return','quantity':-20}))
    assert run(data)[0].components.daily_demand==pytest.approx(880/90)
    data.transactions[0].unit='м'
    assert run(data)[0].quantity is None


def test_missing_coverage_and_no_history_do_not_mean_zero():
    data=sample();data.transaction_coverage=None
    assert run(data)[0].quantity is None


def test_repeated_bulk_does_not_protect_giant_outlier():
    data=sample()
    for week in range(8):
        data.transactions.append(data.transactions[0].model_copy(update={'date':ASOF-timedelta(days=7*week),
            'quantity':100,'document_id':'weekly-'+str(week),'customer_id':'same-customer'}))
    baseline=run(data)[0]
    data.transactions.append(data.transactions[0].model_copy(update={'quantity':10000,'document_id':'giant','customer_id':'same-customer'}))
    rec,explanation=run(data)
    assert rec.quantity==baseline.quantity
    assert next(a for a in explanation.anomalies if a.document_id=='giant').decision=='excluded'


def test_global_block_and_future_transaction():
    data=sample();baseline=run(data)[0]
    data.transactions.append(data.transactions[0].model_copy(update={'date':ASOF+timedelta(days=1),'unit':'м','warehouse':'other'}))
    assert run(data)[0]==baseline
    data.dataset.issues=[Issue(code='INCOMPLETE',message='Источник повреждён',severity='blocking')]
    assert run(data)[0].quantity is None


def test_decimal_multiple_is_valid_in_order_service():
    from app.service import Service
    data=sample()
    for t in data.transactions:
        t.quantity=.25
    data.stocks[0].available=0
    data.constraints=[OrderConstraint(sku='000-A',multiple=.1,unit='шт',source=SOURCE)]
    rec,_=run(data,lead_time_days=0,review_days=1,buffer_days=0)
    assert rec.quantity==.3
    Service._validate_quantity(rec.quantity,rec)


def test_outlier_cleaning_cannot_hide_stockout_conflict():
    data=sample(30)
    data.transactions[0].quantity=10000
    data.stockouts=[StockoutInterval(sku='000-A',start=ASOF,end=ASOF,source=SOURCE)]
    rec,_=run(data)
    assert rec.quantity is None
    assert any(i.code=='STOCKOUT_CONFLICT' for i in rec.issues)
    data=sample();data.transactions=[]
    assert run(data)[0].quantity is None
