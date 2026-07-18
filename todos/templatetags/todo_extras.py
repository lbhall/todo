"""Lightweight, dependency-free Markdown-ish rendering for todo text.

Supports only what the entry-box toolbar produces:
  **bold**  ->  <strong>
  *italic*  ->  <em>       (also _italic_)
  - bullet  ->  <ul><li>   (lines starting with "- " or "* ")
  newlines  ->  <br>

Security: the input is HTML-escaped *first*, then our own tags are inserted,
so user text can never inject markup. No external libraries required.
"""
import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

_BOLD = re.compile(r'\*\*(.+?)\*\*', re.S)
_ITALIC_STAR = re.compile(r'\*(.+?)\*', re.S)
_ITALIC_UNDERSCORE = re.compile(r'_(.+?)_', re.S)
_BULLET = re.compile(r'^\s*[-*]\s+(.*)$')


def _inline(text):
    """Apply inline emphasis. Bold first so ** isn't eaten by the * rule."""
    text = _BOLD.sub(r'<strong>\1</strong>', text)
    text = _ITALIC_UNDERSCORE.sub(r'<em>\1</em>', text)
    text = _ITALIC_STAR.sub(r'<em>\1</em>', text)
    return text


@register.filter(name='format_todo')
def format_todo(value):
    escaped = escape(value or '')
    out = []
    text_lines = []
    list_items = []

    def flush_text():
        if text_lines:
            out.append('<br>'.join(_inline(line) for line in text_lines))
            text_lines.clear()

    def flush_list():
        if list_items:
            out.append('<ul>' + ''.join(f'<li>{_inline(i)}</li>' for i in list_items) + '</ul>')
            list_items.clear()

    for line in escaped.split('\n'):
        m = _BULLET.match(line)
        if m:
            flush_text()
            list_items.append(m.group(1))
        else:
            flush_list()
            text_lines.append(line)
    flush_text()
    flush_list()
    return mark_safe(''.join(out))
