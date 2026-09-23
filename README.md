# Nomad Coders — закупки

Веб-приложение для менеджера закупа Электрокомплекта. Готов общий каркас с работающим синтетическим сценарием: API → рекомендации → черновик → правка → сохранение → согласование → CSV. **Реальный импорт Excel и прогноз ещё не реализованы** и возвращают 501. Демонстрационные количества не являются прогнозом по данным партнёра.

## Быстрый запуск на Windows

Нужны Python 3.12 и Node 22.12+. Проверено на Python 3.12.14, Node 24.19.0 и npm 10.9.0. Из корня проекта:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1 -SkipBrowser
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/seed.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/serve.ps1 -Demo
```

Откройте http://127.0.0.1:8000. Для остановки — Ctrl+C. Health: http://127.0.0.1:8000/api/health, документация API: http://127.0.0.1:8000/docs.

setup создаёт отдельную .venv, устанавливает Python-зависимости из backend/requirements.lock и frontend через npm ci. Несовместимое окружение отклоняется с сообщением. При необходимости скрипты находят подходящий bundled runtime Codex. Явный выбор: переменные NOMAD_NODE, NOMAD_NPM_CLI или аргумент setup -Python с путём к python.exe. Личные пути в Git не сохранять.

seed явно включает синтетику только для загрузки; его можно повторять без дублей. serve -Demo включает показ демонстрационных данных. Без -Demo эти данные недоступны даже в ранее заполненной базе. SQLite по умолчанию находится в runtime/nomad.sqlite3; альтернативный путь задаётся переменной окружения NOMAD_DB. Приложение читает переменные процесса, а не файл .env автоматически.

## Работа над frontend

В существующем worktree тиммейта сначала проверьте git status. Если есть свои изменения, сохраните их коммитом перед merge. Затем:

```powershell
git fetch origin
git merge origin/main
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1 -SkipBrowser
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/seed.ps1
```

Первый терминал, API на 8000:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev.ps1 -Target backend -Demo
```

Второй терминал, интерфейс на 5173 с прокси /api:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev.ps1 -Target frontend
```

Открыть http://127.0.0.1:5173. Тиммейт работает в codex/web-ui, капитан — в codex/api-integration. Полное ТЗ frontend: docs/TASK_WEB.md. Контракты и типы из frontend/src/api/generated меняет только капитан. Ветки тиммейта капитан удалённо не изменяет.

## Демонстрация за минуту

Нажмите «Получить рекомендации»: появятся 144 шт, 0 шт и строка без остатка. У последней нельзя выбрать заказ. Откройте «Почему?» для объяснения и синтетической истории. Создайте черновик, измените 144 на 0, укажите причину и сохраните. После обновления страницы ноль остаётся. Согласуйте заказ и скачайте CSV.

Черновики и все версии хранятся в SQLite. Правка и согласование создают новые версии; правка снимает согласование. Конкурирующая устаревшая версия получает 409. Экспорт доступен только для текущей согласованной версии. CSV содержит UTF-8 BOM, разделитель «;», кириллицу, нулевые значения и экранирование текстовых Excel-формул. Исходная рекомендация не перезаписывается правкой менеджера.

## Проверки и контракт

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1 -Browser
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/contracts.ps1
git diff --exit-code -- contracts/openapi.json contracts/fixtures frontend/src/api/generated
```

setup без -SkipBrowser дополнительно устанавливает Chromium. check запускает pytest, TypeScript, production-сборку Vite и по -Browser сценарий Playwright на 8009 с отдельной временной базой. Порт 8009 должен быть свободен. Проверяются скачанный CSV, обновление страницы и обслуживание собранного интерфейса через FastAPI. 22 backend-проверка и 1 сквозной браузерный сценарий прошли локально. Скриншоты и диагностика — в frontend/test-results (не в Git).

Pydantic — источник истины: contracts.ps1 воспроизводимо создаёт OpenAPI, TypeScript-типы и синтетические JSON. Эти файлы не правят вручную. Описание полей и границ адаптеров — contracts/README.md. GitHub Actions повторяет проверку схем, backend, сборку и браузерный сценарий. Первую успешную удалённую проверку нужно смотреть отдельно от локального результата.

## Архитектура и оставшаяся работа

Стек: FastAPI, Uvicorn, Pydantic, SQLite; React, TypeScript, Vite, Tailwind через официальный Vite-плагин, Recharts. pandas, NumPy и openpyxl подготовлены для импорта и расчётов. Точные установленные версии зафиксированы в backend/requirements.lock и frontend/package-lock.json.

backend/app/contracts — модели; main и api — HTTP; service — связь компонентов; storage — SQLite; export — CSV; ingestion и engine — отдельные функции будущего импорта и расчёта. Расчёт не читает файлы и базу. frontend/src/api/client.ts — общий клиент, generated — типы из OpenAPI. contracts/fixtures содержит только вымышленные примеры.

Два активных исполнителя: капитан делает весь backend и интеграцию, тиммейт — полноценный frontend. Роли: docs/TEAM.md. Далее капитану нужны импорт известных книг, нормализация, реальные сезонность/рост/выбросы/stockout и датированные поставки. Тиммейту — компоненты, редактируемые настройки, фильтры, подробные ограничения и полноценная работа с реальными данными. XLSX-экспорт и список сохранённых заказов пока отсутствуют; оболочка восстанавливает последний заказ по сохранённому в браузере идентификатору. Настройки демо фиксированы и не имитируют пересчёт.

## Данные и ограничения

Исходные файлы партнёра, SQLite, .env и окружения исключены из Git. Правила источников — docs/DATA_NOTES.md; общий план — planning.md. Расчёт не требует LLM, внешним API данные не отправляются. Автоматической отправки поставщикам и подтверждённой совместимости импорта 1С нет. Публичного сайта нет; после установки зависимостей демонстрация работает локально. Публикация кода не означает сдачу решения на платформе хакатона.
