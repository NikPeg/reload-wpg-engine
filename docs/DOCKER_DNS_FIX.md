# Исправление проблемы DNS в Docker

## Проблема

При запуске бота в Docker контейнере возникала ошибка:

```
ClientConnectorDNSError: Cannot connect to host api.telegram.org:443 ssl:default [Name or service not known]
```

Это означает, что Docker контейнер не может разрешить доменное имя `api.telegram.org`.

## Причина

Docker контейнеры по умолчанию используют DNS-сервер хост-системы, но иногда это не работает корректно, особенно на macOS или при использовании VPN.

## Решение

Добавлены явные DNS-серверы в конфигурацию Docker Compose:

```yaml
services:
  wpg-bot:
    dns:
      - 8.8.8.8      # Google DNS Primary
      - 8.8.4.4      # Google DNS Secondary
      - 1.1.1.1      # Cloudflare DNS
```

### Используемые DNS-серверы:

1. **8.8.8.8** и **8.8.4.4** - Google Public DNS (надежный и быстрый)
2. **1.1.1.1** - Cloudflare DNS (приватный и безопасный)

## Альтернативные решения

### 1. Использование network_mode: host (не рекомендуется)

```yaml
services:
  wpg-bot:
    network_mode: host
```

**Минусы:**
- Менее безопасно
- Контейнер видит все сетевые интерфейсы хоста
- Не работает на Docker Desktop для Mac/Windows

### 2. Настройка Docker Daemon

Отредактируйте `/etc/docker/daemon.json`:

```json
{
  "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"]
}
```

Затем перезапустите Docker:

```bash
sudo systemctl restart docker
```

### 3. Использование системного DNS

```yaml
services:
  wpg-bot:
    dns_search: .
```

## Проверка работоспособности

После применения исправления, проверьте, что бот может подключиться к Telegram:

```bash
# Запустите контейнер
docker-compose up -d

# Проверьте логи
docker-compose logs -f wpg-bot

# Проверьте DNS внутри контейнера
docker-compose exec wpg-bot nslookup api.telegram.org
```

Ожидаемый вывод:

```
Server:         8.8.8.8
Address:        8.8.8.8#53

Non-authoritative answer:
Name:   api.telegram.org
Address: 149.154.167.220
```

## Применено в файлах

- `deploy/docker-compose.yml` - основная конфигурация
- `deploy/docker-compose.dev.yml` - конфигурация для разработки

## Дополнительные проблемы

Если проблема сохраняется, проверьте:

1. **Firewall/VPN**: Убедитесь, что нет блокировки исходящих соединений
2. **IPv6**: Попробуйте отключить IPv6 в Docker
3. **Прокси**: Если используется прокси, настройте его в Docker

```yaml
environment:
  - HTTP_PROXY=http://proxy.example.com:8080
  - HTTPS_PROXY=http://proxy.example.com:8080
  - NO_PROXY=localhost,127.0.0.1
```

