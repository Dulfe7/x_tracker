# X Web Tracker

Простой скрипт на Python, который без официального API извлекает новые твиты с публичной страницы X (Twitter) через Playwright и отправляет их в Telegram.

## Структура
```
x_web_tracker/
  tracker.py          # основной скрипт
  .env.example        # пример конфигурации (.env создаётся пользователем)
  last_id.txt         # хранит ID последнего твита
  requirements.txt    # зависимости
```

## Конфигурация
Создайте файл `.env` на основе `.env.example` в каталоге `x_web_tracker`:
```env
X_USERNAME=elonmusk
TELEGRAM_BOT_TOKEN=ваш_бот_токен
TELEGRAM_CHAT_ID=ваш_chat_id
```

## Запуск
1. Создайте и активируйте виртуальное окружение:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
   ```
2. Установите зависимости и браузеры Playwright:
   ```bash
   pip install -r x_web_tracker/requirements.txt
   python -m playwright install
   ```
3. Скопируйте `.env.example` в `.env` и заполните значения.
4. Запустите трекер:
   ```bash
   python x_web_tracker/tracker.py
   ```

## Поведение
- При первом запуске скрипт сохраняет ID последнего твита и не отправляет уведомления.
- На следующих запусках отправляет в Telegram только новые твиты, найденные после сохранённого ID.
- Если страница не загрузилась или разметка изменилась, скрипт выводит предупреждение и завершает работу без исключений.

### Частые проблемы
- Ошибка вида `BrowserType.launch: Executable doesn't exist ... playwright install` означает, что нужно скачать бинарники браузера. Запустите `python -m playwright install`, затем повторите запуск скрипта.
