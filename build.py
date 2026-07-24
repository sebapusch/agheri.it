#!/usr/bin/env python3
from __future__ import annotations

import html
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).parent
SRC = ROOT / "src"
CONTENT = SRC / "content"
LAYOUT = SRC / "layouts" / "base.html"
ASSETS = SRC / "assets"
DIST = ROOT / "dist"

NAV = {
    "de": [
        ("home", "Home", "/de/"),
        ("services", "Leistungen", "/de/leistungen/"),
        ("specialties", "Fachgebiete", "/de/fachgebiete/"),
        ("contact", "Kontakt", "/de/kontakt/"),
        ("links", "Weblinks", "/de/weblinks/"),
    ],
    "it": [
        ("home", "Home", "/it/"),
        ("services", "Servizi Offerti", "/it/servizi/"),
        ("specialties", "Specializzazioni", "/it/specializzazioni/"),
        ("contact", "Contatti", "/it/contatti/"),
        ("links", "Link", "/it/link/"),
    ],
}

LANG_SWITCH = {
    "de": {
        "home": "/it/",
        "services": "/it/servizi/",
        "specialties": "/it/specializzazioni/",
        "contact": "/it/contatti/",
        "links": "/it/link/",
        "impressum": "/it/impressum/",
        "disclaimer": "/it/disclaimer/",
    },
    "it": {
        "home": "/de/",
        "services": "/de/leistungen/",
        "specialties": "/de/fachgebiete/",
        "contact": "/de/kontakt/",
        "links": "/de/weblinks/",
        "impressum": "/de/impressum/",
        "disclaimer": "/de/disclaimer/",
    },
}


def parse_front_matter(raw: str) -> tuple[dict[str, str], str]:
    if not raw.startswith("---\n"):
        return {}, raw
    end = raw.find("\n---\n", 4)
    if end == -1:
        raise ValueError("Unclosed front matter block")
    meta: dict[str, str] = {}
    for line in raw[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"')
    return meta, raw[end + 5 :]


def inline_markdown(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def render_markdown(markdown: str) -> str:
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            lines = [inline_markdown(line) for line in paragraph]
            blocks.append("<p>" + "<br>\n".join(lines) + "</p>")
            paragraph = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            blocks.append("<ul>\n" + "\n".join(list_items) + "\n</ul>")
            list_items = []

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_list()
            continue
        if stripped.startswith("#"):
            flush_paragraph()
            flush_list()
            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped[level:].strip()
            if 1 <= level <= 6 and title:
                blocks.append(f"<h{level}>{inline_markdown(title)}</h{level}>")
                continue
        if stripped.startswith("- "):
            flush_paragraph()
            list_items.append(f"<li>{inline_markdown(stripped[2:].strip())}</li>")
            continue
        flush_list()
        paragraph.append(stripped)

    flush_paragraph()
    flush_list()
    return "\n".join(blocks)


def read_pages() -> list[tuple[Path, dict[str, str], str]]:
    pages = []
    for path in sorted(CONTENT.rglob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta, body = parse_front_matter(raw)
        if meta.get("build", "true").lower() == "false":
            continue
        if "path" not in meta:
            continue
        pages.append((path, meta, body))
    return pages


def read_keywords() -> dict[str, str]:
    raw = (CONTENT / "keywords.md").read_text(encoding="utf-8")
    _, body = parse_front_matter(raw)
    keywords: dict[str, list[str]] = {}
    current = ""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            current = stripped[3:].strip()
            keywords[current] = []
        elif current and stripped.startswith("- "):
            keywords[current].append(stripped[2:].strip())
    return {key: ", ".join(items) for key, items in keywords.items()}


def render_nav(lang: str, active: str) -> str:
    items = []
    for key, label, url in NAV.get(lang, []):
        class_name = "active" if key == active else ""
        items.append(f'<a class="{class_name}" href="{url}">{html.escape(label)}</a>')
    return "\n".join(items)


def render_lang_switch(lang: str, active: str) -> str:
    def flag_link(code: str, label: str, url: str, current: bool = False) -> str:
        flag = f'<span class="flag flag-{code}" aria-hidden="true"></span>'
        text = f'<span class="visually-hidden">{label}</span>'
        if current:
            return f'<span class="flag-link current" aria-current="true">{flag}{text}</span>'
        return f'<a class="flag-link" href="{url}">{flag}{text}</a>'

    if lang not in ("de", "it"):
        return (
            flag_link("de", "Deutsch", "/de/")
            + flag_link("it", "Italiano", "/it/")
        )
    other = "it" if lang == "de" else "de"
    other_url = LANG_SWITCH.get(lang, {}).get(active, f"/{other}/")
    de_url = "/de/" if lang == "de" else other_url
    it_url = other_url if lang == "de" else "/it/"
    de = flag_link("de", "Deutsch", de_url, current=lang == "de")
    it = flag_link("it", "Italiano", it_url, current=lang == "it")
    return de + it


def output_path(url_path: str) -> Path:
    clean = url_path.strip("/")
    if not clean:
        return DIST / "index.html"
    return DIST / clean / "index.html"


def build() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    shutil.copytree(ASSETS, DIST / "assets")

    layout = LAYOUT.read_text(encoding="utf-8")
    keywords = read_keywords()

    for source, meta, body in read_pages():
        lang = meta.get("lang", "en")
        active = meta.get("nav", "")
        rendered = layout
        image = meta.get("image", "")
        image_html = ""
        if image:
            alt = html.escape(meta.get("image_alt", ""))
            image_html = f'<aside class="page-image"><img src="{image}" alt="{alt}"></aside>'

        replacements = {
            "lang": lang,
            "title": meta.get("title", ""),
            "description": meta.get("description", ""),
            "keywords": keywords.get(meta.get("keywords", lang), ""),
            "body_class": meta.get("body_class", "page"),
            "nav": render_nav(lang, active),
            "lang_switch": render_lang_switch(lang, active),
            "content": render_markdown(body),
            "image": image_html,
            "footer_impressum": f"/{lang}/impressum/" if lang in ("de", "it") else "/de/impressum/",
            "footer_disclaimer": f"/{lang}/disclaimer/" if lang in ("de", "it") else "/de/disclaimer/",
        }
        for key, value in replacements.items():
            rendered = rendered.replace("{{ " + key + " }}", value)

        target = output_path(meta["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    build()
