"""The story as a book (requirements "Campaign management": "the story of one branch also exports as a readable book
in Markdown, EPUB or PDF"; docs/story.md "Export and legacy").

The branch being played, chapter by chapter (dungeon/chapters.py), with each chapter's title and the player's lines
set apart from the narration. Nothing hidden goes in: no GM notes, no record, no rolls. EPUB and PDF are written
here with the standard library alone: an EPUB 3 zip, and a PDF in the built-in Helvetica faces. The EPUB carries the
pictures made in each chapter (dungeon/art.py): a passage's picture after that passage, the rest where the chapter
opens.
"""
import html
import io
import re
import uuid
import zipfile
import zlib

from dungeon import chapters, timeline
from dungeon.database import many, optional
from dungeon.errors import require

FORMATS = {'md': 'text/markdown; charset=utf-8', 'epub': 'application/epub+zip', 'pdf': 'application/pdf'}
EMPHASIS = re.compile(r'\*\*(.+?)\*\*|\*(.+?)\*|_(.+?)_')


def paragraphs(text: str) -> list[str]:
    return [' '.join(part.split()) for part in re.split(r'\n\s*\n', text or '') if part.strip()]


def pictures(connection, database, chapter_id: str, ends: dict[str, int]) -> list[dict]:
    """The pictures made in a chapter, each with the paragraph it follows (0: where the chapter opens)."""
    if database is None:
        return []
    from dungeon.images import storage
    found = []
    for row in many(connection, "SELECT id, kind, subject, file FROM story_art WHERE chapter_id=? AND status='done' "
                                'ORDER BY created_at', (chapter_id,)):
        try:
            data = storage.path_of(database, row['file']).read_bytes()
        except FileNotFoundError:
            continue
        found.append({'name': row['file'], 'data': data, 'media': storage.TYPES[row['file'].rsplit('.', 1)[1]],
                      'after': ends.get(row['subject'], 0) if row['kind'] == 'passage' else 0})
    return found


def contents(connection, title: str = '', database=None) -> dict:
    """The book: its title, who it is about, and each chapter's paragraphs as (who, text), 'user' for the player's,
    with its pictures when the database is given."""
    persona = optional(connection, 'SELECT name FROM persona WHERE id=1')
    name = (persona and persona['name']) or ''
    result = []
    for chapter in chapters.listing(connection):
        body, ends = [], {}
        for line in chapters.read(connection, chapter['id']):
            if line['role'] in ('user', 'narrator'):
                body += [(line['role'], part) for part in paragraphs(line['text'])]
                ends[line['id']] = len(body)
        if body:
            result.append({'title': chapter['title'], 'number': chapter['number'], 'paragraphs': body,
                           'pictures': pictures(connection, database, chapter['id'], ends)})
    require(bool(result), 'There is no story to export yet.', 409)
    return {'title': title or (f'The story of {name}' if name else 'A story'), 'hero': name, 'chapters': result,
            'branch_id': timeline.active(connection)}


def plain(text: str) -> str:
    return EMPHASIS.sub(lambda match: next(group for group in match.groups() if group is not None), text)


def heading(chapter: dict) -> str:
    return chapter['title'] if chapter['title'] == f"Chapter {chapter['number']}" else \
        f"Chapter {chapter['number']}: {chapter['title']}"


# Markdown ------------------------------------------------------------------------------------------

def markdown(book: dict) -> bytes:
    parts = [f"# {book['title']}", '']
    for chapter in book['chapters']:
        parts += [f'## {heading(chapter)}', '']
        for role, text in chapter['paragraphs']:
            parts += [f'> {text}' if role == 'user' else text, '']
    return '\n'.join(parts).encode('utf-8')


# EPUB ----------------------------------------------------------------------------------------------

CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""
STYLE = """body { font-family: serif; line-height: 1.5; margin: 0 5%; }
h1, h2 { font-family: sans-serif; text-align: center; margin: 2em 0 1em; }
p { margin: 0 0 0.8em; text-indent: 0; }
p.player { font-style: italic; margin-left: 1.5em; }
figure { margin: 1em 0; text-align: center; }
figure img { max-width: 100%; height: auto; }"""


def inline(text: str) -> str:
    """Escaped text, with *emphasis* as <em>."""
    def emphasized(match):
        group = next(group for group in match.groups() if group is not None)
        return f"<{'strong' if match.group(1) else 'em'}>{group}</{'strong' if match.group(1) else 'em'}>"
    return EMPHASIS.sub(emphasized, html.escape(text, quote=False))


def page(title: str, body: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="en" lang="en"><head><meta charset="utf-8"/>'
            f'<title>{html.escape(title)}</title><link rel="stylesheet" href="style.css" type="text/css"/></head>'
            f'<body>{body}</body></html>')


def chapter_body(chapter: dict) -> str:
    """A chapter's paragraphs, with each picture after the paragraph it follows."""
    def figures(after: int) -> str:
        return ''.join(f'<figure><img src="images/{picture["name"]}" alt=""/></figure>'
                       for picture in chapter.get('pictures', []) if picture['after'] == after)
    parts = [figures(0)]
    for number, (role, text) in enumerate(chapter['paragraphs'], 1):
        parts.append(f'<p class="player">{inline(text)}</p>' if role == 'user' else f'<p>{inline(text)}</p>')
        parts.append(figures(number))
    return ''.join(parts)


def epub(book: dict, modified: str) -> bytes:
    """An EPUB 3 book: the mimetype first and stored, then the package, a contents page and one page a chapter."""
    book_id = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, 'prospero-dungeon:' + book['branch_id'])}"
    title = html.escape(book['title'])
    pages = []
    for index, chapter in enumerate(book['chapters'], 1):
        body = f'<h2>{html.escape(heading(chapter))}</h2>' + chapter_body(chapter)
        pages.append((f'chapter-{index}.xhtml', heading(chapter), page(heading(chapter), body)))
    images = [picture for chapter in book['chapters'] for picture in chapter.get('pictures', [])]
    nav = page(book['title'], f'<h1>{title}</h1><nav epub:type="toc" id="toc"><ol>' + ''.join(
        f'<li><a href="{name}">{html.escape(label)}</a></li>' for name, label, _ in pages) + '</ol></nav>')
    manifest = ''.join(f'<item id="c{index}" href="{name}" media-type="application/xhtml+xml"/>'
                       for index, (name, _, _) in enumerate(pages, 1)) + ''.join(
        f'<item id="i{index}" href="images/{picture["name"]}" media-type="{picture["media"]}"/>'
        for index, picture in enumerate(images, 1))
    spine = ''.join(f'<itemref idref="c{index}"/>' for index in range(1, len(pages) + 1))
    author = f"<dc:creator>{html.escape(book['hero'])}</dc:creator>" if book['hero'] else ''
    opf = ('<?xml version="1.0" encoding="UTF-8"?>\n<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
           'unique-identifier="book-id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
           f'<dc:identifier id="book-id">{book_id}</dc:identifier><dc:title>{title}</dc:title>{author}'
           f'<dc:language>en</dc:language><meta property="dcterms:modified">{modified[:19]}Z</meta></metadata>'
           '<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
           f'<item id="style" href="style.css" media-type="text/css"/>{manifest}</manifest>'
           f'<spine><itemref idref="nav"/>{spine}</spine></package>')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as handle:
        handle.writestr(zipfile.ZipInfo('mimetype'), 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        for name, text in [('META-INF/container.xml', CONTAINER), ('OEBPS/content.opf', opf),
                           ('OEBPS/nav.xhtml', nav), ('OEBPS/style.css', STYLE),
                           *((f'OEBPS/{name}', text) for name, _, text in pages)]:
            handle.writestr(name, text, compress_type=zipfile.ZIP_DEFLATED)
        for picture in images:
            handle.writestr(f"OEBPS/images/{picture['name']}", picture['data'], compress_type=zipfile.ZIP_STORED)
    return buffer.getvalue()


# PDF -----------------------------------------------------------------------------------------------

# Helvetica's widths (thousandths of the font size) for printable ASCII, from its standard metrics.
WIDTHS = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, *[556] * 10, 278, 278,
          584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667,
          778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556,
          278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500,
          334, 260, 334, 584]
WIDE = {'—': 1000, '…': 1000, '–': 556, '‘': 222, '’': 222, '“': 333, '”': 333}
# A 6 by 9 inch page, in points.
WIDTH, HEIGHT, MARGIN = 432, 648, 54
SIZE, LEADING = 10.5, 15
FONTS = {'body': 'Helvetica', 'player': 'Helvetica-Oblique', 'heading': 'Helvetica-Bold'}


def measure(text: str, size: float, bold: bool = False) -> float:
    width = sum(WIDE.get(char) or (WIDTHS[ord(char) - 32] if 32 <= ord(char) < 127 else 556) for char in text)
    return width * size / 1000 * (1.08 if bold else 1)


def wrap(text: str, size: float, room: float, bold: bool = False) -> list[str]:
    lines, line = [], ''
    for word in text.split():
        trial = f'{line} {word}' if line else word
        if line and measure(trial, size, bold) > room:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line] if line else lines


def escaped(text: str) -> str:
    raw = text.encode('cp1252', errors='replace').decode('latin-1')
    return raw.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def laid_out(book: dict) -> list[list[tuple[str, float, float, float, str]]]:
    """Every page as its runs of text: (font, size, x, y, text). Each chapter starts a page."""
    pages, room = [], WIDTH - 2 * MARGIN
    runs, y = [], 0.0

    def new_page():
        nonlocal runs, y
        runs = []
        pages.append(runs)
        y = HEIGHT - MARGIN

    def put(text: str, font: str, size: float, x: float, leading: float, before: float = 0):
        nonlocal y
        for number, line in enumerate(wrap(text, size, room - (x - MARGIN), font == 'heading')):
            if y - leading < MARGIN:
                new_page()
            elif number == 0:
                y -= before
            y -= leading
            runs.append((font, size, x, y, line))

    new_page()
    put(book['title'], 'heading', 20, MARGIN, 28, 120)
    for chapter in book['chapters']:
        new_page()
        put(heading(chapter), 'heading', 14, MARGIN, 20, 24)
        y -= 12
        for role, text in chapter['paragraphs']:
            player = role == 'user'
            put(plain(text), 'player' if player else 'body', SIZE, MARGIN + (18 if player else 0), LEADING, 6)
    return pages


def pdf(book: dict) -> bytes:
    pages = laid_out(book)
    objects: list[bytes] = []
    fonts = {key: 3 + index for index, key in enumerate(FONTS)}
    first_page = 3 + len(FONTS)
    kids = ' '.join(f'{first_page + 2 * index} 0 R' for index in range(len(pages)))
    objects.append(b'<< /Type /Catalog /Pages 2 0 R >>')
    objects.append(f'<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>'.encode())
    for name in FONTS.values():
        objects.append(f'<< /Type /Font /Subtype /Type1 /BaseFont /{name} /Encoding /WinAnsiEncoding >>'.encode())
    resources = ' '.join(f'/F{number} {number} 0 R' for number in fonts.values())
    for number, runs in enumerate(pages, 1):
        text = ''.join(f'BT /F{fonts[font]} {size} Tf {x:.1f} {y:.1f} Td ({escaped(line)}) Tj ET\n'
                       for font, size, x, y, line in runs)
        text += f'BT /F{fonts["body"]} 9 Tf {WIDTH / 2 - 4:.1f} {MARGIN / 2:.1f} Td ({number}) Tj ET\n' if number > 1 else ''
        stream = zlib.compress(text.encode('latin-1'))
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {WIDTH} {HEIGHT}] /Resources << /Font << '
                       f'{resources} >> >> /Contents {len(objects) + 2} 0 R >>'.encode())
        objects.append(f'<< /Length {len(stream)} /Filter /FlateDecode >>\nstream\n'.encode() + stream +
                       b'\nendstream')
    out = io.BytesIO()
    out.write(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(f'{number} 0 obj\n'.encode() + body + b'\nendobj\n')
    start = out.tell()
    out.write(f'xref\n0 {len(objects) + 1}\n0000000000 65535 f \n'.encode())
    out.write(''.join(f'{offset:010d} 00000 n \n' for offset in offsets).encode())
    out.write(f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode())
    return out.getvalue()


def export(connection, kind: str, now: str, title: str = '', database=None) -> tuple[bytes, str]:
    require(kind in FORMATS, 'A book exports as md, epub or pdf.', 422)
    book = contents(connection, title, database if kind == 'epub' else None)
    data = markdown(book) if kind == 'md' else epub(book, now) if kind == 'epub' else pdf(book)
    return data, FORMATS[kind]
