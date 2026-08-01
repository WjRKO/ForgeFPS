import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import i18n from "@/i18n";

const CANONICAL_ORIGIN = "https://forgefps.dev";

const ensure = (selector, create) => {
  let el = document.head.querySelector(selector);
  if (!el) { el = create(); document.head.appendChild(el); }
  return el;
};

const setMeta = (attr, key, content) => {
  if (!content) return;
  const el = ensure(`meta[${attr}="${key}"]`, () => {
    const m = document.createElement("meta");
    m.setAttribute(attr, key);
    return m;
  });
  el.setAttribute("content", content);
};

const setLink = (rel, href, hreflang) => {
  const sel = hreflang ? `link[rel="${rel}"][hreflang="${hreflang}"]` : `link[rel="${rel}"]:not([hreflang])`;
  const el = ensure(sel, () => {
    const l = document.createElement("link");
    l.setAttribute("rel", rel);
    if (hreflang) l.setAttribute("hreflang", hreflang);
    return l;
  });
  el.setAttribute("href", href);
};

export function usePageMeta(title, description) {
  const { pathname } = useLocation();
  useEffect(() => {
    if (title) document.title = title;
    if (description) setMeta("name", "description", description);
    setMeta("property", "og:title", title);
    setMeta("property", "og:description", description);
    setMeta("name", "twitter:title", title);
    setMeta("name", "twitter:description", description);
    const lang = (i18n.resolvedLanguage || i18n.language || "it").slice(0, 2);
    setMeta("property", "og:locale", lang === "en" ? "en_US" : "it_IT");
    setMeta("property", "og:locale:alternate", lang === "en" ? "it_IT" : "en_US");
    // Canonical + hreflang alternates (?lang=) sull'URL di produzione
    const base = `${CANONICAL_ORIGIN}${pathname === "/" ? "/" : pathname}`;
    setLink("canonical", base);
    setMeta("property", "og:url", base);
    setLink("alternate", `${base}${base.includes("?") ? "&" : "?"}lang=it`, "it");
    setLink("alternate", `${base}${base.includes("?") ? "&" : "?"}lang=en`, "en");
    setLink("alternate", base, "x-default");
  }, [title, description, pathname]);
}
