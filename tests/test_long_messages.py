"""
Tests for long message splitting functionality
"""

from wpg_engine.adapters.telegram.handlers.messages import _split_long_text


def test_split_short_text():
    """Test that short text is not split"""
    short_text = "This is a short message."
    result = _split_long_text(short_text, 4096)
    assert len(result) == 1
    assert result[0] == short_text


def test_split_long_text_by_paragraphs():
    """Test splitting long text by paragraphs"""
    long_text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    result = _split_long_text(long_text, 30)  # Force splitting

    assert len(result) >= 2
    assert all(len(part) <= 30 for part in result)

    # Check that content is preserved
    combined = "\n\n".join(result)
    # Remove extra whitespace for comparison
    assert combined.replace("\n\n\n\n", "\n\n").strip() == long_text.strip()


def test_split_very_long_paragraph():
    """Test splitting very long paragraph by sentences"""
    long_paragraph = "This is sentence one. This is sentence two. This is sentence three. This is sentence four."
    result = _split_long_text(long_paragraph, 40)  # Force splitting

    assert len(result) >= 2
    assert all(len(part) <= 40 for part in result)


def test_split_rag_like_content():
    """Test splitting RAG-like content with headers and lists"""
    rag_content = """📊 RAG-справка:

**Запрос игрока:** Нападение Солярии на Вирджинию и Абобистан.

### **1. Военная мощь:**
- **Солярия (СИ):** Высокий уровень (8/10). Преимущество в технологиях (9/10)
- **Вирджиния (ВР):** Средний уровень (5/10). Слабее в военном деле
- **Абобистан (АБ):** Низкий уровень (3/10). Минимальная сопротивляемость

### **2. Экономика и ресурсы:**
- Солярия (7/10) сильнее Вирджинии (6/10) и Абобистана (4/10)

### **3. Рекомендации:**
- Солярия имеет явное военное превосходство
- Вирджиния может создать дипломатические сложности
- Учитывайте репутационные риски нападения на две страны"""

    result = _split_long_text(rag_content, 200)  # Force splitting

    # Should split into multiple parts
    assert len(result) >= 2

    # Each part should be within limit
    assert all(len(part) <= 200 for part in result)

    # First part should contain the header
    assert "📊 RAG-справка:" in result[0]


def test_split_preserves_content():
    """Test that splitting preserves all content"""
    original = "A" * 1000 + "\n\n" + "B" * 1000 + "\n\n" + "C" * 1000
    result = _split_long_text(original, 500)

    # Should be split into multiple parts
    assert len(result) > 1

    # Reconstruct and compare (accounting for formatting changes)
    reconstructed = "\n\n".join(result)

    # Count characters to ensure nothing is lost
    original_chars = len(original.replace("\n\n", ""))
    reconstructed_chars = len(reconstructed.replace("\n\n", ""))

    assert original_chars == reconstructed_chars


def test_empty_text():
    """Test handling of empty text"""
    result = _split_long_text("", 4096)
    assert len(result) == 1
    assert result[0] == ""


def test_exact_limit():
    """Test text that is exactly at the limit"""
    text = "A" * 100
    result = _split_long_text(text, 100)
    assert len(result) == 1
    assert result[0] == text
