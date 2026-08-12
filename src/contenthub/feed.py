"""Fetch and parse the Shoptet Heureka XML product feed."""
from __future__ import annotations

import logging
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests

from .config import USER_AGENT

log = logging.getLogger(__name__)


def strip_diacritics(s: str) -> str:
    """Lowercase + remove Czech diacritics so keyword rules stay simple."""
    return "".join(
        c
        for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


@dataclass
class Product:
    item_id: str
    name: str
    url: str
    img: str
    price_vat: str  # raw feed string, e.g. "1090,00"
    manufacturer: str
    category: str  # full CATEGORYTEXT path
    blob: str  # normalized searchable text
    in_stock: bool = True  # DELIVERY_DATE == 0 (ships immediately)

    @property
    def price_czk(self) -> str:
        """'1090,00' -> '1 090 Kč' (best effort; falls back to raw)."""
        raw = self.price_vat.replace("\xa0", "").replace(" ", "")
        try:
            value = float(raw.replace(",", "."))
            whole = f"{int(round(value)):,}".replace(",", " ")
            return f"{whole} Kč"
        except ValueError:
            return f"{self.price_vat} Kč"


def parse_feed(xml_bytes: bytes) -> list[Product]:
    root = ET.fromstring(xml_bytes)
    products: list[Product] = []
    for it in root.findall("SHOPITEM"):
        get = lambda tag: (it.findtext(tag) or "").strip()  # noqa: E731
        name = get("PRODUCTNAME")
        if not name:
            continue
        category = get("CATEGORYTEXT")
        manufacturer = get("MANUFACTURER")
        products.append(
            Product(
                item_id=get("ITEM_ID"),
                name=name,
                url=get("URL"),
                img=get("IMGURL"),
                price_vat=get("PRICE_VAT"),
                manufacturer=manufacturer,
                category=category,
                blob=strip_diacritics(f"{name} {category} {manufacturer}"),
                in_stock=get("DELIVERY_DATE") == "0",  # 0 = skladem, expeduje hned
            )
        )
    log.info("Parsed %d products from feed", len(products))
    return products


def load_products(feed_url: str, timeout: int = 60) -> list[Product]:
    resp = requests.get(feed_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return parse_feed(resp.content)
