# Самостоятельный запуск и развёртывание Nomad Coders

Инструкция предназначена для комиссии или администратора, получившего доступ к исходникам. **Подключение к компьютеру или Docker команды не требуется.** Приложение можно проверить локально либо разместить в собственном облачном окружении. Создание командой постоянного публичного сервиса не входит в текущий объём сдачи.

Проверены Linux Docker-сборка, локальная PostgreSQL, версии заказов, сохранение после рестарта и сценарий HTTP/браузер → расчёт → правка → согласование → CSV. Ниже описан способ облачного размещения; успешный деплой в конкретном аккаунте проверяется отдельно.

## 1. Быстрая локальная проверка через Docker

Нужны Git, доступ к приватному репозиторию и работающий Docker с Linux-контейнерами. Python и Node на компьютере не требуются. Выполните в новой папке:

```powershell
git clone https://github.com/BAITC-Hacks/hack-43bfd950-nomad-coders.git nomad-coders-review
cd nomad-coders-review
git switch main
docker build -t nomad-coders:demo .
docker run -d --name nomad-review -p 127.0.0.1:8080:8000 -e NOMAD_DEMO=1 --mount type=volume,source=nomad-review-data,target=/app/runtime nomad-coders:demo
```

Откройте **http://127.0.0.1:8080**. Два синтетических набора добавляются автоматически. Выберите «Расчёт закупки · синтетические наблюдения» и пройдите [сценарий проверки](TEST_DRIVE.md). SQLite хранится в volume `nomad-review-data`; повторное создание данных при старте не стирает заказы.

```powershell
docker logs nomad-review
docker stop nomad-review
docker start nomad-review
```

Не выполняйте `docker run` повторно с тем же именем: для существующего контейнера используйте `docker start`. Если порт 8080 занят, измените только левую часть публикации порта, например на `127.0.0.1:8081:8000`, и откройте 8081. Не удаляйте volume, если нужно сохранить заказы.

## 2. Подготовить базу для облака

Для независимой HTTPS-ссылки можно использовать **Render Free + Neon Free**. На бесплатном Render локальная файловая система временная, поэтому заказы следует хранить в PostgreSQL, а не в SQLite внутри контейнера.

В своём аккаунте Neon создайте проект Free, например `nomad-coders`, в регионе Frankfurt. Откройте **Connect**, выберите базу проекта, включите Connection pooling и скопируйте строку подключения с `sslmode=require`. Нужна строка `postgresql://…`, без команды `psql` и окружающих кавычек.

Строку впоследствии вводят только в секрет `DATABASE_URL` на Render. Не включайте её в Git, Dockerfile или frontend. Адрес `host.docker.internal` применяется для локальных проверок и не подходит для облачной базы.

## 3. Выбрать источник приложения для Render

Используйте один из двух вариантов. Создавать оба сервиса не требуется.

### Вариант A — GitHub

Render → **New → Web Service → Git Provider → GitHub**. Выберите репозиторий `BAITC-Hacks/hack-43bfd950-nomad-coders` и ветку `main`.

Для приватного репозитория организации может потребоваться одобрение её владельца на доступ приложения Render. Не меняйте видимость репозитория и не предоставляйте доступ ко всем репозиториям. Если разрешения нет, используйте вариант B.

Настройки сборки: Language **Docker**, Root Directory пустой, Dockerfile Path **`./Dockerfile`**. Build/Start Command оставьте по Dockerfile. Затем перейдите к общим настройкам ниже.

Готовый `render.yaml` позволяет выполнить тот же сценарий через Render Blueprint: он фиксирует Free и отдельно запрашивает `DATABASE_URL`. Это альтернатива ручному созданию сервиса.

### Вариант B — готовый приватный Docker-образ

Этот вариант не требует доступа Render к GitHub. Создайте личный Docker Hub-репозиторий **`nomad-coders` с видимостью Private**. У бесплатного Docker Personal доступен один приватный репозиторий. Если лимит уже занят, не переводите чужой или существующий приватный код в публичный доступ.

Из корня исходников, заменив `YOUR_DOCKER_ID` своим Docker ID:

```powershell
docker login
docker build --platform linux/amd64 -t YOUR_DOCKER_ID/nomad-coders:hackalem-v1 .
docker push YOUR_DOCKER_ID/nomad-coders:hackalem-v1
```

Завершите вход `docker login` в браузере. Для Render создайте отдельный Docker Personal Access Token с правом **Read** и сроком действия, покрывающим период проверки. Токен вводится непосредственно в Render; токен Read не подходит для отправки образа через `docker push`.

В Render: **New → Web Service → Existing Image**. Image URL: `docker.io/YOUR_DOCKER_ID/nomad-coders:hackalem-v1`. Выберите **Add credential**: Registry Docker Hub, Username ваш Docker ID, Personal Access Token — токен Read. После проверки доступа нажмите **Connect**. Docker Command оставьте пустым: команда запуска уже есть в образе.

## 4. Общие настройки сервиса

| Поле | Значение |
| --- | --- |
| Name | `nomad-coders` или свободное имя |
| Region | Frankfurt, желательно рядом с базой |
| Instance Type | **Free** |
| Health Check Path | `/api/health` |
| Environment: `DATABASE_URL` | Строка PostgreSQL из Neon |
| Environment: `NOMAD_DEMO` | `1` |
| Environment: `NOMAD_PUBLIC_DEMO` | `1` |

Нажмите **Deploy Web Service**, дождитесь **Live** и откройте выданный адрес `https://ИМЯ.onrender.com`. Dockerfile собирает React на Node 24, запускает Python 3.12 от непривилегированного пользователя, слушает `0.0.0.0` и порт из `PORT`. Дополнительная команда запуска не нужна.

Сервис работает на хостинге: компьютер, с которого выполнена настройка, можно выключить. Не удаляйте сервис, базу, образ или токен до завершения проверки.

## 5. Проверить развёрнутую версию

Пройдите сценарий [docs/TEST_DRIVE.md](TEST_DRIVE.md). Дополнительно проверьте:

- `/api/health` возвращает JSON с `status: ok`, `demo_enabled: true`, `public_demo: true`.
- Главная страница и обновление вложенного адреса открывают интерфейс, неизвестный `/api/…` возвращает JSON-404.
- Настройки меняют результат: для учебного SYN-1 буфер 7 → 144 шт, буфер 14 → 216 шт.
- Сохранённая нулевая правка переживает обновление страницы; согласованная версия экспортируется в CSV.
- После перезапуска сервиса заказ остаётся в PostgreSQL. Повторный старт не создаёт дубли наборов.
- В публичном режиме нет формы загрузки оригиналов; прямой запрос импорта возвращает 403.

Если Python-окружение проекта установлено, из корня можно выполнить автоматическую HTTP-проверку. Подставьте свой HTTPS-адрес:

```powershell
.venv/Scripts/python.exe backend/scripts/smoke.py https://YOUR-SERVICE.onrender.com --state runtime/public-smoke.json
```

После ручного рестарта Render:

```powershell
.venv/Scripts/python.exe backend/scripts/smoke.py https://YOUR-SERVICE.onrender.com --state runtime/public-smoke.json --verify-restart
```

Скрипт создаёт один явно синтетический заказ, проверяет CSV, затем сравнивает сохранённый заказ после рестарта. Браузерный тест внешнего адреса описан в README через `NOMAD_E2E_URL`.

## Обновление и ограничения

При GitHub-развёртывании Render может автоматически пересобирать подключённую ветку. Для Existing Image новый `docker push` сам по себе не обновляет приложение: выберите **Manual Deploy → Deploy latest reference**. Изменение версии приложения не должно сопровождаться удалением базы.

Render Free засыпает после 15 минут без входящего трафика и просыпается при следующем запросе, обычно около минуты. Бесплатные ресурсы имеют квоты; гарантированная непрерывная доступность не заявляется. PostgreSQL нужен для сохранения заказов при рестартах и засыпании. Проверяйте выбранный тариф **Free**, не подключая платные ресурсы ради демонстрации.

`NOMAD_PUBLIC_DEMO=1` запрещает импорт и скрывает настоящие данные; режим требует PostgreSQL и включённой синтетики. Авторизации и разделения пользователей нет, демонстрационные заказы общие. Для локального импорта оригиналов используйте непубличный вариант из README.

Исходные XLSX/ZIP, `.env`, окружения и рабочие базы исключены из Docker-контекста. Конфигурация подключения поступает при запуске. Ранее использованный Cloudflare Tunnel был временным инструментом команды и не нужен для самостоятельной проверки.

Условия сервисов сверены 23.09.2026: [Render — готовые образы](https://render.com/docs/deploying-an-image), [Render Free](https://render.com/docs/free), [лимиты Docker Hub](https://docs.docker.com/docker-hub/usage/), [токены Docker](https://docs.docker.com/security/access-tokens/personal-access-tokens/).
