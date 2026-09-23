import hashlib
import math
from collections import defaultdict
from datetime import timedelta
from fractions import Fraction

from app.contracts import CalculationComponents, EngineOutput, HistoryPoint, Issue, ItemExplanation, Recommendation
from .demand import estimate, month_end


def indexed(records):
    result=defaultdict(list)
    for record in records:
        result[record.sku].append(record)
    return result


def plan_orders(data, settings):
    if len(data.dataset.suppliers)!=1 or any(p.supplier!=data.dataset.suppliers[0] for p in data.products):
        raise ValueError('Один набор должен содержать только одного поставщика')
    if len({p.sku for p in data.products})!=len(data.products):
        raise ValueError('В наборе повторяются коды товаров')
    if len({o.sku for o in settings.overrides})!=len(settings.overrides) or any(not o.reason.strip() for o in settings.overrides):
        raise ValueError('Переопределения должны быть уникальны и иметь непустую причину')
    product_ids={p.sku for p in data.products}
    if any(o.sku not in product_ids for o in settings.overrides):
        raise ValueError('Переопределение относится к неизвестному товару')
    tx, monthly, stocks, incoming, constraints, stockouts = (
        indexed(getattr(data, name)) for name in ('transactions','monthly','stocks','inbound','constraints','stockouts'))
    per_issue=indexed([i for i in data.dataset.issues if i.sku])
    overrides={o.sku:o for o in settings.overrides}
    factors={month:1.0 for month in range(1,13)}
    global_issues=[i for i in data.dataset.issues if i.sku is None]
    seasonal=[s for s in data.seasonality if s.supplier==data.dataset.suppliers[0]]
    if seasonal:
        if len(seasonal)!=12 or len({s.month for s in seasonal})!=12:
            raise ValueError('Нужен один положительный коэффициент сезонности на каждый месяц')
        mean=sum(s.factor for s in seasonal)/12
        factors={s.month:s.factor/mean for s in seasonal}
    else:
        global_issues.append(Issue(code='NEUTRAL_SEASONALITY',message='Сезонность неизвестна; применён нейтральный профиль 1'))
    if not data.stockouts:
        global_issues.append(Issue(code='NO_CONFIRMED_STOCKOUTS',message='Точных интервалов отсутствия товара нет; потерянный спрос не выдумывается по месячным остаткам'))
    if data.transactions and not any(t.customer_id for t in data.transactions):
        global_issues.append(Issue(code='NO_CUSTOMER_IDS',message='Анонимные ID клиентов отсутствуют; повторяемость крупных покупок проверяется по товару и неделям'))
    recommendations, explanations=[],[]
    for product in data.products:
        sku=product.sku; override=overrides.get(sku)
        issues=list(per_issue[sku])+[i for i in global_issues if i.severity=='blocking']
        assumptions=list(settings.assumptions)
        if not product.unit:
            issues.append(Issue(code='UNKNOWN_UNIT',message='Единица товара неизвестна или противоречива',sku=sku,severity='blocking'))
        records=[s for s in stocks[sku] if s.as_of<=settings.as_of]
        stock=max(records,key=lambda s:s.as_of) if records else None
        available=stock.available if stock else None
        stock_date=stock.as_of if stock else None
        if override and override.available_stock is not None:
            available=override.available_stock
            stock_date=settings.as_of
            assumptions.append('Доступный остаток задан менеджером на дату расчёта: '+override.reason)
        elif stock is None or available is None:
            issues.append(Issue(code='MISSING_STOCK',message='Нет подтверждённого доступного остатка; задайте его явно с причиной',sku=sku,severity='blocking'))
        elif not stock.is_current or stock.as_of!=settings.as_of:
            issues.append(Issue(code='STALE_STOCK',message='Остаток не подтверждён на дату расчёта; месячный снимок не равен текущему',sku=sku,severity='blocking',source=stock.source))
        if stock and stock.unit!=product.unit:
            issues.append(Issue(code='STOCK_UNIT_CONFLICT',message='Единица остатка не совпадает с единицей товара',sku=sku,severity='blocking'))
        covered_end=min(settings.as_of,data.transaction_coverage.end) if data.transaction_coverage else settings.as_of
        covered_start=max(data.transaction_coverage.start,covered_end-timedelta(days=364)) if data.transaction_coverage else covered_end-timedelta(days=364)
        relevant_tx=[t for t in tx[sku] if covered_start<=t.date<=covered_end] if settings.demand_source=='transactions' else []
        if any(t.unit!=product.unit for t in relevant_tx if t.quantity is not None):
            issues.append(Issue(code='DEMAND_UNIT_CONFLICT',message='Единицы операций не совпадают с единицей товара',sku=sku,severity='blocking'))
        warehouses={t.warehouse for t in relevant_tx if t.warehouse}
        if data.transaction_coverage:
            month_totals=defaultdict(float)
            for t in tx[sku]:
                if t.quantity is not None and covered_start<=t.date<=covered_end:
                    month_totals[t.date.replace(day=1)]+=t.quantity
            differences=[m for m in monthly[sku] if m.kind=='sales' and m.quantity is not None
                and covered_start<=m.month and month_end(m.month)<=covered_end
                and abs(month_totals[m.month]-m.quantity)>max(1,abs(m.quantity)*.05)]
            if differences:
                m=differences[-1]
                issues.append(Issue(code='SOURCE_DISCREPANCY',sku=sku,source=m.source,
                    message=f'Месячный отчёт и журнал расходятся за {len(differences)} мес.; например {m.month:%Y-%m}: {m.quantity:g} и {month_totals[m.month]:g}. Источники не суммируются.'))
        if any(m.kind=='opening_stock' and m.quantity==0 and m.month<=settings.as_of for m in monthly[sku]):
            issues.append(Issue(code='POSSIBLE_STOCKOUT',sku=sku,message='Есть нулевой месячный остаток; он не определяет точные дни stockout'))
        if len(warehouses)>1:
            issues.append(Issue(code='WAREHOUSE_SCOPE',message='Несколько складов в спросе; соответствие остатку не подтверждено',sku=sku,severity='blocking'))
        if stock and stock.warehouse and warehouses and warehouses!={stock.warehouse}:
            issues.append(Issue(code='WAREHOUSE_SCOPE',message='Склад спроса не совпадает со складом остатка',sku=sku,severity='blocking'))
        minimum=multiple=None
        if len(constraints[sku])>1:
            issues.append(Issue(code='CONSTRAINT_CONFLICT',message='Несколько правил заказа одного товара',sku=sku,severity='blocking'))
        elif constraints[sku]:
            rule=constraints[sku][0];minimum=rule.minimum;multiple=rule.multiple
            if rule.unit!=product.unit:
                issues.append(Issue(code='CONSTRAINT_UNIT_CONFLICT',message='Единица минимальной отгрузки/кратности не подтверждена',sku=sku,severity='blocking'))
        else:
            issues.append(Issue(code='NO_ORDER_CONSTRAINT',message='Минимум и кратность не заданы; применена только точность единицы',sku=sku))
        demand=estimate(tx[sku],monthly[sku],stockouts[sku],data.transaction_coverage,settings,factors,override)
        issues.extend(i.model_copy(update={'sku':sku}) for i in demand.issues)
        assumptions.extend(demand.assumptions)
        buffer=settings.category_buffer_days.get(product.category,settings.buffer_days)
        horizon=settings.lead_time_days+settings.review_days
        arrivals=defaultdict(float)
        for delivery in incoming[sku]:
            if delivery.unit!=product.unit:
                issues.append(Issue(code='INBOUND_UNIT_CONFLICT',message='Единица поставки не совпадает с единицей товара',sku=sku,severity='blocking',source=delivery.source))
                continue
            if delivery.arrival_date is None:
                issues.append(Issue(code='UNKNOWN_INBOUND_DATE',message='Поставка без даты не уменьшает заказ',sku=sku,source=delivery.source))
                continue
            offset=(delivery.arrival_date-settings.as_of).days
            if offset<=0:
                issues.append(Issue(code='PAST_INBOUND',message='Поставка на/до даты остатка повторно не учтена',sku=sku,source=delivery.source))
            elif offset<=horizon:
                arrivals[offset]+=delivery.quantity
        daily=demand.base*demand.growth if demand.base is not None else None
        forecast=safety=raw_need=quantity=None
        urgency='needs_input';peak_day=None
        eligible=sum(arrivals.values())
        if daily is not None:
            future=[daily*factors[(settings.as_of+timedelta(days=offset)).month] for offset in range(1,horizon+buffer+1)]
            cumulative=[0]
            for value in future:
                cumulative.append(cumulative[-1]+value)
            forecast=cumulative[horizon]
            safety=cumulative[horizon+buffer]-cumulative[horizon]
            if available is not None:
                raw_need=0; received=0; early_deficit=False
                for day in range(1,horizon+1):
                    received+=arrivals[day]
                    if day<max(1,settings.lead_time_days) and cumulative[day]>available+received+1e-9:
                        early_deficit=True
                    if day>=max(1,settings.lead_time_days):
                        need=cumulative[day+buffer]-available-received
                        if need>raw_need:
                            raw_need=need;peak_day=day
                if not any(i.severity=='blocking' for i in issues):
                    positive=max(0,raw_need)
                    if positive<=1e-9:
                        quantity=0
                    else:
                        positive=max(positive,minimum or 0)
                        step=multiple or (1 if product.unit in ('шт','упак') else .01)
                        # Fraction prevents decimal context overflow on finite input.
                        quotient=Fraction(str(positive))/Fraction(str(step))
                        count=math.ceil(quotient-Fraction(1,10**9))
                        quantity=float(max(0,count)*Fraction(str(step)))
                    urgency='expedite' if early_deficit else ('order_now' if quantity>0 else 'covered')
                if early_deficit:
                    issues.append(Issue(code='BEFORE_LEAD_TIME',message='Ожидается дефицит до обычного срока поставки; требуется ускорение или перемещение',sku=sku))
            for day,value in enumerate(future[:horizon],1):
                demand.history.append(HistoryPoint(date=settings.as_of+timedelta(days=day),raw=None,cleaned=None,adjusted=None,forecast=value))
        if quantity is None:
            urgency='needs_input'
            explanation='Расчёт заказа заблокирован: '+'; '.join(dict.fromkeys(i.message for i in issues if i.severity=='blocking'))
        else:
            explanation=(f'Источник: {settings.demand_source}. Базовый спрос с ростом {daily:.4g} {product.unit}/день; '
                f'прогноз на {horizon} дн. {forecast:.4g}, буфер на конец горизонта {safety:.4g}, '
                f'доступный остаток {available:.4g}, датированные поступления в горизонте {eligible:.4g}. '
                f'Максимальная потребность по дням {raw_need:.4g}; минимум {minimum if minimum is not None else "не задан"}, '
                f'кратность {multiple if multiple is not None else "не задана"}; заказ {quantity:.4g} {product.unit}.')
            if peak_day:
                explanation+=f' Пик потребности: {(settings.as_of+timedelta(days=peak_day)).isoformat()}; поздние приходы не покрывают предыдущие дни.'
        rid=hashlib.sha256((product.supplier+'/'+sku).encode()).hexdigest()[:20]
        recommendation=Recommendation(id=rid,product=product,stock_date=stock_date,quantity=quantity,
            urgency=urgency,explanation=explanation,demand_source=settings.demand_source,
            components=CalculationComponents(daily_demand=daily,horizon_days=horizon,forecast_demand=forecast,
                safety_stock=safety,available_stock=available,eligible_inbound=eligible,raw_need=raw_need,
                minimum=minimum,multiple=multiple,growth_factor=demand.growth,
                stockout_lost_demand=demand.lost if stockouts[sku] else None),
            issues=issues)
        recommendations.append(recommendation)
        explanations.append(ItemExplanation(calculation_id='pending',dataset_version=data.dataset.version,
            is_synthetic=data.dataset.is_synthetic,recommendation=recommendation,history=demand.history,
            inbound=incoming[sku],anomalies=demand.anomalies,assumptions=assumptions))
    return EngineOutput(recommendations=recommendations,explanations=explanations,issues=global_issues)
