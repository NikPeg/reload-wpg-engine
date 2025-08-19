"""
Tests for RAG system
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from wpg_engine.core.rag_system import RAGSystem
from wpg_engine.models import Country


@pytest.fixture
def mock_db():
    """Mock database session"""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def rag_system(mock_db):
    """RAG system instance"""
    return RAGSystem(mock_db)


@pytest.fixture
def sample_countries():
    """Sample countries data"""
    country1 = Country(
        id=1,
        name="Солярия",
        capital="Солнечный Город",
        population=5000000,
        synonyms=["Солнечная Империя", "СИ"],
        economy=7,
        military=8,
        foreign_policy=6,
        territory=7,
        technology=9,
        religion_culture=5,
        governance_law=8,
        construction_infrastructure=7,
        social_relations=6,
        intelligence=7,
    )

    country2 = Country(
        id=2,
        name="Вирджиния",
        capital="Ричмонд",
        population=3000000,
        synonyms=["Вирг", "ВР"],
        economy=6,
        military=5,
        foreign_policy=7,
        territory=6,
        technology=6,
        religion_culture=8,
        governance_law=7,
        construction_infrastructure=6,
        social_relations=7,
        intelligence=5,
    )

    country3 = Country(
        id=3,
        name="Абобистан",
        capital="Абобград",
        population=2000000,
        synonyms=["Абоба", "АБ"],
        economy=4,
        military=3,
        foreign_policy=5,
        territory=5,
        technology=4,
        religion_culture=6,
        governance_law=4,
        construction_infrastructure=3,
        social_relations=5,
        intelligence=4,
    )

    return [country1, country2, country3]


@pytest.mark.asyncio
async def test_get_all_countries_data(rag_system, mock_db, sample_countries):
    """Test getting all countries data"""
    # Mock database query properly
    mock_scalars = AsyncMock()
    mock_scalars.all = lambda: sample_countries  # Use lambda instead of return_value
    mock_result = AsyncMock()
    mock_result.scalars = lambda: mock_scalars  # Use lambda instead of return_value
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Test
    countries_data = await rag_system._get_all_countries_data(game_id=1)

    # Assertions
    assert len(countries_data) == 3
    assert countries_data[0]['name'] == "Солярия"
    assert countries_data[0]['synonyms'] == ["Солнечная Империя", "СИ"]
    assert countries_data[0]['aspects']['military'] == 8
    assert countries_data[1]['name'] == "Вирджиния"
    assert countries_data[2]['name'] == "Абобистан"


@pytest.mark.asyncio
async def test_create_analysis_prompt(rag_system):
    """Test creating analysis prompt"""
    message = "Хочу напасть на Вирджинию и Абобистан"
    sender_country = "Солярия"
    countries_data = [
        {
            'name': 'Солярия',
            'capital': 'Солнечный Город',
            'population': 5000000,
            'synonyms': ['Солнечная Империя', 'СИ'],
            'aspects': {
                'economy': 7,
                'military': 8,
                'foreign_policy': 6,
                'territory': 7,
                'technology': 9,
                'religion_culture': 5,
                'governance_law': 8,
                'construction_infrastructure': 7,
                'social_relations': 6,
                'intelligence': 7,
            },
            'descriptions': {
                'economy': None,
                'military': None,
                'foreign_policy': None,
                'territory': None,
                'technology': None,
                'religion_culture': None,
                'governance_law': None,
                'construction_infrastructure': None,
                'social_relations': None,
                'intelligence': None,
            }
        }
    ]

    prompt = rag_system._create_analysis_prompt(message, sender_country, countries_data)

    # Check that prompt contains key elements
    assert "Солярия" in prompt
    assert "напасть на Вирджинию и Абобистан" in prompt
    assert "Военной мощи" in prompt  # Fixed case
    assert "📊 RAG-справка:" in prompt


@pytest.mark.asyncio
async def test_generate_admin_context_no_api_key(rag_system, mock_db):
    """Test generate_admin_context when no API key is available"""
    rag_system.api_key = None

    result = await rag_system.generate_admin_context(
        "Тестовое сообщение",
        "Солярия",
        1
    )

    assert result == ""


@pytest.mark.asyncio
async def test_generate_admin_context_with_api_key(rag_system, mock_db, sample_countries):
    """Test generate_admin_context with API key"""
    rag_system.api_key = "test-key"

    # Mock database query properly
    mock_scalars = AsyncMock()
    mock_scalars.all = lambda: sample_countries
    mock_result = AsyncMock()
    mock_result.scalars = lambda: mock_scalars
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Mock API call
    with patch.object(rag_system, '_call_openrouter_api') as mock_api:
        mock_api.return_value = "📊 RAG-справка: Тестовый ответ от AI"

        result = await rag_system.generate_admin_context(
            "Хочу напасть на Вирджинию",
            "Солярия",
            1
        )

        assert result == "📊 RAG-справка: Тестовый ответ от AI"
        mock_api.assert_called_once()


@pytest.mark.asyncio
async def test_generate_admin_context_api_error(rag_system, mock_db, sample_countries):
    """Test generate_admin_context when API call fails"""
    rag_system.api_key = "test-key"

    # Mock database query properly
    mock_scalars = AsyncMock()
    mock_scalars.all = lambda: sample_countries
    mock_result = AsyncMock()
    mock_result.scalars = lambda: mock_scalars
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Mock API call to raise exception
    with patch.object(rag_system, '_call_openrouter_api') as mock_api:
        mock_api.side_effect = Exception("API Error")

        result = await rag_system.generate_admin_context(
            "Тестовое сообщение",
            "Солярия",
            1
        )

        assert result == ""
