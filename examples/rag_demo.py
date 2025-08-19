"""
Демонстрация работы RAG системы
"""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from wpg_engine.core.rag_system import RAGSystem
from wpg_engine.models import Country, Game
from wpg_engine.models.base import Base


async def create_demo_data(session: AsyncSession):
    """Создать демонстрационные данные"""

    # Создать игру
    game = Game(
        name="Демо игра",
        description="Демонстрационная игра для RAG",
        setting="Фэнтези",
        max_players=10,
        years_per_day=5,
        max_points=30,
        max_population=10000000
    )
    session.add(game)
    await session.flush()

    # Создать страны
    countries_data = [
        {
            "name": "Солярия",
            "capital": "Солнечный Город",
            "population": 5000000,
            "synonyms": ["Солнечная Империя", "СИ"],
            "aspects": {
                "economy": 7, "military": 8, "foreign_policy": 6,
                "territory": 7, "technology": 9, "religion_culture": 5,
                "governance_law": 8, "construction_infrastructure": 7,
                "social_relations": 6, "intelligence": 7
            }
        },
        {
            "name": "Вирджиния",
            "capital": "Ричмонд",
            "population": 3000000,
            "synonyms": ["Вирг", "ВР"],
            "aspects": {
                "economy": 6, "military": 5, "foreign_policy": 7,
                "territory": 6, "technology": 6, "religion_culture": 8,
                "governance_law": 7, "construction_infrastructure": 6,
                "social_relations": 7, "intelligence": 5
            }
        },
        {
            "name": "Абобистан",
            "capital": "Абобград",
            "population": 2000000,
            "synonyms": ["Абоба", "АБ"],
            "aspects": {
                "economy": 4, "military": 3, "foreign_policy": 5,
                "territory": 5, "technology": 4, "religion_culture": 6,
                "governance_law": 4, "construction_infrastructure": 3,
                "social_relations": 5, "intelligence": 4
            }
        }
    ]

    for country_data in countries_data:
        country = Country(
            game_id=game.id,
            name=country_data["name"],
            capital=country_data["capital"],
            population=country_data["population"],
            synonyms=country_data["synonyms"],
            **country_data["aspects"]
        )
        session.add(country)

    await session.commit()
    return game.id


async def demo_rag_analysis():
    """Демонстрация анализа RAG системы"""

    # Создать временную базу данных в памяти
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Создать таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Создать сессию
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Создать демонстрационные данные
        game_id = await create_demo_data(session)

        # Создать RAG систему
        rag_system = RAGSystem(session)

        # Тестовые сообщения
        test_messages = [
            {
                "message": "Хочу напасть на Вирджинию и Абобистан",
                "sender": "Солярия"
            },
            {
                "message": "Предлагаю торговое соглашение с СИ",
                "sender": "Вирджиния"
            },
            {
                "message": "Нужна помощь в развитии технологий",
                "sender": "Абобистан"
            },
            {
                "message": "Солнечная Империя угрожает нашим границам",
                "sender": "Абобистан"
            }
        ]

        print("🤖 Демонстрация RAG системы для админа\n")
        print("=" * 60)

        for i, test_case in enumerate(test_messages, 1):
            print(f"\n📝 Тест {i}:")
            print(f"Отправитель: {test_case['sender']}")
            print(f"Сообщение: {test_case['message']}")
            print("-" * 40)

            # Получить контекст от RAG системы
            context = await rag_system.generate_admin_context(
                test_case["message"],
                test_case["sender"],
                game_id
            )

            if context:
                print("🎯 RAG контекст для админа:")
                print(context)
            else:
                print("⚠️ RAG контекст не сгенерирован (нет API ключа или ошибка)")

                # Показать альтернативную информацию
                print("📊 Базовая информация о странах:")
                countries_data = await rag_system._get_all_countries_data(game_id)
                for country in countries_data:
                    if (country['name'].lower() in test_case['message'].lower() or
                        any(syn.lower() in test_case['message'].lower() for syn in country['synonyms'])):
                        print(f"  🏛️ {country['name']}: Военное дело {country['aspects']['military']}/10, "
                              f"Экономика {country['aspects']['economy']}/10")

            print()


if __name__ == "__main__":
    print("Запуск демонстрации RAG системы...")
    print("Примечание: Для полной работы нужен API ключ OpenRouter в переменной AI_TOKEN")
    print()

    asyncio.run(demo_rag_analysis())
