import re
import json
import asyncio
from urllib.parse import urlparse, quote_plus
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,image/apng,*/*;q=0.8"),
    "Accept-Encoding": "gzip, deflate",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

PRICE_RE = re.compile(r"(?:€|EUR|\$|£|USD)\s?([0-9][0-9\.\,]*)", re.IGNORECASE)

# Friendly store names for known domains (keyword -> label)
STORE_NAMES = {
    "amazon": "Amazon", "ebay": "eBay", "mediaworld": "MediaWorld", "unieuro": "Unieuro",
    "euronics": "Euronics", "eprice": "ePRICE", "monclick": "Monclick", "newegg": "Newegg",
    "bestbuy": "Best Buy", "aliexpress": "AliExpress", "trovaprezzi": "Trovaprezzi",
    "aksist": "AK Informatica", "drako": "Drako", "nexths": "Next", "bpm-power": "BPM Power",
}

# Per-store DOM selectors (best-effort, used on top of ld+json / OpenGraph)
STORE_SELECTORS = {
    "amazon": {
        "title": ["#productTitle", "#title span"],
        "price": ["#corePriceDisplay_desktop_feature_div span.a-offscreen",
                  "#corePrice_feature_div span.a-offscreen", "span.a-price span.a-offscreen",
                  "#priceblock_ourprice", "#priceblock_dealprice", "#sns-base-price"],
        "image": ["#landingImage", "#imgBlkFront", "#main-image"],
    },
    "ebay": {
        "title": ["h1.x-item-title__mainTitle span", "#itemTitle", "h1 span.ux-textspans"],
        "price": [".x-price-primary span.ux-textspans", "#prcIsum", "#mm-saleDscPrc"],
        "image": ["#icImg", "img.ux-image-magnify__image--original"],
    },
    "mediaworld": {"title": ["h1"], "price": ["[data-test='product-price']", "[class*='Price']", ".price"], "image": []},
    "unieuro": {"title": ["h1.product-name", "h1"], "price": [".product-price", "[class*='price']"], "image": []},
    "euronics": {"title": ["h1"], "price": [".price", "[class*='price']"], "image": []},
    "eprice": {"title": ["h1"], "price": [".product-price", ".price"], "image": []},
    "newegg": {"title": ["h1.product-title"], "price": [".price-current strong", ".product-price .price-current"], "image": []},
    "bestbuy": {"title": ["h1.heading-5"], "price": [".priceView-customer-price span"], "image": []},
}


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().replace("www.", "")
        return host.split(":")[0] or "store"
    except Exception:
        return "store"


def _store_key(domain: str):
    for key in STORE_SELECTORS:
        if key in domain:
            return key
    return None


def _store_label(domain: str) -> str:
    for kw, label in STORE_NAMES.items():
        if kw in domain:
            return label
    return domain


def _clean_title(title: str) -> str:
    if not title:
        return title
    t = title.strip()
    # Strip common store prefixes/suffixes from <title>
    t = re.sub(r"^\s*Amazon\.[a-z.]+\s*[:\-]\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*[:\-|]\s*Amazon\.[a-z.]+.*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*[|\-–]\s*(eBay|MediaWorld|Unieuro|Euronics|ePRICE|Newegg|Best Buy).*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip(" -|:")
    return t[:200]


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
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return round(float(raw), 2)
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


def _first_text(soup, selectors):
    for sel in selectors or []:
        try:
            el = soup.select_one(sel)
        except Exception:
            continue
        if el:
            txt = el.get_text(strip=True)
            if txt:
                return txt
    return None


def _scrape_sync(url: str) -> dict:
    domain = _domain(url)
    result = {"url": url, "platform": domain, "store": _store_label(domain), "title": None,
              "price": None, "currency": "EUR", "image": None, "status": "ok", "error": None}
    try:
        resp = _get(url)
        if resp.status_code in (403, 429, 503):
            result["status"] = "blocked"
            result["error"] = f"Lo store ha risposto {resp.status_code} (anti-bot). Inserisci nome e prezzo manualmente."
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
                        if p and result["price"] is None:
                            result["price"] = _parse_price(str(p))
                        cur = offers.get("priceCurrency")
                        if cur:
                            result["currency"] = cur

        # 2) Per-store DOM selectors
        skey = _store_key(domain)
        if skey:
            sel = STORE_SELECTORS[skey]
            if not result["title"]:
                result["title"] = _first_text(soup, sel.get("title"))
            if result["price"] is None:
                ptxt = _first_text(soup, sel.get("price"))
                if ptxt:
                    result["price"] = _parse_price(ptxt)
                    result["currency"] = _detect_currency(ptxt)
            if not result["image"]:
                for isel in sel.get("image", []):
                    el = soup.select_one(isel)
                    if el and el.get("src"):
                        result["image"] = el.get("src")
                        break

        # 3) Generic fallbacks (OpenGraph / meta / body)
        if not result["title"]:
            og = soup.find("meta", property="og:title")
            tw = soup.find("meta", attrs={"name": "twitter:title"})
            if og and og.get("content"):
                result["title"] = og["content"]
            elif tw and tw.get("content"):
                result["title"] = tw["content"]
            elif soup.title:
                result["title"] = soup.title.get_text(strip=True)
        if not result["image"]:
            og = soup.find("meta", property="og:image")
            if og and og.get("content"):
                result["image"] = og["content"]
        if result["price"] is None:
            for finder in (
                lambda: soup.find("meta", property="product:price:amount"),
                lambda: soup.find("meta", attrs={"itemprop": "price"}),
                lambda: soup.find("meta", property="og:price:amount"),
                lambda: soup.find("meta", attrs={"name": "twitter:data1"}),
            ):
                mp = finder()
                if mp and mp.get("content"):
                    result["price"] = _parse_price(mp["content"])
                    if result["price"] is not None:
                        break
        if result["price"] is None:
            # embedded JSON like "price":"1299.99" or "priceAmount":1299.99
            m = re.search(r'"(?:price|priceAmount|lowPrice)"\s*:\s*"?([0-9]+(?:[\.,][0-9]{1,2})?)"?', resp.text)
            if m:
                result["price"] = _parse_price(m.group(1))
        if result["price"] is None:
            body_text = soup.get_text(" ", strip=True)[:6000]
            result["price"] = _parse_price(body_text)
            result["currency"] = _detect_currency(body_text)

        result["title"] = _clean_title(result["title"]) if result["title"] else None
        if not result["title"]:
            result["status"] = "no_title"
            result["error"] = "Nome non rilevato. Modificalo manualmente."
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


def _search_amazon(query: str, limit: int) -> list:
    url = f"https://www.amazon.it/s?k={quote_plus(query)}"
    out = []
    try:
        resp = _get(url)
        if resp.status_code != 200:
            return out
        soup = BeautifulSoup(resp.text, "lxml")
        for c in soup.select("div[data-component-type='s-search-result']"):
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
                "currency": "EUR", "image": img_el.get("src") if img_el else None,
                "platform": "amazon.it", "store": "Amazon",
            })
    except Exception:
        return out
    return out


def _search_ebay(query: str, limit: int) -> list:
    url = f"https://www.ebay.it/sch/i.html?_nkw={quote_plus(query)}"
    out = []
    try:
        resp = _get(url)
        if resp.status_code != 200:
            return out
        soup = BeautifulSoup(resp.text, "lxml")
        for c in soup.select("li.s-item"):
            if len(out) >= limit:
                break
            title_el = c.select_one(".s-item__title")
            link_el = c.select_one("a.s-item__link")
            if not title_el or not link_el:
                continue
            title = title_el.get_text(strip=True)
            if not title or "Shop on eBay" in title:
                continue
            price_el = c.select_one(".s-item__price")
            img_el = c.select_one(".s-item__image-img") or c.select_one("img")
            img = img_el.get("src") or img_el.get("data-src") if img_el else None
            out.append({
                "title": title[:200], "url": link_el.get("href", "").split("?")[0],
                "price": _parse_price(price_el.get_text()) if price_el else None,
                "currency": "EUR", "image": img, "platform": "ebay.it", "store": "eBay",
            })
    except Exception:
        return out
    return out


def _search_sync(query: str, limit: int = 10) -> list:
    per = max(3, limit // 2)
    results = _search_amazon(query, per) + _search_ebay(query, limit - per)
    return results[:limit]


async def search_products(query: str, limit: int = 10) -> list:
    return await asyncio.to_thread(_search_sync, query, limit)
