"""Readers for the reference library (dungeon/library.py): a long text file as titled sections of plain text.

Plain text and Markdown, a web page, an EPUB book and a TiddlyWiki saved as one file (one section per tiddler, its
title kept). Nothing runs and nothing is fetched: markup is dropped and only the words are kept.
"""
import html
import json
import posixpath
import re
from html.parser import HTMLParser
from io import BytesIO
from pathlib import PureWindowsPath
from urllib.parse import unquote
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from dungeon.errors import DomainError

TYPES = '.txt, .md, .html, .epub or a TiddlyWiki file'
MAX_UNPACKED = 64 * 1024 * 1024
# A line on its own that starts a chapter of a novel or a part of a script.
CHAPTER = re.compile(r'^[ \t]*((?:chapter|part|book|act|scene|prologue|epilogue|interlude)\b[^\n]{0,80})$',
                     re.IGNORECASE | re.MULTILINE)
MARKDOWN_HEADING = re.compile(r'^#{1,6}[ \t]+(.+?)[ \t#]*$', re.MULTILINE)
BLOCKS = {'p', 'div', 'br', 'li', 'tr', 'section', 'article', 'blockquote', 'pre', 'table', 'ul', 'ol', 'dd', 'dt'}
HEADINGS = {'h1', 'h2', 'h3', 'h4'}
SKIPPED = {'script', 'style', 'head', 'title', 'svg', 'noscript', 'template'}
STORE = re.compile(r'<script class="tiddlywiki-tiddler-store" type="application/json">(.*?)</script>', re.S)
STORE_AREA = re.compile(r'<div id="storeArea"[^>]*>(.*)</div>', re.S)
OLD_TIDDLER = re.compile(r'<div\s([^>]*\btitle="[^"]*"[^>]*)>(.*?)</div>', re.S)
# A tiddler named after a picture, a video or a sound holds only the player for it.
MEDIA = re.compile(r'\.(png|jpe?g|gif|webp|svg|mp4|webm|mov|mp3|wav|ogg|m4a|pdf)$', re.IGNORECASE)
TEXT_TYPES = {'', 'text/vnd.tiddlywiki', 'text/x-tiddlywiki', 'text/markdown', 'text/x-markdown', 'text/plain',
              'text/html'}


def problem(message: str) -> DomainError:
    return DomainError(message, 422)


def read(filename: str, source: bytes) -> dict:
    """{format, name, sections: [(title, text)]} from one file."""
    path = PureWindowsPath(filename)
    suffix, stem = path.suffix.lower(), path.stem or 'Book'
    if suffix == '.epub' or source.startswith(b'PK\x03\x04'):
        return epub(source, stem)
    text = decoded(source)
    if is_tiddlywiki(text):
        return tiddlywiki(text, stem)
    if suffix in {'.html', '.htm', '.xhtml'}:
        page = Page.read(text)
        return {'format': 'Web page', 'name': page.title or stem, 'sections': page.sections}
    if suffix in {'.md', '.markdown'}:
        return {'format': 'Markdown', 'name': stem, 'sections': split_at(text, MARKDOWN_HEADING, stem)}
    if suffix == '.txt':
        return {'format': 'Plain text', 'name': stem, 'sections': split_at(text, CHAPTER, stem)}
    raise problem(f'Choose a {TYPES}.')


def decoded(source: bytes) -> str:
    try:
        return source.decode('utf-8-sig')
    except UnicodeDecodeError:
        return source.decode('cp1252', errors='replace')


def split_at(text: str, headings: re.Pattern, title: str) -> list[tuple[str, str]]:
    """Sections of a text, each starting at a heading line (kept as the section's title)."""
    marks = list(headings.finditer(text))
    sections = [(title, text[:marks[0].start()] if marks else text)]
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        sections.append((mark.group(1).strip(), text[mark.end():end]))
    return [(name, body) for name, body in sections if body.strip()]


# Web pages and EPUB chapters ------------------------------------------------------------------------------

class Page(HTMLParser):
    """The words of a page, split into sections at its headings."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.sections, self.skipping = '', [], 0
        self.heading, self.words, self.current = None, [], ''

    @classmethod
    def read(cls, text: str, title: str = '') -> 'Page':
        page = cls()
        page.current = title
        page.feed(text)
        page.close()
        page.flush()
        return page

    def handle_starttag(self, tag, attrs):
        if tag in SKIPPED:
            self.skipping += 1
        elif tag in HEADINGS:
            self.flush()
            self.heading = []
        elif tag in BLOCKS:
            self.words.append('\n\n' if tag != 'br' else '\n')

    def handle_endtag(self, tag):
        if tag in SKIPPED:
            self.skipping = max(0, self.skipping - 1)
        elif tag in HEADINGS and self.heading is not None:
            self.current, self.heading = ' '.join(''.join(self.heading).split()) or self.current, None
        elif tag in BLOCKS:
            self.words.append('\n\n')

    def handle_data(self, data):
        if self.skipping:
            if self.lasttag == 'title' and not self.title:
                self.title = ' '.join(data.split())
            return
        (self.heading if self.heading is not None else self.words).append(data)

    def flush(self):
        text = ''.join(self.words)
        if text.strip():
            self.sections.append((self.current, text))
        self.words = []


def epub(source: bytes, stem: str) -> dict:
    try:
        with ZipFile(BytesIO(source)) as archive:
            if sum(entry.file_size for entry in archive.infolist()) > MAX_UNPACKED:
                raise problem('This book unpacks to more than the library takes.')
            opf = rootfile(archive)
            tree = ElementTree.fromstring(archive.read(opf))
            sections = []
            for href in spine(tree):
                path = unquote(posixpath.normpath(posixpath.join(posixpath.dirname(opf), href)))
                if path in archive.namelist():
                    sections += Page.read(decoded(archive.read(path))).sections
    except (BadZipFile, KeyError, ElementTree.ParseError) as error:
        raise problem('This EPUB book could not be read.') from error
    title = next((node.text for node in tree.iter() if node.tag.endswith('}title') and node.text), stem)
    return {'format': 'EPUB book', 'name': title.strip(), 'sections': sections}


def rootfile(archive: ZipFile) -> str:
    container = ElementTree.fromstring(archive.read('META-INF/container.xml'))
    found = next((node.get('full-path') for node in container.iter() if node.tag.endswith('rootfile')), None)
    if not found:
        raise problem('This EPUB book has no table of contents.')
    return found


def spine(tree) -> list[str]:
    """The book's chapters in reading order."""
    items = {node.get('id'): node.get('href') for node in tree.iter() if node.tag.endswith('}item')}
    return [items[node.get('idref')] for node in tree.iter()
            if node.tag.endswith('}itemref') and items.get(node.get('idref'))]


# TiddlyWiki --------------------------------------------------------------------------------------------

def is_tiddlywiki(text: str) -> bool:
    head = text[:4096]
    return 'tiddlywiki' in head.casefold() and ('tiddlywiki-tiddler-store' in text or 'id="storeArea"' in text)


def tiddlywiki(text: str, stem: str) -> dict:
    tiddlers = tiddlers_of(text)
    site = next((item.get('text', '') for item in tiddlers if item.get('title') == '$:/SiteTitle'), '')
    sections = [(title, body) for item in tiddlers if (title := shown_title(item))
                and (body := wikitext(item.get('text', ''))).strip()]
    return {'format': 'TiddlyWiki', 'name': site.strip() or stem, 'sections': sections}


def tiddlers_of(text: str) -> list[dict]:
    """Tiddlers from a TiddlyWiki 5 store (JSON) or an older one (HTML divs)."""
    found = []
    for store in STORE.findall(text):
        try:
            found += [item for item in json.loads(store) if isinstance(item, dict)]
        except json.JSONDecodeError:
            continue
    if found:
        return found
    area = STORE_AREA.search(text)
    for attributes, body in OLD_TIDDLER.findall(area.group(1) if area else ''):
        fields = {key: html.unescape(value) for key, value in re.findall(r'([\w.-]+)="([^"]*)"', attributes)}
        body = re.sub(r'^\s*<pre>|</pre>\s*$', '', body)
        found.append({**fields, 'text': html.unescape(body)})
    return found


def shown_title(item: dict) -> str:
    """A tiddler's title when it is something to read: not the wiki's own machinery, a draft or a picture."""
    title = str(item.get('title') or '').strip()
    if not title or title.startswith('$:/') or title.startswith('Draft of ') or item.get('draft.of'):
        return ''
    if MEDIA.search(title):
        return ''
    return title if str(item.get('type') or '') in TEXT_TYPES else ''


WIKI_RULES = (
    (re.compile(r'<(style|script)\b.*?</\1\s*>', re.S | re.I), ''),
    (re.compile(r'^\\define\b.*?^\\end\b.*?$', re.S | re.M), ''),
    (re.compile(r'^\\\w+.*$', re.M), ''),
    (re.compile(r'<<.*?>>', re.S), ''),
    (re.compile(r'\{\{.*?\}\}', re.S), ''),
    (re.compile(r'\[img[^\]]*\[[^\]]*\]\]'), ''),
    (re.compile(r'!\[[^\]]*\]\([^)]*\)'), ''),
    (re.compile(r'\[ext\[([^|\]]*)\|[^\]]*\]\]'), r'\1'),
    (re.compile(r'\[\[([^|\]]*)\|[^\]]*\]\]'), r'\1'),
    (re.compile(r'\[\[([^\]]*)\]\]'), r'\1'),
    (re.compile(r'\[([^\]]+)\]\([^)]*\)'), r'\1'),
    (re.compile(r'<[^>]+>'), ' '),
    (re.compile(r"''|(?<!:)//|__|~~|\^\^|,,|\*\*|@@[\w.:;#-]*"), ''),
    (re.compile(r'^[ \t]*[!#]+[ \t]*', re.M), ''),
    (re.compile(r'^[ \t]*[*\-][ \t]+', re.M), '- '),
    (re.compile(r'^[ \t]*\|(.*)\|[a-z]?[ \t]*$', re.M), lambda match: '; '.join(
        cell.strip(' !') for cell in match.group(1).split('|') if cell.strip(' !'))),
    (re.compile(r'^[ \t]*(```|""")\w*[ \t]*$', re.M), ''),
)


def wikitext(text: str) -> str:
    """The words of a tiddler: links become their text; macros, widgets, pictures and styling go."""
    for pattern, replacement in WIKI_RULES:
        text = pattern.sub(replacement, text)
    return html.unescape(text)
