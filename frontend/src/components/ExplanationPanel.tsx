import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { api, type Explanation } from '../api/client'
import { date, demandSources, ErrorNotice, Issues, quantity, RecommendationQuantity, sourceText } from './common'
const HistoryChart = lazy(() => import('./HistoryChart'))
export function ExplanationPanel({ calculationId, itemId, onClose }: { calculationId: string; itemId: string; onClose: () => void }) {
  const [data, setData] = useState<Explanation | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [retry, setRetry] = useState(0)
  const panel = useRef<HTMLDivElement>(null)
  useEffect(() => {
    let active = true
    setData(null); setError(null)
    void api.explanation(calculationId, itemId).then(result => { if (active) setData(result) }, e => { if (active) setError(e) })
    return () => { active = false }
  }, [calculationId, itemId, retry])
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    panel.current?.focus()
    return () => { document.body.style.overflow = overflow; previous?.focus() }
  }, [])
  const r = data?.recommendation
  return <div className="drawer-backdrop" onClick={e => { if (e.target === e.currentTarget) onClose() }}><div ref={panel} tabIndex={-1} className="drawer" role="dialog" aria-modal="true" aria-labelledby="explanation-title" onKeyDown={e => {
    if (e.key === 'Escape') { e.preventDefault(); onClose() }
    if (e.key === 'Tab') { const nodes = Array.from(panel.current!.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), summary, [tabindex="0"]')); const first = nodes[0]; const last = nodes[nodes.length - 1]; if (e.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) { e.preventDefault(); last?.focus() } else if (!e.shiftKey && (document.activeElement === last || document.activeElement === panel.current)) { e.preventDefault(); first?.focus() } }
  }}><div className="drawer-header"><div><span className="eyebrow">ОСНОВАНИЯ РЕКОМЕНДАЦИИ</span><h2 id="explanation-title">{r ? `Объяснение: ${r.product.sku}` : 'Объяснение товара'}</h2></div><button onClick={onClose} aria-label="Закрыть объяснение">Закрыть</button></div>
    {!data && !error && <p role="status">Загружаем объяснение…</p>}<ErrorNotice error={error} />{!!error && <button onClick={() => setRetry(n => n + 1)}>Повторить загрузку</button>}
    {data && r && <><h3>{r.product.name}</h3><p className="muted">Артикул {r.product.article} · версия {data.dataset_version}</p>{data.is_synthetic && <p className="notice compact">Синтетический пример</p>}<div className="explanation-result"><span>К заказу</span><RecommendationQuantity value={r.quantity} unit={r.product.unit} /></div><p>{r.explanation}</p><Issues issues={r.issues} />
    <h3>Из чего сложился расчёт</h3><dl className="components"><dt>Дата остатков</dt><dd>{date(r.stock_date)}</dd><dt>Источник спроса</dt><dd>{demandSources[r.demand_source]}</dd>{([
      ['daily_demand', 'Спрос в день'], ['horizon_days', 'Горизонт, дней'], ['forecast_demand', 'Прогноз спроса'], ['safety_stock', 'Страховой запас'], ['available_stock', 'Доступный остаток'], ['eligible_inbound', 'Учтённые поставки'], ['raw_need', 'Потребность до округления'], ['minimum', 'Минимальная отгрузка'], ['multiple', 'Кратность упаковки'], ['growth_factor', 'Коэффициент роста'], ['stockout_lost_demand', 'Восстановленный спрос при отсутствии товара'],
    ] as const).map(([key, label]) => <div className="definition-row" key={key}><dt>{label}</dt><dd>{quantity(r.components[key])}</dd></div>)}</dl><p className="muted">Количества — {r.product.unit ?? 'единица неизвестна'}. Минимум и кратность — отдельные ограничения. Сезонные коэффициенты в этом ответе не передаются.</p>
    <h3>История спроса</h3>{data.history?.length ? <><Suspense fallback={<p role="status">Загружаем график…</p>}><HistoryChart history={data.history} unit={r.product.unit} /></Suspense><details><summary>Данные графика таблицей</summary><div className="table-wrap"><table><thead><tr><th>Дата</th><th>Исходный</th><th>Очищенный</th><th>Скорректированный</th><th>Прогноз</th></tr></thead><tbody>{data.history.map((h, i) => <tr key={i}><td>{date(h.date)}</td><td>{quantity(h.raw)}</td><td>{quantity(h.cleaned)}</td><td>{quantity(h.adjusted)}</td><td>{quantity(h.forecast)}</td></tr>)}</tbody></table></div></details></> : <p className="muted">История не передана сервером.</p>}
    <h3>Входящие поставки</h3><p className="muted">Не каждая поставка входит в расчёт. Учтённое количество указано выше.</p>{data.inbound?.length ? data.inbound.map((inbound, i) => <div className="detail-card" key={i}><b>{date(inbound.arrival_date)}</b><p>{quantity(inbound.quantity)} {inbound.unit ?? 'единица неизвестна'}</p><small>{sourceText(inbound.source)}</small></div>) : <p className="muted">Поставки не переданы.</p>}
    <h3>Крупные покупки и аномалии</h3>{data.anomalies?.length ? data.anomalies.map((a, i) => <div className="detail-card" key={i}><b>{({ excluded: 'Исключено', recurring: 'Повторяющийся спрос', retained: 'Сохранено', review: 'Нужна проверка' })[a.decision]}</b><p>{a.document_id} · {date(a.date)} · {quantity(a.quantity)} {r.product.unit}</p><p>{a.reason}</p>{a.sources?.map((s, n) => <small key={n}>{sourceText(s)}</small>)}</div>) : <p className="muted">Решения по аномалиям не переданы.</p>}
    <h3>Допущения</h3>{data.assumptions?.length ? <ul className="plain-list">{data.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul> : <p className="muted">Допущения не переданы.</p>}
    <h3>Источники товара</h3>{r.product.sources?.length ? r.product.sources.map((s, i) => <p className="source" key={i}>{sourceText(s)}</p>) : <p className="muted">Источники не указаны.</p>}
    </>}
  </div></div>
}
