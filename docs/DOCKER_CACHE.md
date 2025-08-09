# Docker Cache Guide

Руководство по работе с кэшем Docker для эффективной разработки WPG Engine.

## 🧠 Как работает кэш Docker

Docker кэширует каждый слой (layer) образа. Каждая инструкция в Dockerfile создает новый слой:

```dockerfile
FROM python:3.11-slim          # Слой 1 - базовый образ
RUN apt-get update...          # Слой 2 - системные пакеты  
RUN groupadd -r wpgbot...      # Слой 3 - пользователь
WORKDIR /app                   # Слой 4 - рабочая директория
COPY requirements.txt .        # Слой 5 - зависимости
RUN pip install...             # Слой 6 - установка пакетов
COPY . .                       # Слой 7 - ВАШ КОД
```

## ✅ Когда кэш используется

- Dockerfile не изменился
- Файлы, копируемые в слой, не изменились  
- Команды RUN одинаковые
- В выводе видите `CACHED`

## ❌ Когда кэш НЕ используется

- Изменили код проекта (влияет на `COPY . .`)
- Изменили `requirements.txt` (влияет на `pip install`)
- Изменили Dockerfile
- Использовали флаг `--no-cache`

## 🔄 Рабочий процесс разработки

### При изменении кода Python
```bash
# Изменили main.py, wpg_engine/*.py и т.д.
make run    # Автоматически пересоберет образ
```

### При добавлении новых зависимостей
```bash
# Изменили requirements.txt
make down
make run    # Переустановит все пакеты
```

### При изменении Dockerfile
```bash
# Изменили Dockerfile (добавили системные пакеты и т.д.)
make down
docker-compose build --no-cache
docker-compose up -d
```

### При странном поведении
```bash
# Принудительная очистка всего кэша
make clean
docker build --no-cache -t wpg-engine .
make run
```

## 🔍 Как понять что происходит

Смотрите на вывод команды `docker build`:

```bash
=> CACHED [2/9] RUN apt-get update...     # ← Использует кэш
=> [7/9] COPY --chown=wpgbot:wpgbot . .   # ← Пересобирает (нет CACHED)
```

## 💡 Оптимизация кэша

Наш Dockerfile уже оптимизирован для максимального использования кэша:

1. **Системные пакеты** (изменяются редко) → кэшируются долго
2. **Python зависимости** (изменяются средне) → кэшируются пока не изменится `requirements.txt`
3. **Код приложения** (изменяется часто) → пересобирается при каждом изменении

## 🚀 Быстрые команды

| Ситуация | Команда |
|----------|---------|
| Изменил код | `make run` |
| Добавил зависимость | `make down && make run` |
| Изменил Dockerfile | `docker-compose build --no-cache && docker-compose up -d` |
| Что-то сломалось | `make clean && docker build --no-cache -t wpg-engine . && make run` |

## 🎯 Полезные команды для отладки

```bash
# Посмотреть все образы
docker images

# Посмотреть размер слоев
docker history wpg-engine

# Очистить неиспользуемые образы
docker image prune

# Очистить весь кэш Docker (ОСТОРОЖНО!)
docker system prune -a
```

## ⚠️ Важные моменты

- **Не используйте `--no-cache` без необходимости** - это замедляет сборку
- **При изменении только кода Python** достаточно `make run`
- **Кэш работает по принципу "изменился один слой = пересобираются все последующие"**
- **Порядок инструкций в Dockerfile важен для эффективного кэширования**

## 🔧 Troubleshooting

### Проблема: Код не обновляется в контейнере
```bash
# Решение: принудительная пересборка
make down
docker-compose build --no-cache
docker-compose up -d
```

### Проблема: Долгая сборка каждый раз
```bash
# Проверьте что requirements.txt не изменяется постоянно
# Убедитесь что .dockerignore настроен правильно
```

### Проблема: Ошибки типа "file not found" в контейнере
```bash
# Возможно используется старый кэш, очистите его
docker build --no-cache -t wpg-engine .