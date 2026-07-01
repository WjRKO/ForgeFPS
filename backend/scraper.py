import re
import json
import asyncio
from urllib.parse import urlparse, quote_plus
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"),
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

PRICE_RE = re.compile(r"(?:€|EUR|\$|£|USD)\s?([0-9][0-9\.\,]*)", re.IGNORECASE)


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().replace("www.", "")
        return host.split(":")[0] or "store"
    except Exception:
        return "store"


def _parse_price(text: str):
    if not text:
        return None
    m = PRICE_RE.search(text)
    if not m:
        m = re.search(r"([0-9]{1,3}(?:[\.\,][0-9]{3})*[\.\,][0-9]{2})", text)
        if not m:
            return None
        raw = m.group(1)
    else:
        raw = m.group(1)
    raw = raw.strip()
    # normalize european formatting: 1.299,99 -> 1299.99
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        val = float(raw)
        return round(val, 2)
    except ValueError:
        return None


def _detect_currency(text: str) -> str:
    if "€" in text or "EUR" in text.upper():
        return "EUR"
    if "£" in text:
        return "GBP"
    if "$" in text or "USD" in text.upper():
        return "USD"
    return "EUR"


def _get(url: str):
    return requests.get(url, headers=HEADERS, timeout=15)


def _scrape_sync(url: str) -> dict:
    result = {"url": url, "platform": _domain(url), "title": None,
              "price": None, "currency": "EUR", "image": None, "status": "ok", "error": None}
    try:
        resp = _get(url)
        if resp.status_code in (403, 429, 503):
            result["status"] = "blocked"
            result["error"] = f"Store returned {resp.status_code} (anti-bot). Inserisci il prezzo manualmente."
            return result
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # 1) ld+json structured data
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "{}")
            except Exception:
                continue
            nodes = data if isinstance(data, list) else [data]
            if isinstance(data, dict) and "@graph" in data:
                nodes = data["@graph"]
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                if node.get("@type") in ("Product", "Offer") or "offers" in node:
                    result["title"] = result["title"] or node.get("name")
                    img = node.get("image")
                    if isinstance(img, list):
                        img = img[0] if img else None
                    if isinstance(img, dict):
                        img = img.get("url")
                    result["image"] = result["image"] or img
                    offers = node.get("offers")
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    if isinstance(offers, dict):
                        p = offers.get("price") or offers.get("lowPrice")
                        if p:
                            result["price"] = _parse_price(str(p))
                        cur = offers.get("priceCurrency")
                        if cur:
                            result["currency"] = cur

        # 2) Amazon-specific selectors
        if "amazon" in result["platform"]:
            if not result["title"]:
                t = soup.select_one("#productTitle")
                if t:
                    result["title"] = t.get_text(strip=True)
            if result["price"] is None:
                for sel in ["#corePrice_feature_div .a-offscreen", "span.a-price .a-offscreen",
                            "#priceblock_ourprice", "#priceblock_dealprice"]:
                    el = soup.select_one(sel)
                    if el:
                        result["price"] = _parse_price(el.get_text())
                        result["currency"] = _detect_currency(el.get_text())
                        if result["price"] is not None:
                            break
            if not result["image"]:
                img = soup.select_one("#landingImage") or soup.select_one("#imgBlkFront")
                if img:
                    result["image"] = img.get("src")

        # 3) Generic fallbacks
        if not result["title"]:
            og = soup.find("meta", property="og:title")
            if og and og.get("content"):
                result["title"] = og["content"]
            elif soup.title:
                result["title"] = soup.title.get_text(strip=True)
        if not result["image"]:
            og = soup.find("meta", property="og:image")
            if og and og.get("content"):
                result["image"] = og["content"]
        if result["price"] is None:
            meta_price = soup.find("meta", property="product:price:amount") or \
                soup.find("meta", attrs={"itemprop": "price"})
            if meta_price and meta_price.get("content"):
                result["price"] = _parse_price(meta_price["content"])
            else:
                body_text = soup.get_text(" ", strip=True)[:5000]
                result["price"] = _parse_price(body_text)
                result["currency"] = _detect_currency(body_text)

        if result["title"]:
            result["title"] = result["title"][:200]
        if result["price"] is None:
            result["status"] = "no_price"
            result["error"] = "Prezzo non rilevato. Inseriscilo manualmente."
        return result
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"Impossibile leggere la pagina: {str(e)[:120]}"
        return result


async def scrape_product(url: str) -> dict:
    return await asyncio.to_thread(_scrape_sync, url)


def _search_sync(query: str, limit: int = 8) -> list:
    url = f"https://www.amazon.it/s?k={quote_plus(query)}"
    out = []
    try:
        resp = _get(url)
        if resp.status_code != 200:
            return out
        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.select("div[data-component-type='s-search-result']")
        for c in cards:
            if len(out) >= limit:
                break
            title_el = c.select_one("h2 span") or c.select_one("h2 a span")
            link_el = c.select_one("h2 a") or c.select_one("a.a-link-normal")
            if not title_el or not link_el:
                continue
            href = link_el.get("href", "")
            if href and not href.startswith("http"):
                href = "https://www.amazon.it" + href
            price_el = c.select_one("span.a-price span.a-offscreen")
            img_el = c.select_one("img.s-image")
            out.append({
                "title": title_el.get_text(strip=True)[:200],
                "url": href.split("/ref=")[0] if href else url,
                "price": _parse_price(price_el.get_text()) if price_el else None,
                "currency": "EUR",
                "image": img_el.get("src") if img_el else None,
                "platform": "amazon.it",
            })
    except Exception:
        return out
    return out


async def search_products(query: str, limit: int = 8) -> list:
    return await asyncio.to_thread(_search_sync, query, limit)
