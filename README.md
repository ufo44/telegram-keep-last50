# Telegram Keep Last 50

Минимальный скрипт для чистки Telegram-канала через пользовательский Telegram Client API. Он оставляет последние N обычных сообщений в канале, а более старые сообщения удаляет партиями.

По умолчанию скрипт рассчитан на канал `@bknovosti` и оставляет последние `50` сообщений. Системная запись создания канала (`MessageActionChannelCreate`) пропускается, потому что Telegram API обычно не удаляет её как обычное сообщение.

## Для чего нужен

- Быстро почистить старую историю Telegram-канала.
- Не трогать последние актуальные публикации.
- Удалять сообщения партиями, чтобы не читать всю историю канала перед началом удаления.
- Работать от имени пользовательского аккаунта Telegram, у которого есть права администратора на удаление сообщений.

## Зависимости

- Python 3.10+
- [Telethon](https://docs.telethon.dev/) `>=1.36,<2`

Файл зависимостей:

```txt
telethon>=1.36,<2
```

Установка:

```powershell
python -m pip install -r requirements.txt
```

## Настройка

Нужны `api_id` и `api_hash` Telegram-приложения из `https://my.telegram.org/apps`.

Можно передать их через переменные окружения:

```powershell
$env:TG_API_ID="123456"
$env:TG_API_HASH="your_api_hash_here"
$env:TG_CHANNEL="@bknovosti"
```

Или через аргументы:

```powershell
python .\keep_last_50.py --api-id 123456 --api-hash your_api_hash_here
```

## Авторизация

Первый запуск отправляет код входа на телефон:

```powershell
python .\keep_last_50.py --phone +79991234567 --send-code
```

После получения кода:

```powershell
python .\keep_last_50.py --code 12345
```

Если на аккаунте включена двухфакторная защита:

```powershell
python .\keep_last_50.py --code 12345 --password "your_2fa_password"
```

После успешного входа Telethon создаст локальный файл сессии `telegram_cleanup.session`. Этот файл нельзя публиковать или отправлять в GitHub.

## Проверка без удаления

```powershell
python .\keep_last_50.py --max-delete 100 --show-selected
```

Без флага `--execute` скрипт ничего не удаляет.

## Удаление партиями

Удалить до 500 старых сообщений за один проход, оставив последние 50:

```powershell
python .\keep_last_50.py --execute --max-delete 500 --batch-size 100
```

Повторяйте команду, пока в выводе не появится:

```txt
Messages selected for deletion: 0
Nothing to delete.
```

## Основные параметры

- `--channel` - канал, например `@bknovosti`.
- `--keep` - сколько последних обычных сообщений оставить. По умолчанию `50`.
- `--execute` - реально удалять сообщения. Без него только предпросмотр.
- `--max-delete` - максимальное число сообщений за один проход. `0` означает без лимита.
- `--batch-size` - размер пачки удаления.
- `--show-selected` - показать ID выбранных старых сообщений.

## Безопасность

Не коммитьте:

- `.env`
- `*.session`
- `*.auth_state.json`
- `*.log`

Эти файлы добавлены в `.gitignore`.
