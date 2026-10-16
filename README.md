# NokaGram social shorts

Полностью автоматический конвейер вертикальных промо-роликов для Telegram-канала
[@NokaGram](https://t.me/NokaGram).

```
content/topics.json  ->  edge-tts (голос)  ->  ASS-субтитры  ->
ffmpeg (процедурный фон + брендинг)  ->  out/<id>.mp4 + <id>.json  ->
YouTube (videos.insert) / TikTok (Content Posting API)
```

Рендер не требует API-ключей. Публикация — по секретам (см. ниже).

## Быстрый старт (локально)

```powershell
pip install -r requirements.txt
# нужен ffmpeg в PATH
python scripts/make_short.py --out out            # ротация по дню
python scripts/make_short.py --out out --topic nokagram-intro
```

Результат: `out/<id>.mp4` (1080x1920, H.264/AAC) и `out/<id>.json` с метаданными.

## Как это работает

- **Сценарий** — `content/topics.json`, поле `scenes` (список фраз). Озвучка
  читает их подряд, субтитры режутся по границам слов от edge-tts.
- **Голос** — `voice` у топика (`ru-RU-DmitryNeural` / `ru-RU-SvetlanaNeural`).
- **Фон** — генерируется на лету фильтром ffmpeg `gradients` + шум + виньетка,
  никаких стоков и прав.
- **Брендинг** — хэндл `@NokaGram` снизу и CTA сверху (берётся из `cta`).
- **Ротация** — если `--topic` пуст, топик выбирается по номеру дня.

## GitHub Actions

Workflow `.github/workflows/shorts.yml`:
- `schedule: 0 9 * * *` — ежедневный рендер (UTC), публикация по секретам.
- `workflow_dispatch` — ручной запуск, поля `topic` и `publish`.

### Секреты репозитория

| Secret | Зачем |
|---|---|
| `YT_CLIENT_ID` | OAuth-клиент Google (Desktop app) |
| `YT_CLIENT_SECRET` | ... |
| `YT_REFRESH_TOKEN` | получается один раз локально, см. ниже |
| `TIKTOK_ACCESS_TOKEN` | токен с scope `video.publish` (нужен app-audit) |

Пока секретов нет — workflow просто рендерит и кладёт видео в артефакт.

### Как получить YouTube refresh token

1. Google Cloud Console -> новый проект.
2. Включить **YouTube Data API v3**.
3. OAuth consent screen: тип External, добавить себя в Test users.
   (В статусе Testing refresh-token живёт ~7 дней — для долгой работы нужно
   опубликовать приложение / пройти verification.)
4. Credentials -> Create credentials -> **OAuth client ID** -> тип **Desktop app**.
5. Локально:

```powershell
$env:YT_CLIENT_ID="....apps.googleusercontent.com"
$env:YT_CLIENT_SECRET="...."
python scripts/yt_auth.py
```

Скрипт откроет браузер и выведет `YT_REFRESH_TOKEN` — залить в Secrets.

Квота: загрузка = отдельный bucket, ~100 видео/сутки. Шортсы отдельного метода
не имеют — просто вертикаль ≤3 мин.

### TikTok

Direct Post требует:
- зарегистрированное приложение + продукт **Content Posting API**;
- scope `video.publish` **после ревью** и **пройденный app-audit**;
- домен верифицирован, если грузишь по `PULL_FROM_URL` (у нас `FILE_UPLOAD`).

До аудита все посты принудительно `SELF_ONLY` (приватно) — это ограничение
TikTok, а не наше. `TIKTOK_PRIVACY` по умолчанию `SELF_ONLY`.

## Правки контента

`content/topics.json` — просто добавь новый объект с уникальным `id`.
Тексты сейчас черновые и НЕ проверены на соответствие фактическому состоянию
продукта — вычитай перед публикацией.
