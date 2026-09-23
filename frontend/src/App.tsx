import { useEffect, useState } from 'react'
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, ApiError, type Dataset, type Calculation, type Explanation, type Order } from './api/client'

type View = 'data' | 'recommendations' | 'order'
const quantity = (value: number | null | undefined) => value == null ? 'Нет данных' : value.toLocaleString('ru-RU')
const statuses = { order_now: 'Заказать', expedite: 'Срочно', covered: 'Запас достаточен', needs_input: 'Нужны данные' }

export default function App() {
  const [view, setView] = useState<View>('data')
  const [connected, setConnected] = useState(false)
  const [demo, setDemo] = useState(false)
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [datasetId, setDatasetId] = useState('')
  const [calculation, setCalculation] = useState<Calculation | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [explanation, setExplanation] = useState<Explanation | null>(null)
  const [order, setOrder] = useState<Order | null>(null)
  const [edits, setEdits] = useState<Record<string, { quantity: string; reason: string }>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [supplier, setSupplier] = useState<'systeme' | 'iek'>('systeme')
  const [files, setFiles] = useState<File[]>([])

  async function run(action: () => Promise<void>) {
    setBusy(true); setError('')
    try { await action() }
    catch (e) {
      setError(e instanceof ApiError ? e.message + (e.details.length ? ': ' + e.details.map(d => d.message).join('; ') : '')
        : e instanceof Error ? e.message : 'Не удалось выполнить действие')
    } finally { setBusy(false) }
  }
  function acceptOrder(next: Order) {
    setOrder(next); setEdits({})
    localStorage.setItem('nomad-order', next.id)
  }
  useEffect(() => {
    void run(async () => {
      const health = await api.health(); setConnected(true); setDemo(health.demo_enabled)
      const list = await api.datasets(); setDatasets(list); setDatasetId(list[0]?.id ?? '')
      const saved = localStorage.getItem('nomad-order')
      if (saved) {
        try { acceptOrder(await api.order(saved)); setView('order') }
        catch (e) { if (e instanceof ApiError && e.status === 404) localStorage.removeItem('nomad-order'); else throw e }
      }
    })
  }, [])
  const dirty = Object.keys(edits).length > 0
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = '' }
    if (dirty) window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  const dataset = datasets.find(d => d.id === datasetId)
  const dirtyEdit = (id: string, field: 'quantity' | 'reason', value: string) => {
    const line = order!.lines.find(l => l.recommendation_id === id)!
    setEdits(current => ({ ...current, [id]: { ...(current[id] ?? { quantity: String(line.quantity), reason: line.override_reason ?? '' }), [field]: value } }))
  }

  return <div className="app"><header><b>NOMAD / ЗАКУПКИ</b><span>{connected ? 'Сервер подключён' : 'Соединение с сервером…'}</span></header>
    <main><p className="eyebrow">ЭЛЕКТРОКОМПЛЕКТ · РАБОЧЕЕ МЕСТО ЗАКУПЩИКА</p>
      <h1>Пополнение склада</h1><p className="muted">От данных о спросе к проверенному заказу поставщику.</p>
      {demo && <div className="notice" role="note"><b>Демонстрационный режим · синтетические данные.</b> Готовые числа проверяют работу приложения. Реальный импорт и прогноз ещё не подключены.</div>}
      <nav aria-label="Этапы заказа">
        <button disabled={dirty || busy} className={view === 'data' ? 'active' : ''} onClick={() => setView('data')}>1. Данные и настройки</button>
        <button disabled={!calculation || dirty || busy} className={view === 'recommendations' ? 'active' : ''} onClick={() => setView('recommendations')}>2. Рекомендации</button>
        <button disabled={!order} className={view === 'order' ? 'active' : ''} onClick={() => setView('order')}>3. Проверка заказа</button>
      </nav>
      {error && <div className="notice error" role="alert">{error}</div>}
      {busy && <p role="status">Загрузка…</p>}
      {view === 'data' && <>
        <section className="panel"><h2>Набор данных</h2>
          <div className="toolbar"><label>Доступные наборы<select value={datasetId} onChange={e => setDatasetId(e.target.value)}>
            {!datasets.length && <option value="">Наборов пока нет</option>}
            {datasets.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select></label>
          <button className="primary" disabled={busy || !datasetId} onClick={() => void run(async () => {
            const result = await api.calculate({ dataset_id: datasetId, settings: { as_of: '2026-09-22', lead_time_days: 14, review_days: 7, buffer_days: 7, demand_source: 'transactions' } })
            setCalculation(result); setSelected(result.recommendations.filter(r => r.quantity != null && r.product.unit && !(r.issues ?? []).some(i => i.severity === 'blocking')).map(r => r.id))
            setExplanation(null); setView('recommendations')
          })}>Получить рекомендации</button></div>
          {dataset && <p className="muted">Версия: {dataset.version}. Источник: {(dataset.sources ?? []).map(s => s.file).join(', ')}.</p>}
          <div className="metrics">{[['Дата расчёта', '22.09.2026'], ['Срок поставки', '14 дней'], ['Пересмотр', '7 дней'], ['Буфер', '7 дней']].map(([label, value]) =>
            <div className="metric" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
          <p className="muted">В каркасе параметры фиксированы для демонстрационного примера. Изменяемые настройки подключаются вместе с реальным расчётом.</p>
          {!datasets.length && demo && <p>Загрузите синтетический набор командой из README, затем обновите страницу.</p>}
        </section>
        <section className="panel"><h2>Загрузка Excel</h2><p className="muted">Точка подключения подготовлена. Пока импорт возвращает сообщение «ещё не реализован».</p>
          <div className="toolbar"><label>Поставщик<select value={supplier} onChange={e => setSupplier(e.target.value as typeof supplier)}><option value="systeme">Systeme Electric</option><option value="iek">IEK</option></select></label>
            <label>Книги XLSX<input type="file" accept=".xlsx" multiple onChange={e => setFiles(Array.from(e.target.files ?? []))} /></label>
            <button disabled={busy || !files.length} onClick={() => void run(async () => {
              const imported = await api.upload(files, supplier); setDatasets(await api.datasets()); setDatasetId(imported.id)
            })}>Загрузить</button></div></section>
      </>}
      {view === 'recommendations' && calculation && <>
        <section className="panel"><div className="split"><h2>Рекомендации к заказу</h2><span className="badge">{calculation.recommendations.length} товара</span></div>
          <p className="muted">Ноль — запас достаточен. «Нет данных» — расчёт невозможен, строку нельзя добавить в заказ.</p>
          <div className="table-wrap"><table><thead><tr><th>Выбор</th><th>Товар / артикул</th><th>Остаток</th><th>Рекомендация</th><th>Статус</th><th>Расчёт</th></tr></thead><tbody>
            {calculation.recommendations.map(r => <tr key={r.id}>
              <td><input aria-label={'Выбрать ' + r.product.sku} type="checkbox" checked={selected.includes(r.id)} disabled={r.quantity == null || !r.product.unit || (r.issues ?? []).some(i => i.severity === 'blocking')}
                onChange={e => setSelected(s => e.target.checked ? [...s, r.id] : s.filter(id => id !== r.id))} /></td>
              <td>{r.product.name}<small>{r.product.sku} · {r.product.article}</small></td>
              <td>{quantity(r.components.available_stock)}</td><td><b>{quantity(r.quantity)}</b> {r.quantity != null && r.product.unit}</td>
              <td><span className={'badge' + (r.urgency === 'needs_input' ? ' warning' : '')}>{statuses[r.urgency]}</span></td>
              <td><button aria-label={'Объяснение ' + r.product.sku} disabled={busy} onClick={() => void run(async () => setExplanation(await api.explanation(calculation.id, r.id)))}>Почему?</button></td>
            </tr>)}</tbody></table></div>
          <div className="toolbar"><button className="primary" disabled={busy || !selected.length} onClick={() => void run(async () => {
            const first = calculation.recommendations.find(r => selected.includes(r.id))!
            if (calculation.recommendations.some(r => selected.includes(r.id) && r.product.supplier !== first.product.supplier)) throw new Error('Выберите товары одного поставщика')
            acceptOrder(await api.createOrder({ calculation_id: calculation.id, supplier: first.product.supplier, recommendation_ids: selected }))
            setView('order')
          })}>Создать черновик</button><span className="muted">Выбрано: {selected.length}</span></div>
        </section>
        {explanation && <section className="panel"><h2>Объяснение: {explanation.recommendation.product.sku}</h2>
          <p>{explanation.recommendation.explanation}</p>
          {(explanation.recommendation.issues ?? []).map((i, n) => <p className="notice" key={n}>{i.message}</p>)}
          <p className="muted">Искусственная месячная история, единицы товара</p>
          <div className="chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={explanation.history}>
            <XAxis dataKey="date" /><YAxis /><Tooltip /><Line dataKey="raw" name="Наблюдения" stroke="#0f766e" strokeWidth={2} isAnimationActive={false} />
          </LineChart></ResponsiveContainer></div>
          {(explanation.assumptions ?? []).map(a => <p key={a} className="muted">{a}</p>)}</section>}
      </>}
      {view === 'order' && order && <section className="panel"><div className="split"><h2>Проверка заказа</h2><span className="badge">{order.status === 'approved' ? 'Согласован' : 'Черновик'} · версия {order.revision}</span></div>
        <p className="muted">Поставщик: {order.supplier}. Правка сохраняется отдельно от исходной рекомендации и требует повторного согласования.</p>
        <div className="table-wrap"><table><thead><tr><th>Товар</th><th>Рекомендовано</th><th>В заказе</th><th>Причина правки</th></tr></thead><tbody>
          {order.lines.map(line => <tr key={line.recommendation_id}><td>{line.product.name}<small>{line.product.sku} · {line.product.unit}</small></td>
            <td>{quantity(line.recommended_quantity)}</td><td><input className="order-input" aria-label={'Количество ' + line.product.sku} type="number" min="0" step="any" disabled={busy}
              value={edits[line.recommendation_id]?.quantity ?? String(line.quantity)} onChange={e => dirtyEdit(line.recommendation_id, 'quantity', e.target.value)} /></td>
            <td><input className="reason-input" aria-label={'Причина ' + line.product.sku} disabled={busy} value={edits[line.recommendation_id]?.reason ?? line.override_reason ?? ''}
              onChange={e => dirtyEdit(line.recommendation_id, 'reason', e.target.value)} placeholder="Обязательна при изменении" /></td></tr>)}
        </tbody></table></div>
        {dirty && <p className="notice">Есть несохранённые изменения. Сначала сохраните правки.</p>}
        <div className="toolbar">
          <button disabled={busy || !dirty} onClick={() => void run(async () => {
            const overrides = Object.entries(edits).map(([recommendation_id, edit]) => {
              if (!edit.quantity.trim() || !Number.isFinite(Number(edit.quantity)) || Number(edit.quantity) < 0 || !edit.reason.trim()) throw new Error('Укажите неотрицательное количество и причину каждой правки')
              return { recommendation_id, quantity: Number(edit.quantity), reason: edit.reason.trim() }
            })
            acceptOrder(await api.patchOrder(order.id, { expected_revision: order.revision, overrides }))
          })}>Сохранить правки</button>
          <button disabled={busy || dirty} onClick={() => void run(async () => acceptOrder(await api.order(order.id)))}>Загрузить сохранённый заказ</button>
          {dirty && <button disabled={busy} onClick={() => setEdits({})}>Отменить несохранённые правки</button>}
          <button className="primary" disabled={busy || dirty || order.status === 'approved'} onClick={() => void run(async () => acceptOrder(await api.approve(order.id, order.revision)))}>Согласовать заказ</button>
          {order.status === 'approved' && !dirty && <a className="button primary" href={api.exportUrl(order)}>Скачать CSV</a>}
        </div><p className="muted">CSV — локальная выгрузка, заказ поставщику не отправляется. Согласование фиксирует проверенную вами версию.</p>
      </section>}
      <footer>Nomad Coders · Каркас для HackAlem · Данные партнёра остаются на вашем компьютере</footer>
    </main></div>
}
