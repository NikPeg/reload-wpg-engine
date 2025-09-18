#!/usr/bin/env python3
"""
Демонстрация улучшенной RAG системы с текстовыми описаниями
"""

from unittest.mock import AsyncMock

from wpg_engine.core.rag_system import RAGSystem


def test_rag_with_descriptions():
    """Демонстрация того, как RAG теперь включает текстовые описания"""

    # Создаем мок RAG системы
    mock_db = AsyncMock()
    rag_system = RAGSystem(mock_db)

    # Пример данных стран с описаниями
    countries_data = [
        {
            "name": "Солярия",
            "capital": "Солнечный Город",
            "population": 5000000,
            "synonyms": ["Солнечная Империя", "СИ"],
            "aspects": {
                "economy": 7,
                "military": 8,
                "foreign_policy": 6,
                "territory": 7,
                "technology": 9,
                "religion_culture": 5,
                "governance_law": 8,
                "construction_infrastructure": 7,
                "social_relations": 6,
                "intelligence": 7,
            },
            "descriptions": {
                "economy": "Развитая промышленность с акцентом на солнечную энергетику",
                "military": "Современная армия с высокотехнологичным оружием на солнечных батареях",
                "foreign_policy": "Активная дипломатия, продвижение экологических технологий",
                "territory": "Обширные солнечные равнины, идеальные для энергетики",
                "technology": "Мировой лидер в области солнечных технологий и чистой энергии",
                "religion_culture": "Культ Солнца, поклонение светилу как источнику жизни",
                "governance_law": "Конституционная монархия с Советом Солнца",
                "construction_infrastructure": "Развитая сеть солнечных электростанций",
                "social_relations": "Стабильное общество, объединенное идеей чистой энергии",
                "intelligence": "Эффективные спецслужбы 'Солнечный Глаз'",
            },
        },
        {
            "name": "Вирджиния",
            "capital": "Ричмонд",
            "population": 3000000,
            "synonyms": ["Вирг", "ВР"],
            "aspects": {
                "economy": 6,
                "military": 5,
                "foreign_policy": 7,
                "territory": 6,
                "technology": 6,
                "religion_culture": 8,
                "governance_law": 7,
                "construction_infrastructure": 6,
                "social_relations": 7,
                "intelligence": 5,
            },
            "descriptions": {
                "economy": "Аграрная экономика с развитым табачным производством",
                "military": "Традиционная армия с акцентом на кавалерию",
                "foreign_policy": "Дипломатия джентльменов, старые традиции",
                "territory": "Плодородные земли, холмистая местность",
                "technology": "Консервативный подход к новым технологиям",
                "religion_culture": "Глубокие христианские традиции, аристократическая культура",
                "governance_law": "Республика с сильными традициями самоуправления",
                "construction_infrastructure": "Классическая архитектура, железные дороги",
                "social_relations": "Традиционное общество с четкой иерархией",
                "intelligence": "Разведка на основе личных связей и традиций",
            },
        }
    ]

    # Создаем промпт
    message = "Хочу напасть на Вирджинию с помощью новых технологий"
    sender_country = "Солярия"

    prompt = rag_system._create_analysis_prompt(message, sender_country, countries_data)

    print("=" * 80)
    print("🔍 ДЕМОНСТРАЦИЯ УЛУЧШЕННОЙ RAG СИСТЕМЫ")
    print("=" * 80)
    print(f"Сообщение игрока: {message}")
    print(f"Страна отправителя: {sender_country}")
    print("=" * 80)
    print("ПРОМПТ ДЛЯ LLM (с текстовыми описаниями):")
    print("=" * 80)
    print(prompt)
    print("=" * 80)

    # Проверяем, что описания включены
    assert "Развитая промышленность с акцентом на солнечную энергетику" in prompt
    assert "Современная армия с высокотехнологичным оружием на солнечных батареях" in prompt
    assert "Мировой лидер в области солнечных технологий" in prompt
    assert "Аграрная экономика с развитым табачным производством" in prompt
    assert "Традиционная армия с акцентом на кавалерию" in prompt

    print("✅ УСПЕХ: Все текстовые описания включены в промпт!")
    print("✅ Теперь RAG система учитывает не только цифры, но и текстовые описания полей стран!")


if __name__ == "__main__":
    test_rag_with_descriptions()
