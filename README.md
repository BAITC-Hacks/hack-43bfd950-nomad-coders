# Nomad Coders — закупки

Веб-приложение для менеджера закупа Электрокомплекта. Сейчас опубликован общий каркас: FastAPI, React/TypeScript, Tailwind, Recharts, общий контракт и синтетические примеры. Реальный импорт Excel и прогноз ещё не реализованы; эти операции возвращают 501.

## Запуск на Windows

Нужны Python 3.12 и Node 22.12+; проверяемая версия Node указана в .node-version. Из корня проекта:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1 -SkipBrowser
```

Скрипт создаёт .venv, устанавливает backend по requirements.lock и frontend через npm ci. Может использовать подходящие bundled runtime Codex, если системные команды отсутствуют. Для явного выбора используйте NOMAD_NODE, NOMAD_NPM_CLI и аргумент setup -Python с путём к python.exe. Личные пути в Git не сохранять.

Первый терминал:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev.ps1 -Target backend
```

Второй терминал:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev.ps1 -Target frontend
```

Открыть http://127.0.0.1:5173. Проверка сервера: http://127.0.0.1:8000/api/health. Схема API: http://127.0.0.1:8000/docs.

## Проверка и сборка

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/contracts.ps1
```

После сборки интерфейс также доступен через backend на http://127.0.0.1:8000. contracts.ps1 обновляет OpenAPI, TypeScript-типы и синтетические JSON из Pydantic-моделей. Эту команду при изменении схем выполняет капитан.

## Архитектура и команда

backend/app/contracts — общие модели; api — HTTP; storage и export — сохранение и выгрузка; ingestion и engine — границы будущих импорта и расчёта. frontend/src/api/generated — типы из OpenAPI. contracts/fixtures — явно вымышленные примеры для независимой разработки интерфейса.

Два исполнителя: капитан делает весь backend и интеграцию, тиммейт — frontend. Подробности в docs/TEAM.md, docs/TASK_WEB.md и docs/TASK_DATA.md. Основной план — planning.md, ограничения данных — docs/DATA_NOTES.md.

## Данные и ограничения

Исходные файлы партнёра, SQLite, .env и окружения в Git не входят. Расчёт не требует LLM, внешние API не используются. Автоматической отправки поставщикам и подтверждённой совместимости импорта 1С нет. Локальная демонстрация — основной вариант, публичного сайта нет. Синтетические количества не являются прогнозом по данным партнёра.
