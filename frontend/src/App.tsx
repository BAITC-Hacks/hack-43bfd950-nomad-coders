import { useEffect, useState } from 'react'

export default function App() {
  const [status, setStatus] = useState('Проверяем соединение…')
  useEffect(() => {
    fetch('/api/health').then(r => { if (!r.ok) throw new Error(); return r.json() })
      .then(() => setStatus('Сервер подключён'))
      .catch(() => setStatus('Сервер недоступен. Запустите backend.'))
  }, [])
  return <div className="app"><header><b>NOMAD / ЗАКУПКИ</b><span>{status}</span></header>
    <main><p className="eyebrow">ЭЛЕКТРОКОМПЛЕКТ · РАБОЧЕЕ МЕСТО ЗАКУПЩИКА</p>
      <h1>Пополнение склада</h1><p>Общий каркас готов к подключению данных и интерфейса.</p>
      <nav><button>Данные и настройки</button><button>Рекомендации</button><button>Проверка заказа</button></nav>
      <section className="panel"><h2>Начните с данных</h2><p>Реальный импорт и прогноз ещё не подключены. Демонстрационный сценарий будет отмечен отдельно.</p></section>
    </main></div>
}
