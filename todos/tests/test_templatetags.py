from django.test import SimpleTestCase

from todos.templatetags.todo_extras import _inline, format_todo


class InlineTests(SimpleTestCase):
    def test_bold(self):
        self.assertEqual(_inline('a **b** c'), 'a <strong>b</strong> c')

    def test_italic_star_and_underscore(self):
        self.assertEqual(_inline('*x*'), '<em>x</em>')
        self.assertEqual(_inline('_y_'), '<em>y</em>')

    def test_bold_not_eaten_by_italic(self):
        self.assertEqual(_inline('**bold**'), '<strong>bold</strong>')


class FormatTodoTests(SimpleTestCase):
    def test_empty_input(self):
        self.assertEqual(format_todo(''), '')
        self.assertEqual(format_todo(None), '')

    def test_escapes_html(self):
        out = format_todo('<script>alert(1)</script>')
        self.assertNotIn('<script>', out)
        self.assertIn('&lt;script&gt;', out)

    def test_newlines_become_br(self):
        out = format_todo('line1\nline2')
        self.assertEqual(out, 'line1<br>line2')

    def test_bold_and_italic(self):
        out = format_todo('**b** and *i*')
        self.assertEqual(out, '<strong>b</strong> and <em>i</em>')

    def test_bullets_dash(self):
        out = format_todo('- one\n- two')
        self.assertEqual(out, '<ul><li>one</li><li>two</li></ul>')

    def test_bullets_star(self):
        out = format_todo('* a')
        self.assertEqual(out, '<ul><li>a</li></ul>')

    def test_mixed_text_and_list(self):
        out = format_todo('intro\n- item\noutro')
        self.assertEqual(out, 'intro<ul><li>item</li></ul>outro')

    def test_inline_inside_bullet(self):
        out = format_todo('- **bold** item')
        self.assertEqual(out, '<ul><li><strong>bold</strong> item</li></ul>')
