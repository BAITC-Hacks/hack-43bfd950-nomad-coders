import { useEffect, useRef, useState } from 'react'
import { api, ApiError, type Dataset, type Calculation, type Order } from './api/client'
import { DataPage, demoSettings, type Settings } from './pages/DataPage'
import { RecommendationsPage } from './pages/RecommendationsPage'
import { OrderPage, type Edits } from './pages/OrderPage'
import { ExplanationPanel } from './components/ExplanationPanel'
import { canSelect, ErrorNotice } from './components/common'

type View = 'data' | 'recommendations' | 'order'
const titles = { data: 'Данные и настройки', recommendations: 'Рекомендации', order: 'Проверка заказа' }
export default function App() {
  const [view, setView] = useState<View>('data')
  const [connected, setConnected] = useState(false)
  const [demo, setDemo] = useState(false)
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [datasetId, setDatasetId] = useState('')
  const [settings, setSettings] = useState<Settings>(demoSettings)
  const [calculation, setCalculation] = useState<Calculation | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [explanationId, setExplanationId] = useState<string>()
  const [order, setOrder] = useState<Order | null>(null)
  const [edits, setEdits] = useState<Edits>({})
  const [busy, setBusy] = useState(false)
  const [initializing, setInitializing] = useState(true)
  const [error, setError] = useState<unknown>(null)
  const lock = useRef(false)
  const initialized = useRef(false)
  const [errorScope, setErrorScope] = useState('data')
  const dirty = Object.keys(edits).length > 0
  const stale = !!calculation && (calculation.dataset_id !== datasetId || JSON.stringify(calculation.settings) !== JSON.stringify(settings))

  async function run(action: () => Promise<void>) {
    if (lock.current) return
    lock.current = true; setBusy(true); setError(null)
    try { await action() } catch (e) { setError(e) }
    finally { lock.current = false; setBusy(false) }
  }
  function acceptOrder(next: Order) { setOrder(next); setEdits({}); localStorage.setItem('nomad-order', next.id) }
  function acceptCalculation(result: Calculation) {
    setCalculation(result); setDatasetId(result.dataset_id); setSettings(result.settings)
    const eligible = result.recommendations.filter(canSelect)
    setSelected(eligible.filter(r => r.product.supplier === eligible[0]?.product.supplier).map(r => r.id))
    setExplanationId(undefined)
    localStorage.setItem('nomad-calculation', result.id)
  }
  async function initialize() {
    setInitializing(true)
    await run(async () => {
      const health = await api.health(); setConnected(true); setDemo(health.demo_enabled)
      const list = await api.datasets(); setDatasets(list); setDatasetId(list[0]?.id ?? '')
      const savedOrder = localStorage.getItem('nomad-order')
      const savedCalculation = localStorage.getItem('nomad-calculation')
      if (savedOrder) {
        let restored: Order | null = null
        try { restored = await api.order(savedOrder) }
        catch (e) { if (e instanceof ApiError && e.status === 404) localStorage.removeItem('nomad-order'); else throw e }
        if (restored) { acceptOrder(restored); setView('order'); acceptCalculation(await api.calculation(restored.calculation_id)); return }
      }
      if (savedCalculation) {
        try { acceptCalculation(await api.calculation(savedCalculation)); setView('recommendations') }
        catch (e) { if (e instanceof ApiError && e.status === 404) localStorage.removeItem('nomad-calculation'); else throw e }
      }
    })
    setInitializing(false)
  }
  useEffect(() => { if (!initialized.current) { initialized.current = true; void initialize() } }, [])
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = '' }
    if (dirty) window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  function navigate(next: View) {
    if (dirty || busy) return
    setError(null); setExplanationId(undefined)
    if (next === 'order' && order && order.calculation_id !== calculation?.id) { void run(async () => { acceptCalculation(await api.calculation(order.calculation_id)); setView(next) }); return }
    setView(next)
  }
  function dirtyEdit(id: string, field: 'quantity' | 'reason', value: string) {
    const line = order!.lines.find(l => l.recommendation_id === id)!
    setEdits(current => {
      const edit = { ...(current[id] ?? { quantity: String(line.quantity), reason: line.override_reason ?? '' }), [field]: value }
      const next = { ...current, [id]: edit }
      if (edit.quantity === String(line.quantity) && edit.reason === (line.override_reason ?? '')) delete next[id]
      return next
    })
  }
  const activeDemo = (view === 'order' ? order?.is_synthetic : view === 'recommendations' ? calculation?.is_synthetic : datasets.find(d => d.id === datasetId)?.is_synthetic) ?? false
  return <div className="app"><header className="app-header"><div className="brand"><span className="brand-mark" aria-hidden="true">N</span><b>NOMAD <span>/ ЗАКУПКИ</span></b></div><div className="header-status">{demo && <span className="badge">Демо доступно</span>}<span>{connected ? 'Сервер подключён' : error ? 'Сервер недоступен' : 'Подключение…'}</span></div></header>
    <main><div className="page-heading"><div><p className="eyebrow">ЭЛЕКТРОКОМПЛЕКТ · ПОПОЛНЕНИЕ СКЛАДА</p><h1>{titles[view]}</h1></div><span className="muted">Рабочее место закупщика</span></div>
      {activeDemo && <div className="demo-note" role="note"><b>Демонстрационный режим · синтетические данные.</b> Фиксированные числа проверяют сценарий заказа.</div>}
      <nav className="steps" aria-label="Этапы заказа">{(['data', 'recommendations', 'order'] as const).map((key, i) => <button key={key} aria-current={view === key ? 'step' : undefined} disabled={dirty || busy || (key === 'recommendations' && !calculation) || (key === 'order' && !order)} className={view === key ? 'active' : ''} onClick={() => navigate(key)}>{i + 1}. {titles[key]}</button>)}</nav>
      {initializing ? <section className="panel" role="status">Загружаем сохранённые данные…</section> : !connected ? <section className="panel"><ErrorNotice error={error} /><button className="primary" onClick={() => void initialize()}>Повторить подключение</button></section> : <>
      {view === 'data' && <DataPage datasets={datasets} datasetId={datasetId} settings={settings} busy={busy} error={error} errorScope={errorScope} onDataset={id => { setDatasetId(id); if (id !== datasetId) setSettings(demoSettings); setError(null) }} onSettings={setSettings}
        onRefresh={() => { setErrorScope('data'); void run(async () => setDatasets(await api.datasets())) }}
        onCalculate={() => { setErrorScope('data'); void run(async () => { const result = await api.calculate({ dataset_id: datasetId, settings }); acceptCalculation(result); setView('recommendations') }) }}
        onUpload={(files, supplier) => { setErrorScope('upload'); void run(async () => { const imported = await api.upload(files, supplier); setDatasets(await api.datasets()); setDatasetId(imported.id); setSettings(demoSettings) }) }} />}
      {view === 'recommendations' && calculation && <RecommendationsPage calculation={calculation} selected={selected} onSelected={setSelected} activeId={explanationId} onExplain={setExplanationId} onData={() => navigate('data')} stale={stale} busy={busy} error={error} onCreate={() => void run(async () => {
        const first = calculation.recommendations.find(r => selected.includes(r.id))!
        if (calculation.recommendations.some(r => selected.includes(r.id) && r.product.supplier !== first.product.supplier)) throw new Error('Выберите товары одного поставщика')
        acceptOrder(await api.createOrder({ calculation_id: calculation.id, supplier: first.product.supplier, recommendation_ids: selected })); setView('order')
      })} />}
      {view === 'order' && order && <OrderPage order={order} calculation={calculation} edits={edits} onEdit={dirtyEdit} busy={busy} error={error} onDiscard={() => { setEdits({}); setError(null) }} onReload={() => void run(async () => acceptOrder(await api.order(order.id)))} onApprove={() => void run(async () => acceptOrder(await api.approve(order.id, order.revision)))} onExport={() => void run(async () => api.downloadOrder(order))} onSave={() => void run(async () => {
        const overrides = Object.entries(edits).map(([recommendation_id, edit]) => {
          if (!edit.quantity.trim() || !Number.isFinite(Number(edit.quantity)) || Number(edit.quantity) < 0 || !edit.reason.trim()) throw new Error('Укажите неотрицательное количество и причину каждой правки')
          return { recommendation_id, quantity: Number(edit.quantity), reason: edit.reason.trim() }
        })
        acceptOrder(await api.patchOrder(order.id, { expected_revision: order.revision, overrides }))
      })} />}
      </>}
      <footer><span>Nomad Coders</span><span>Решение о заказе остаётся за менеджером</span></footer>
    </main>{explanationId && calculation && <ExplanationPanel calculationId={calculation.id} itemId={explanationId} onClose={() => setExplanationId(undefined)} />}
  </div>
}
