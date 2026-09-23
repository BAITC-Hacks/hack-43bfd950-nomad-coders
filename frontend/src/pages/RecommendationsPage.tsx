import { useMemo, useState } from 'react'
import type { Calculation, Recommendation } from '../api/client'
import { canSelect, date, ErrorNotice, Issues, quantity, RecommendationQuantity, statuses, suppliers } from '../components/common'

type Props = { calculation: Calculation; selected: string[]; onSelected: (ids: string[]) => void; onExplain: (id: string) => void; activeId?: string; onCreate: () => void; busy: boolean; error: unknown; stale: boolean; onData: () => void }
export function RecommendationsPage(p: Props) {
  const [filters, setFilters] = useState({ search: '', supplier: '', category: '', urgency: '', issue: '', sort: 'quantity_desc' })
  const [page, setPage] = useState(0)
  const [size, setSize] = useState(50)
  const rows = p.calculation.recommendations
  function filter(key: keyof typeof filters, value: string) { setFilters(f => ({ ...f, [key]: value })); setPage(0) }
  const filtered = useMemo(() => rows.filter(r => {
    const search = filters.search.trim().toLocaleLowerCase('ru')
    return [r.product.name, r.product.sku, r.product.article].some(v => v.toLocaleLowerCase('ru').includes(search)) && (!filters.supplier || r.product.supplier === filters.supplier) && (!filters.category || (r.product.category ?? '__unknown') === filters.category) && (!filters.urgency || r.urgency === filters.urgency) && (!filters.issue || (filters.issue === 'blocking' ? (r.issues ?? []).some(i => i.severity === 'blocking') : (r.issues ?? []).length > 0))
  }).sort((a, b) => {
    if (filters.sort === 'status') return statuses[a.urgency].localeCompare(statuses[b.urgency], 'ru')
    if (a.quantity == null) return b.quantity == null ? 0 : 1
    if (b.quantity == null) return -1
    return (a.quantity - b.quantity) * (filters.sort === 'quantity_asc' ? 1 : -1)
  }), [rows, filters])
  const maxPage = Math.max(0, Math.ceil(filtered.length / size) - 1)
  const currentPage = Math.min(page, maxPage)
  const visible = filtered.slice(currentPage * size, (currentPage + 1) * size)
  const selectedRows = rows.filter(r => p.selected.includes(r.id))
  const supplier = selectedRows[0]?.product.supplier
  const mixed = new Set(selectedRows.map(r => r.product.supplier)).size > 1
  const hidden = selectedRows.filter(r => !visible.some(v => v.id === r.id)).length
  const allowed = (r: Recommendation) => canSelect(r) && (!supplier || r.product.supplier === supplier)
  const pageEligible = visible.filter(allowed)
  const allChecked = pageEligible.length > 0 && pageEligible.every(r => p.selected.includes(r.id))
  return <section className="panel recommendations-panel">
    <div className="section-heading"><div><h2>Рекомендации к заказу</h2><p className="muted">Версия данных {p.calculation.dataset_version} · расчёт на {date(p.calculation.settings.as_of)}{p.calculation.is_synthetic && ' · синтетические данные'}</p></div><div className="header-actions"><button className="primary" disabled={p.busy || p.stale || !p.selected.length || mixed} onClick={p.onCreate}>{p.busy ? 'Создаём…' : 'Создать черновик'}</button><button disabled={p.busy} onClick={p.onData}>Изменить параметры</button></div></div>
    {p.stale && <div className="notice warning" role="status">Данные или настройки изменены. Эти рекомендации неактуальны. Вернитесь к настройкам и выполните новый расчёт.</div>}
    <div className="summary-strip"><div><strong>{rows.filter(r => r.quantity != null && r.quantity > 0).length}</strong><span>Требуют заказа</span></div><div><strong>{rows.filter(r => r.quantity === 0).length}</strong><span>Без потребности</span></div><div><strong>{rows.filter(r => r.quantity == null).length}</strong><span>Нужны данные</span></div><div><strong>{rows.length}</strong><span>Всего товаров</span></div></div>
    <div className="filters"><label className="search">Поиск<input type="search" placeholder="Название, SKU или артикул" value={filters.search} onChange={e => filter('search', e.target.value)} /></label>
      <label>Поставщик<select value={filters.supplier} onChange={e => filter('supplier', e.target.value)}><option value="">Все поставщики</option>{Array.from(new Set(rows.map(r => r.product.supplier))).map(s => <option key={s} value={s}>{suppliers[s]}</option>)}</select></label>
      <label>Категория<select value={filters.category} onChange={e => filter('category', e.target.value)}><option value="">Все категории</option>{Array.from(new Set(rows.map(r => r.product.category))).map(c => <option key={c ?? '__unknown'} value={c ?? '__unknown'}>{c == null ? 'Не указана' : `Код ${c}`}</option>)}</select></label>
      <label>Срочность<select value={filters.urgency} onChange={e => filter('urgency', e.target.value)}><option value="">Любая</option>{Object.entries(statuses).map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select></label>
      <label>Проблемы данных<select value={filters.issue} onChange={e => filter('issue', e.target.value)}><option value="">Все строки</option><option value="any">Есть проблемы</option><option value="blocking">Блокируют заказ</option></select></label>
      <label>Сортировка<select value={filters.sort} onChange={e => filter('sort', e.target.value)}><option value="quantity_desc">Количество ↓</option><option value="quantity_asc">Количество ↑</option><option value="status">По статусу</option></select></label>
      <button onClick={() => { setFilters({ search: '', supplier: '', category: '', urgency: '', issue: '', sort: 'quantity_desc' }); setPage(0) }}>Сбросить фильтры</button></div>
    <Issues issues={p.calculation.issues} />
    <div className="table-wrap" tabIndex={0} role="region" aria-label="Таблица рекомендаций"><table><thead><tr><th><input type="checkbox" aria-label="Выбрать все на текущей странице" disabled={p.busy || p.stale || !pageEligible.length} checked={allChecked} onChange={e => {
      if (!e.target.checked) p.onSelected(p.selected.filter(id => !pageEligible.some(r => r.id === id)))
      else { const firstSupplier = supplier ?? pageEligible[0]?.product.supplier; p.onSelected([...new Set([...p.selected, ...pageEligible.filter(r => r.product.supplier === firstSupplier).map(r => r.id)])]) }
    }} /></th><th>Товар / SKU / артикул</th><th>Ед. / категория</th><th className="numeric">Доступный остаток</th><th className="numeric">Рекомендация</th><th>Срочность / проблемы</th><th>Объяснение</th></tr></thead><tbody>
      {visible.map(r => <tr key={r.id} className={p.activeId === r.id ? 'explained' : p.selected.includes(r.id) ? 'selected' : ''}>
        <td><input type="checkbox" aria-label={'Выбрать ' + r.product.sku} checked={p.selected.includes(r.id)} disabled={p.busy || p.stale || (!p.selected.includes(r.id) && !allowed(r)) || !canSelect(r)} onChange={e => p.onSelected(e.target.checked ? [...p.selected, r.id] : p.selected.filter(id => id !== r.id))} /></td>
        <td className="product-cell"><b>{r.product.name}</b><small>{r.product.sku} · {r.product.article}</small><small>{suppliers[r.product.supplier]}</small></td><td>{r.product.unit ?? 'Единица неизвестна'}<small>{r.product.category == null ? 'Категория не указана' : `Код ${r.product.category}`}</small></td>
        <td className="numeric">{quantity(r.components.available_stock)}<small>{date(r.stock_date)}</small></td><td className="numeric"><RecommendationQuantity value={r.quantity} unit={r.product.unit} /></td>
        <td><span className={'badge' + (r.urgency === 'needs_input' || r.urgency === 'expedite' ? ' warning' : '')}>{statuses[r.urgency]}</span>{!!r.issues?.length && <small className="issue-label">Проблем: {r.issues.length}{r.issues.some(i => i.severity === 'blocking') ? ' · заказ заблокирован' : ''}</small>}{!r.product.unit && <small>Заказ заблокирован: неизвестная единица</small>}</td><td><button aria-label={'Объяснение ' + r.product.sku} onClick={() => p.onExplain(r.id)}>Почему?</button></td>
      </tr>)}
    </tbody></table>{!visible.length && <div className="empty"><h3>Товары не найдены</h3><p>Измените запрос или сбросьте фильтры. Выбранные товары сохранены.</p></div>}</div>
    <div className="pagination"><span>Найдено: {filtered.length} · страница {currentPage + 1} из {maxPage + 1}</span><label>Строк на странице<select value={size} onChange={e => { setSize(Number(e.target.value)); setPage(0) }}><option>50</option><option>100</option></select></label><button disabled={!currentPage} onClick={() => setPage(currentPage - 1)}>Назад</button><button disabled={currentPage >= maxPage} onClick={() => setPage(currentPage + 1)}>Далее</button></div>
    <ErrorNotice error={p.error} /><div className="action-bar"><span>Выбрано: {p.selected.length}{hidden > 0 && ` · вне текущей страницы: ${hidden}`}</span>{p.selected.length > 0 && <button disabled={p.busy} onClick={() => p.onSelected([])}>Очистить выбор</button>}</div><p className="muted">Один заказ — один поставщик. «Выбрать все» выбирает доступные товары одного поставщика на текущей странице.{supplier && ` Сейчас выбран: ${suppliers[supplier]}.`}</p>
  </section>
}
