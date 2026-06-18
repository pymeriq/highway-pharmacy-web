#!/usr/bin/env python3
"""Validate the committed Cloudflare Pages static deployment."""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ERRORS: list[str] = []


def check(condition: bool, message: str) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"{status}: {message}")
    if not condition:
        ERRORS.append(message)


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.hrefs: list[str] = []
        self.image_srcs: list[str] = []
        self.copy_keys: set[str] = set()
        self.alt_keys: set[str] = set()
        self.fallback_keys: set[str] = set()
        self.json_ld: list[dict] = []
        self.meta: dict[tuple[str, str], str] = {}
        self.links: list[dict[str, str]] = []
        self.html_lang = ""
        self.title = ""
        self._in_json = False
        self._in_title = False
        self._buffer = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key: value or "" for key, value in attrs}
        if tag == "html":
            self.html_lang = data.get("lang", "")
        if "id" in data:
            self.ids.add(data["id"])
        if "href" in data:
            self.hrefs.append(data["href"])
        if tag == "img" and "src" in data:
            self.image_srcs.append(data["src"])
        for attr, target in (
            ("data-copy", self.copy_keys),
            ("data-alt-copy", self.alt_keys),
            ("data-fallback-copy", self.fallback_keys),
        ):
            if attr in data:
                target.add(data[attr])
        if tag == "meta":
            for key in ("name", "property"):
                if key in data:
                    self.meta[(key, data[key])] = data.get("content", "")
        if tag == "link":
            self.links.append(data)
        if tag == "title":
            self._in_title = True
            self._buffer = ""
        if tag == "script" and data.get("type") == "application/ld+json":
            self._in_json = True
            self._buffer = ""

    def handle_data(self, data: str) -> None:
        if self._in_json or self._in_title:
            self._buffer += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_json:
            self.json_ld.append(json.loads(self._buffer))
            self._in_json = False
        if tag == "title" and self._in_title:
            self.title = self._buffer.strip()
            self._in_title = False


def parse_html(path: Path) -> SiteParser:
    parser = SiteParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


required_root_files = [
    "index.html",
    "en/index.html",
    "es/index.html",
    "styles.css",
    "app.js",
    "_redirects",
    "assets",
    "robots.txt",
    "sitemap.xml",
]
check(all((ROOT / path).exists() for path in required_root_files), "deployment root files are present")
try:
    ET.parse(ROOT / "sitemap.xml")
    sitemap_valid = True
except ET.ParseError:
    sitemap_valid = False
check(sitemap_valid, "sitemap.xml is valid XML")

required_images = [
    "logo-highway.png",
    "icono-highway.png",
    "hero-exterior.jpg",
    "autofarmacia.jpg",
    "recetario.jpg",
    "interior-general.jpg",
    "interior-general1.jpg",
    "jugueteria-header.png",
    "jugueteria-shelf.jpg",
    "regalo.jpg",
    "regalo1.jpg",
    "regalo2.jpg",
    "regalo3.jpg",
    "regalo4.jpg",
    "regalo5.jpg",
]
check(all((ROOT / "assets" / image).is_file() for image in required_images), "required owner-provided images exist")

redirect_lines = {
    line.strip()
    for line in (ROOT / "_redirects").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.lstrip().startswith("#")
}
check("/ /es/ 302" in redirect_lines, "root redirects to the Spanish homepage")
check("/en/* /en/index.html 200" in redirect_lines, "English localized routes fallback to en/index.html")
check("/es/* /es/index.html 200" in redirect_lines, "Spanish localized routes fallback to es/index.html")
check(not any(line.startswith("/* ") for line in redirect_lines), "root assets are not swallowed by a global SPA fallback")

root_parser = parse_html(ROOT / "index.html")
en_parser = parse_html(ROOT / "en/index.html")
es_parser = parse_html(ROOT / "es/index.html")

check(en_parser.html_lang == "en" and es_parser.html_lang == "es", "localized entry documents declare the correct language")
check("Pharmacy in Santa Isabel" in en_parser.title, "English entry document has localized title")
check("Farmacia en Santa Isabel" in es_parser.title, "Spanish entry document has localized title")
check(en_parser.meta.get(("property", "og:locale")) == "en_US", "English Open Graph locale is correct")
check(es_parser.meta.get(("property", "og:locale")) == "es_PR", "Spanish Open Graph locale is correct")
check(
    any(link.get("rel") == "canonical" and link.get("href") == "https://highwaypharmacypr.com/en/" for link in en_parser.links)
    and any(link.get("rel") == "canonical" and link.get("href") == "https://highwaypharmacypr.com/es/" for link in es_parser.links),
    "localized canonical URLs are present",
)
check(
    all(
        any(link.get("hreflang") == lang for link in parser.links)
        for parser in (en_parser, es_parser)
        for lang in ("en", "es", "x-default")
    ),
    "localized entry documents contain hreflang links",
)

app_js = (ROOT / "app.js").read_text(encoding="utf-8")
styles_css = (ROOT / "styles.css").read_text(encoding="utf-8")
deploy_text = "\n".join(
    [
        (ROOT / "index.html").read_text(encoding="utf-8"),
        (ROOT / "en/index.html").read_text(encoding="utf-8"),
        (ROOT / "es/index.html").read_text(encoding="utf-8"),
        app_js,
        styles_css,
    ]
)

content_body = app_js.split("const content = {", 1)[1].split("\n};\n\nconst icons", 1)[0]
es_content = content_body.split("  es: {", 1)[1].split("\n  },\n  en: {", 1)[0]
en_content = content_body.split("\n  en: {", 1)[1]
key_pattern = re.compile(r"^    ([A-Za-z][A-Za-z0-9]*):", re.MULTILINE)
es_keys = set(key_pattern.findall(es_content))
en_keys = set(key_pattern.findall(en_content))
bindings = root_parser.copy_keys | root_parser.alt_keys | root_parser.fallback_keys
check(es_keys == en_keys, "EN/ES translation keys match")
check(not (bindings - es_keys) and not (bindings - en_keys), "all HTML translation bindings exist")

asset_refs = set(re.findall(r'["\'](/assets/[A-Za-z0-9._-]+)', deploy_text))
missing_assets = sorted(path for path in asset_refs if not (ROOT / path.lstrip("/")).is_file())
check(not missing_assets, f"all /assets references resolve ({len(asset_refs)} unique assets)")
check(
    all(f"/assets/{image}" in deploy_text for image in required_images),
    "all required owner images are referenced",
)
check(
    all(src.startswith("/assets/") for src in root_parser.image_srcs),
    "all rendered image sources use root-relative /assets paths",
)

missing_anchors = sorted({href[1:] for href in root_parser.hrefs if href.startswith("#")} - root_parser.ids)
check(not missing_anchors, "internal anchors resolve")
check(
    all(route in app_js for route in ("services", "servicios", "history", "historia", "contact", "contacto", "promotions", "promociones")),
    "localized navigation routes are defined",
)
check(
    all(token in app_js for token in ("canonicalUrl", 'meta[property="og:url"]', 'link[hreflang="es"]', 'link[hreflang="en"]', "localizedPath(target)")),
    "runtime updates canonical, Open Graph, hreflang, and language-switch routes",
)
check(
    all(
        link in deploy_text
        for link in (
            'href="tel:+17878456272"',
            'href="https://wa.me/19394196449"',
            "https://www.google.com/maps/search/?api=1&query=Highway+Pharmacy+Santa+Isabel+PR",
        )
    ),
    "mobile action dock call, WhatsApp, and directions links are present",
)
check(
    'action="mailto:highwayrx@gmail.com"' in deploy_text and "formNote" in app_js,
    "contact form is mailto-based and clearly disclosed",
)

for name, parser in (("root", root_parser), ("English", en_parser), ("Spanish", es_parser)):
    check(bool(parser.json_ld), f"{name} entry document contains structured data")
    if not parser.json_ld:
        continue
    schema = parser.json_ld[0]
    contacts = schema.get("contactPoint", [])
    hours = schema.get("openingHoursSpecification", [])
    sunday = next((item for item in hours if item.get("dayOfWeek") == "Sunday"), None)
    check(schema.get("name") == "Farmacias Aliadas Highway Pharmacy", f"{name} schema business name is correct")
    check(
        schema.get("address", {}).get("streetAddress") == "Plaza Oasis, Carr. 153 km 6.9, Edificio B Local B3",
        f"{name} schema address is correct",
    )
    check(schema.get("telephone") == "+1-787-845-6272" and schema.get("email") == "highwayrx@gmail.com", f"{name} schema phone and email are correct")
    check(any(item.get("telephone") == "+1-939-419-6449" for item in contacts), f"{name} schema WhatsApp contact is correct")
    check(len(hours) == 3 and sunday is not None and "opens" not in sunday, f"{name} schema hours include Sunday closed")

banned_refs = (
    "highway-pharmacy-hero",
    "generated_images",
    "image_gen",
    "unsplash",
    "pexels",
    "pixabay",
    "stock pharmacy",
    "ai-generated",
)
check(not any(ref in deploy_text.lower() for ref in banned_refs), "no generated or stock image references remain")
ecommerce_refs = (
    "shop " + "online",
    "comprar " + "en línea",
    "online " + "store",
    "tienda " + "en línea",
    "shopping " + "experience",
    "compra " + "en línea",
    "sin " + "receta",
)
check(not any(ref in deploy_text.lower() for ref in ecommerce_refs), "no ecommerce wording or old Spanish OTC wording remains")
check(styles_css.count("{") == styles_css.count("}"), "CSS braces are balanced")

if ERRORS:
    print(f"\nValidation failed with {len(ERRORS)} issue(s).")
    sys.exit(1)

print("\nCloudflare Pages deployment validation passed.")
