import { useEffect, useState } from 'react'
import type { Dataset } from '../api/client'
import type { components } from '../api/generated/schema'
import { date, ErrorNotice, Issues, sourceText, suppliers } from '../components/common'

export type Settings = components['schemas']['CalculationSettings']
export const demoSettings: Settings = { as_of: '2026-09-22', lead_time_days: 14, review_days: 7, buffer_days: 7, demand_source: 'transactions' }
type Props = { datasets: Dataset[]; datasetId: string; onDataset: (id: string) => void; settings: Settings; onSettings: (settings: Settings) => void; busy: boolean; error: unknown; errorScope: string; onCalculate: () => void; onUpload: (files: File[], supplier: 'systeme' | 'iek') => void; onRefresh: () => void }
export function DataPage(p: Props) {
  const [supplier, setSupplier] = useState<'systeme' | 'iek'>('systeme')
  const [filter, setFilter] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const dataset = p.datasets.find(d => d.id === p.datasetId)
  useEffect(() => {
    if (dataset && filter && !dataset.suppliers.includes(filter as Dataset['suppliers'][number])) setFilter('')
  }, [dataset, filter])
  const invalidFiles = files.some(f => !f.name.toLowerCase().endsWith('.xlsx')) ? 'Выберите книги в формате XLSX.' : files.reduce((sum, f) => sum + f.size, 0) > 30 * 1024 * 1024 ? 'Общий размер файлов превышает 30 МиБ.' : ''
  const available = p.datasets.filter(d => !filter || d.suppliers.includes(filter as Dataset['suppliers'][number]))
  return <div className="data-layout"><section className="panel"><div className="section-heading"><div><h2>Данные для расчёта</h2><p className="muted">Выберите набор и проверьте его происхождение.</p></div><div className="header-actions"><button className="primary" disabled={p.busy || !dataset} type="submit" form="calculation-settings">{p.busy ? 'Выполняем запрос…' : 'Получить рекомендации'}</button><button disabled={p.busy} onClick={p.onRefresh}>Обновить список</button></div></div>
    <div className="form-grid"><label>Поставщик набора<select value={filter} disabled={p.busy} onChange={e => { setFilter(e.target.value); if (dataset && e.target.value && !dataset.suppliers.includes(e.target.value as Dataset['suppliers'][number])) p.onDataset('') }}><option value="">Все поставщики</option>{Object.entries(suppliers).map(([key, title]) => <option key={key} value={key}>{title}</option>)}</select></label>
    <label>Доступные наборы<select value={p.datasetId} disabled={p.busy} onChange={e => p.onDataset(e.target.value)}><option value="">Выберите набор</option>{available.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label></div>
    {dataset ? <div className="dataset-info"><span className="badge">{dataset.is_synthetic ? 'Синтетические данные' : 'Загруженные данные'}</span><dl><dt>Версия</dt><dd>{dataset.version}</dd><dt>Загружен</dt><dd>{date(dataset.created_at)}</dd><dt>Поставщики</dt><dd>{dataset.suppliers.map(s => suppliers[s]).join(', ')}</dd></dl><p className="muted">Дата загрузки не является датой остатков.</p>{(dataset.sources ?? []).map((s, i) => <p className="source" key={i}>{sourceText(s)}</p>)}<Issues issues={dataset.issues} /></div> : <div className="empty"><h3>Начните с данных</h3><p>Выберите сохранённый набор или загрузите книги Excel справа.</p></div>}
    <form id="calculation-settings" onSubmit={e => { e.preventDefault(); p.onCalculate() }}><h3>Параметры пополнения</h3>{dataset?.is_synthetic && <p className="notice compact">Фиксированный пример · настройки и демонстрационные числа не меняются.</p>}
    <fieldset disabled={p.busy || !dataset || dataset.is_synthetic}><div className="form-grid settings-grid">
      <label>Дата расчёта<input required type="date" value={p.settings.as_of} onChange={e => p.onSettings({ ...p.settings, as_of: e.target.value })} /><small>Расчёт на конец выбранного дня</small></label>
      {([['lead_time_days', 'Срок поставки', 'Дней до получения заказа', 0], ['review_days', 'Интервал пересмотра', 'Дней до следующего заказа', 1], ['buffer_days', 'Страховой запас', 'Дополнительные дни спроса', 0]] as const).map(([key, title, hint, min]) => <label key={key}>{title}<input required type="number" min={min} max={365} step={1} value={Number.isNaN(p.settings[key]) ? '' : p.settings[key]} onChange={e => p.onSettings({ ...p.settings, [key]: e.target.value === '' ? NaN : Number(e.target.value) })} /><small>{hint}</small></label>)}
      <label>Источник спроса<select value={p.settings.demand_source} onChange={e => p.onSettings({ ...p.settings, demand_source: e.target.value as Settings['demand_source'] })}><option value="transactions">Транзакции</option><option value="monthly">Месячные продажи</option></select><small>Источники не складываются</small></label>
    </div></fieldset><ErrorNotice error={p.errorScope === 'data' ? p.error : null} /><div className="action-bar"><span className="muted">Расчёт выполняется на сервере</span></div></form>
    </section><section className="panel upload-panel"><span className="eyebrow">НОВЫЙ НАБОР</span><h2>Загрузка Excel</h2><p className="muted">Книги одного поставщика. XLSX, до 30 МиБ в сумме.</p><label>Поставщик импорта<select disabled={p.busy} value={supplier} onChange={e => setSupplier(e.target.value as typeof supplier)}><option value="systeme">Systeme Electric</option><option value="iek">IEK</option></select></label>
    <label className="file-picker">Книги XLSX<input disabled={p.busy} type="file" accept=".xlsx" multiple onChange={e => { const chosen = Array.from(e.target.files ?? []); setFiles(old => [...old, ...chosen]); e.target.value = '' }} /></label>
    <ul className="file-list">{files.map((file, i) => <li key={i}><div><b>{file.name}</b><small>{(file.size / 1024 / 1024).toFixed(2)} МиБ</small></div><button disabled={p.busy} aria-label={'Удалить ' + file.name} onClick={() => setFiles(files.filter((_, n) => n !== i))}>Удалить</button></li>)}</ul>
    <ErrorNotice error={p.errorScope === 'upload' ? p.error : null} />{invalidFiles && <p className="notice error" role="alert">{invalidFiles}</p>}<button disabled={p.busy || !files.length || !!invalidFiles} onClick={() => p.onUpload(files, supplier)}>{p.busy ? 'Загружаем…' : 'Загрузить'}</button><p className="muted">Если импорт ещё не подключён, сервер сообщит об этом. Файлы не подменяются демонстрационными данными.</p></section></div>
}
