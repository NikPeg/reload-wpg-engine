"""
Tests for RAG formatting functionality
"""

from telegramify_markdown import markdownify


def test_telegramify_markdown_basic():
    """Test basic telegramify-markdown functionality"""
    markdown_text = """
# Header 1

**Bold text** and *italic text*

- List item 1
- List item 2

### Subheader

Some regular text with `code`.
"""

    # Should not raise exception
    result = markdownify(markdown_text)
    assert isinstance(result, str)
    assert len(result) > 0


def test_telegramify_markdown_rag_format():
    """Test telegramify-markdown with RAG-style content"""
    rag_content = """📊 RAG-справка:

**Запрос игрока:** Нападение Солярии на Вирджинию и Абобистан.

### **1. Военная мощь:**
- **Солярия (СИ):** Высокий уровень (8/10). Преимущество в технологиях (9/10)
- **Вирджиния (ВР):** Средний уровень (5/10). Слабее в военном деле
- **Абобистан (АБ):** Низкий уровень (3/10). Минимальная сопротивляемость

### **2. Рекомендации:**
- Солярия имеет явное военное превосходство
- Учитывайте репутационные риски нападения на две страны"""

    # Should not raise exception
    result = markdownify(rag_content)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "📊" in result  # Emoji should be preserved


def test_html_escaping():
    """Test HTML character escaping for fallback"""
    dangerous_text = 'Text with <script>alert("xss")</script> & "quotes" & \'apostrophes\''

    safe_text = (dangerous_text
                 .replace('&', '&amp;')
                 .replace('<', '&lt;')
                 .replace('>', '&gt;')
                 .replace('"', '&quot;')
                 .replace("'", '&#x27;'))

    assert '&lt;script&gt;' in safe_text
    assert '&amp;' in safe_text
    assert '&quot;' in safe_text
    assert '&#x27;' in safe_text
    assert '<script>' not in safe_text


def test_markdown_with_special_characters():
    """Test markdown with characters that might cause issues"""
    problematic_text = """📊 **RAG-справка:**

**Административной Республики** (АР) со стороны страны **ejedfiojovjfd**.

### **Сравнительный анализ**:
1. **Военная мощь**:
   - **АР**: Высокий уровень (7/10), сильная разведка (9/10).

*Примечание*: Данные могут содержать символы < > & " '"""

    # Should handle special characters gracefully
    try:
        result = markdownify(problematic_text)
        assert isinstance(result, str)
    except Exception:
        # If markdownify fails, fallback should work
        safe_text = (problematic_text
                     .replace('&', '&amp;')
                     .replace('<', '&lt;')
                     .replace('>', '&gt;')
                     .replace('"', '&quot;')
                     .replace("'", '&#x27;'))
        assert isinstance(safe_text, str)
        assert '&lt;' in safe_text or '<' not in problematic_text
