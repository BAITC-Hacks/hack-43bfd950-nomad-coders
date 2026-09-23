"""Demand estimates are deterministic; observations are never mutated."""
import calendar
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.contracts import AnomalyDecision, HistoryPoint, Issue


def days(start, end):
    for offset in range(max(0, (end-start).days+1)):
        yield start+timedelta(days=offset)


def month_end(day):
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


@dataclass
class Demand:
    base: float | None = None
    growth: float = 1
    lost: float = 0
    history: list = field(default_factory=list)
    anomalies: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    assumptions: list = field(default_factory=list)


def clean_documents(transactions):
    grouped = defaultdict(list)
    for t in transactions:
        if t.quantity is not None:
            grouped[(t.date, t.document_id, t.customer_id, t.document_type)].append(t)
    docs = [(key, sum(t.quantity for t in rows), rows) for key, rows in sorted(grouped.items(), key=lambda pair:str(pair[0]))]
    positive = [q for _,q,_ in docs if q>0]
    if len(positive)<8:
        return docs, [], ['Недостаточно документов для уверенного автоматического исключения всплесков.']
    quartiles=statistics.quantiles(positive,n=4,method='inclusive')
    threshold=max(quartiles[2]+3*(quartiles[2]-quartiles[0]),statistics.median(positive)*5)
    candidates=[(key,q,rows) for key,q,rows in docs if q>threshold]
    decisions, cleaned=[],[]
    for key,q,rows in docs:
        if q<=threshold:
            cleaned.append((key,q,rows));continue
        # Repeated modest bulk orders must not protect a vastly larger one-off.
        peers=[k for k,value,_ in candidates if q/2<=value<=q*2]
        dates=sorted({k[0] for k in peers})
        weeks={d.isocalendar()[:2] for d in dates}
        regular=len(weeks)>=3 and statistics.median([(b-a).days for a,b in zip(dates,dates[1:])])<=21
        same_customer=key[2] is not None and regular and len({k[0].isocalendar()[:2] for k in peers if k[2]==key[2]})>=3
        recent_cluster=len(dates)>=3 and (dates[-1]-dates[0]).days<=14
        if regular or same_customer:
            decision='recurring'
            reason=('Повторяющиеся крупные покупки клиента в разных неделях.' if same_customer else
                    'Крупные покупки повторяются в разных неделях; принадлежность одному клиенту не утверждается.')
        elif recent_cluster:
            decision='review'
            reason='Серия крупных документов может означать новый уровень спроса; сохранена до проверки.'
        else:
            decision='excluded'
            reason=f'Одиночный документ выше устойчивого порога {threshold:.3g}; исключён из регулярного спроса.'
        decisions.append(AnomalyDecision(document_id=key[1],date=key[0],quantity=q,decision=decision,
                                        reason=reason,sources=[t.source for t in rows]))
        cleaned.append((key,0 if decision=='excluded' else q,rows))
    return cleaned,decisions,[]


def estimate(transactions, monthly, stockouts, coverage, settings, factors, override):
    result=Demand()
    raw=defaultdict(float);cleaned=defaultdict(float)
    if settings.demand_source=='transactions':
        if coverage is None:
            result.issues.append(Issue(code='MISSING_COVERAGE',message='Не задан период покрытия журнала операций',severity='blocking'))
            return result
        end=min(settings.as_of,coverage.end)
        start=max(coverage.start,end-timedelta(days=364))
        relevant=[t for t in transactions if start<=t.date<=end]
        if not relevant:
            result.issues.append(Issue(code='NO_HISTORY',message='Нет операций выбранного товара в периоде; отсутствие истории не означает нулевой спрос',severity='blocking'))
            return result
        if any(t.quantity is None for t in relevant):
            result.issues.append(Issue(code='UNKNOWN_TRANSACTION',message='В выбранной истории есть неизвестные количества',severity='blocking'))
        if not coverage.is_complete:
            result.assumptions.append('Полнота журнала не подтверждена; календарные дни без операций внутри указанного покрытия приняты без продаж.')
            result.issues.append(Issue(code='UNCONFIRMED_COVERAGE',message=result.assumptions[-1]))
        documents, result.anomalies, notes=clean_documents(relevant)
        result.assumptions.extend(notes)
        for t in relevant:
            if t.quantity is not None:
                raw[t.date]+=t.quantity
        for key,q,_ in documents:
            cleaned[key[0]]+=q
        if any(t.quantity is not None and t.quantity<0 for t in relevant):
            result.issues.append(Issue(code='SIGNED_RETURNS',message='Отрицательные операции сохранены со знаком и уменьшают чистый спрос; семантику возвратов следует проверить'))
        recognized=('расходная накладная','возврат','продажа','реализация')
        if any(not t.document_type.lower().startswith(recognized) for t in relevant):
            result.issues.append(Issue(code='DOCUMENT_TYPE_REVIEW',message='Есть виды документов с неподтверждённой семантикой; количества сохранены со знаком'))
    else:
        available=[m for m in monthly if m.kind=='sales' and m.is_complete and month_end(m.month)<=settings.as_of]
        known=[m for m in available if m.quantity is not None]
        if not known:
            result.issues.append(Issue(code='NO_MONTHLY_HISTORY',message='Нет полных месяцев с известными продажами',severity='blocking'))
            return result
        end=month_end(max(m.month for m in known))
        start=max(min(m.month for m in known),(end-timedelta(days=335)).replace(day=1))
        lookup={m.month:m for m in available if m.month>=start}
        known_days=set()
        excluded_stockout={d for interval in stockouts for d in days(max(start,interval.start),min(end,interval.end))}
        for observation in lookup.values():
            if observation.quantity is None:
                continue
            dates=list(days(observation.month,month_end(observation.month)))
            in_stock=[d for d in dates if d not in excluded_stockout]
            if not in_stock:
                if observation.quantity:
                    result.issues.append(Issue(code='STOCKOUT_CONFLICT',message='Продажи есть в полностью закрытом периоде stockout',severity='blocking'))
                known_days.update(dates)
                continue
            for d in dates:
                raw[d]=observation.quantity/len(dates)
                cleaned[d]=observation.quantity/len(in_stock) if d in in_stock else 0
                known_days.add(d)
        result.assumptions.append('Месячные продажи распределены равномерно по известным дням наличия; документы и клиентов по агрегатам проверить нельзя.')
        result.issues.append(Issue(code='MONTHLY_ANOMALY_LIMIT',message='Месячный источник не позволяет надёжно выделить разовую накладную; транзакции не добавляются к месячным продажам'))
    calendar_days=list(days(start,end))
    if settings.demand_source=='monthly':
        calendar_days=[d for d in calendar_days if d in known_days]
        if len(calendar_days)<(end-start).days+1:
            result.issues.append(Issue(code='MISSING_MONTHS',message='Неизвестные месяцы исключены из знаменателя, а не приняты за нули'))
    if len(calendar_days)<28:
        result.issues.append(Issue(code='SHORT_HISTORY',message='Нужно хотя бы 28 известных календарных дней истории',severity='blocking'))
        return result
    if (settings.as_of-end).days>60:
        result.issues.append(Issue(code='STALE_HISTORY',message='Последние наблюдения старше 60 дней относительно даты расчёта',severity='blocking'))
    unavailable={d for interval in stockouts for d in days(max(start,interval.start),min(end,interval.end))}
    observed=[d for d in calendar_days if d not in unavailable]
    if not observed:
        result.issues.append(Issue(code='NO_IN_STOCK_HISTORY',message='Вся история закрыта stockout; базовый спрос неизвестен',severity='blocking'))
        return result
    if settings.demand_source=='transactions' and any(t.quantity is not None and t.quantity>0 and t.date in unavailable for t in relevant):
        result.issues.append(Issue(code='STOCKOUT_CONFLICT',message='Продажи противоречат подтверждённым дням отсутствия товара',severity='blocking'))
    rate=max(0,sum(cleaned[d]/factors[d.month] for d in observed)/len(observed))
    adjusted={d:rate*factors[d.month] if d in unavailable else cleaned[d] for d in calendar_days}
    result.lost=sum(max(0,adjusted[d]-cleaned[d]) for d in calendar_days if d in unavailable)
    by_month=defaultdict(list)
    for d in calendar_days:
        by_month[d.replace(day=1)].append(d)
    full_rates=[]
    for month, dates in sorted(by_month.items()):
        result.history.append(HistoryPoint(date=month,raw=sum(raw[d] for d in dates),
            cleaned=sum(cleaned[d] for d in dates),adjusted=sum(adjusted[d] for d in dates)))
        if len(dates)==calendar.monthrange(month.year,month.month)[1] and month_end(month)<=settings.as_of:
            full_rates.append((month,sum(adjusted[d]/factors[d.month] for d in dates)/len(dates)))
    base=rate
    if len(full_rates)>=6:
        last=full_rates[-6:]
        consecutive=all((b[0].year-a[0].year)*12+b[0].month-a[0].month==1 for a,b in zip(last,last[1:]))
        previous=statistics.median(v for _,v in last[:3])
        recent=statistics.median(v for _,v in last[3:])
        if consecutive and previous>0:
            base=previous
            ratio=recent/previous
            sustained=(ratio>1.1 and all(v>previous*1.05 for _,v in last[3:])) or (ratio<.9 and all(v<previous*.95 for _,v in last[3:]))
            result.growth=max(.5,min(2,ratio)) if sustained else 1
            if not sustained:
                base=statistics.median(v for _,v in last)
            if sustained and result.growth!=ratio:
                result.issues.append(Issue(code='GROWTH_CAPPED',message='Оценка роста ограничена диапазоном 0.5–2; проверьте изменение спроса'))
        else:
            result.assumptions.append('Нет непрерывных шести месяцев с ненулевой базой; автоматический рост не применён.')
    else:
        result.assumptions.append('Менее шести полных месяцев: автоматический рост не применён.')
    if override and override.growth_factor is not None:
        result.growth=override.growth_factor
        result.assumptions.append('Рост заменён ручным коэффициентом: '+override.reason)
    result.base=max(0,base)
    result.assumptions.append('Сезонность снята с истории и применяется один раз к каждому прогнозному дню. Stockout увеличивает скорость спроса, не добавляется как долг к заказу.')
    return result
