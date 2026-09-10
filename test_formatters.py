import unittest
import formatters

class TestFormatters(unittest.TestCase):
    def test_header_sanitization(self):
        raw = "# Título 1\n## Título 2\n### Título 3"
        sanitized = formatters.sanitize_telegram_markdown(raw)
        self.assertNotIn("#", sanitized)
        self.assertIn("📌 **TÍTULO 1**", sanitized)
        self.assertIn("🔹 **Título 2**", sanitized)
        self.assertIn("• **Título 3**", sanitized)

    def test_divider_removal(self):
        raw = "Texto 1\n---\nTexto 2\n***\nTexto 3\n___"
        sanitized = formatters.sanitize_telegram_markdown(raw)
        self.assertNotIn("---", sanitized)
        self.assertNotIn("***", sanitized)
        self.assertNotIn("___", sanitized)
        self.assertIn("Texto 1", sanitized)
        self.assertIn("Texto 2", sanitized)
        self.assertIn("Texto 3", sanitized)

    def test_callout_conversion(self):
        raw = "> [!NOTE] Este é um aviso importante\n> [!WARNING] Cuidado com o comando"
        sanitized = formatters.sanitize_telegram_markdown(raw)
        self.assertIn("💡 **Note:** Este é um aviso importante", sanitized)
        self.assertIn("⚠️ **Warning:** Cuidado com o comando", sanitized)
        self.assertNotIn("[!NOTE]", sanitized)

    def test_code_block_protection(self):
        raw = "```python\n# Comentário de código não deve ser transformado\n---\nx = 10\n```"
        sanitized = formatters.sanitize_telegram_markdown(raw)
        self.assertIn("# Comentário de código não deve ser transformado", sanitized)
        self.assertIn("---", sanitized)
        self.assertTrue(sanitized.startswith("```python"))

    def test_table_to_cards(self):
        raw = "| Nome | Status |\n|---|---|\n| Bot | Online |"
        sanitized = formatters.sanitize_telegram_markdown(raw)
        self.assertNotIn("|---|---|", sanitized)
        self.assertIn("• **Nome:** Bot", sanitized)
        self.assertIn("• **Status:** Online", sanitized)

    def test_html_formatting(self):
        raw = "### Título\n**Negrito** e *Itálico* e `codigo`\n```python\nprint(1)\n```"
        html_out = formatters.format_telegram_html(raw)
        self.assertIn("<b>Negrito</b>", html_out)
        self.assertIn("<i>Itálico</i>", html_out)
        self.assertIn("<code>codigo</code>", html_out)
        self.assertIn('<pre><code class="language-python">print(1)</code></pre>', html_out)

    def test_speech_phonetic_sanitization(self):
        raw = """### Relatório Técnico 🚀✨
---
Aqui está o código gerado para o bot:

```python
def conectar_banco():
    return sqlite3.connect("banco.db")
```

Para mais detalhes, consulte https://github.com/akitaonrails/ai-memory ou https://akitaonrails.com/2026/artigo.
> [!NOTE] Lembre-se de rodar os testes!
"""
        speech = formatters.prepare_text_for_speech(raw, max_chars=6000)
        # Emojis must be removed
        self.assertNotIn("🚀", speech)
        self.assertNotIn("✨", speech)
        # Headers & dividers removed
        self.assertNotIn("###", speech)
        self.assertNotIn("---", speech)
        # URLs must be converted into natural speech references
        self.assertNotIn("https://", speech)
        self.assertIn("link do GitHub", speech)
        self.assertIn("link do artigo do Akita", speech)
        # Code block converted into descriptive placeholder
        self.assertNotIn("def conectar_banco()", speech)
        self.assertIn("Bloco de código em python detalhado no chat", speech)
        # Prose text preserved
        self.assertIn("Relatório Técnico", speech)
        self.assertIn("Lembre-se de rodar os testes", speech)

if __name__ == "__main__":
    unittest.main()
