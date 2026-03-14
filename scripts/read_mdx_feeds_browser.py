#!/usr/bin/env python3
"""Read Medoxie MDX Feeds via browser automation.

Designed for OpenClaw-style environments where the target site is client-rendered.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from typing import List, Optional
from urllib.parse import urljoin

DEFAULT_URL = "https://www.medoxie.com/"
WAIT_MS = 18000


@dataclass
class FeedItem:
    title: str
    author: Optional[str] = None
    handle: Optional[str] = None
    relative_time: Optional[str] = None
    summary: Optional[str] = None
    link: Optional[str] = None
    full_text: Optional[str] = None


@dataclass
class Result:
    status: str
    source_url: str
    message: str
    user_message: Optional[str] = None
    items: Optional[List[FeedItem]] = None
    debug: Optional[dict] = None


def _print(result: Result, as_json: bool) -> None:
    if as_json:
        payload = asdict(result)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"status: {result.status}")
    print(f"source_url: {result.source_url}")
    print(result.message)
    if result.user_message:
        print(f"user_message: {result.user_message}")
    if result.items:
        for i, item in enumerate(result.items, 1):
            print(f"\n[{i}] {item.title}")
            if item.author:
                print(f"  author: {item.author}")
            if item.handle:
                print(f"  handle: {item.handle}")
            if item.relative_time:
                print(f"  time: {item.relative_time}")
            if item.summary:
                print(f"  summary: {item.summary}")
            if item.link:
                print(f"  link: {item.link}")
            if item.full_text:
                text = re.sub(r"\s+", " ", item.full_text).strip()
                print(f"  full_text: {text[:700]}{'...' if len(text) > 700 else ''}")


def _import_playwright():
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover
        return None, None, exc
    return sync_playwright, PlaywrightTimeoutError, None


def _extract_items(page, base_url: str, limit: int) -> List[FeedItem]:
    js = """
    () => {
      const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();
      const isPostish = (el) => {
        if (!el) return false;
        const txt = clean(el.innerText || '');
        if (!txt) return false;
        return txt.includes('Read more') || /@[A-Za-z0-9_\.\-]+/.test(txt) || /\b\d+[smhdwyo]+\s+ago\b/i.test(txt);
      };

      const all = [...document.querySelectorAll('section, article, div, main')];
      let scope = all.find(el => /MDX Feeds/i.test(clean(el.innerText || '')));
      if (!scope) {
        const h = [...document.querySelectorAll('h1,h2,h3,h4,button,span,div')].find(el => /MDX Feeds/i.test(clean(el.textContent || '')));
        scope = h ? (h.closest('section,div,main,article') || document.body) : document.body;
      }

      const containers = [...scope.querySelectorAll('article, a, div')]
        .filter(isPostish)
        .slice(0, 50);

      const seen = new Set();
      const items = [];

      for (const el of containers) {
        const txt = clean(el.innerText || '');
        if (!txt || seen.has(txt)) continue;
        seen.add(txt);

        const lines = txt.split(/\n+/).map(clean).filter(Boolean);
        const handle = (txt.match(/@[A-Za-z0-9_\.\-]+/) || [null])[0];
        const relativeTime = (txt.match(/\b\d+\s*(?:s|m|h|d|w|mo|y)\s+ago\b/i) || [null])[0]
          || (txt.match(/\b\d+[smhdwy]\b/i) || [null])[0];

        let title = null;
        for (const line of lines) {
          if (!/^(MDX Feeds|Read more|Open menu)$/i.test(line) && !/^@[A-Za-z0-9_\.\-]+$/.test(line) && !/\bago\b/i.test(line) && line.length > 12) {
            title = line;
            break;
          }
        }
        if (!title && lines.length) title = lines[Math.min(1, lines.length - 1)];

        let author = null;
        for (const line of lines.slice(0, 4)) {
          if (line !== title && !line.startsWith('@') && !/\bago\b/i.test(line) && line.length <= 60) {
            author = line;
            break;
          }
        }

        const anchors = [...el.querySelectorAll('a[href]')];
        const href = anchors.map(a => a.getAttribute('href')).find(Boolean) || (el.closest('a[href]') && el.closest('a[href]').getAttribute('href'));

        const summaryLines = lines.filter(line => line !== title && line !== author && line !== handle && line !== relativeTime && !/^Read more$/i.test(line));
        const summary = summaryLines.join(' ').slice(0, 500) || null;

        if (title) {
          items.push({ title, author, handle, relative_time: relativeTime, summary, link: href });
        }
      }
      return items;
    }
    """
    raw_items = page.evaluate(js)
    items: List[FeedItem] = []
    seen_keys = set()
    for raw in raw_items:
        title = (raw.get("title") or "").strip()
        if not title:
            continue
        key = (title, raw.get("handle"), raw.get("link"))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        link = raw.get("link")
        if link:
            link = urljoin(base_url, link)
        items.append(
            FeedItem(
                title=title,
                author=raw.get("author"),
                handle=raw.get("handle"),
                relative_time=raw.get("relative_time"),
                summary=raw.get("summary"),
                link=link,
            )
        )
        if len(items) >= limit:
            break
    return items


def _extract_full_text(page) -> str:
    js = """
    () => {
      const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();
      const nodes = [...document.querySelectorAll('article, main, section, div')];
      const scored = nodes.map(el => {
        const txt = clean(el.innerText || '');
        return { txt, len: txt.length };
      }).filter(x => x.len > 300).sort((a, b) => b.len - a.len);
      return scored.length ? scored[0].txt : clean(document.body.innerText || '');
    }
    """
    return page.evaluate(js)


def run(url: str, limit: int, full: bool, as_json: bool, headless: bool) -> int:
    sync_playwright, PlaywrightTimeoutError, import_error = _import_playwright()
    if import_error:
        result = Result(
            status="error",
            source_url=url,
            message="Playwright is not installed in this environment.",
            user_message="I need browser automation support to read Medoxie because the feed is rendered after JavaScript runs. Please install Playwright first.",
            debug={"error": repr(import_error), "hint": "pip install playwright && playwright install chromium"},
        )
        _print(result, as_json)
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        debug = {"steps": []}
        try:
            debug["steps"].append("goto")
            page.goto(url, wait_until="domcontentloaded", timeout=WAIT_MS)
            page.wait_for_timeout(1200)

            debug["steps"].append("wait_for_feed_or_ui")
            selectors = [
                "text=MDX Feeds",
                "text=Read more",
                "text=/@[A-Za-z0-9_\\.\\-]+/",
            ]
            visible = False
            for _ in range(8):
                body_text = page.locator("body").inner_text(timeout=4000)
                if any(token in body_text for token in ["MDX Feeds", "Read more", "@"]):
                    visible = True
                    break
                page.wait_for_timeout(1000)

            body_text = page.locator("body").inner_text(timeout=5000)
            trimmed = re.sub(r"\s+", " ", body_text).strip()
            debug["body_excerpt"] = trimmed[:600]

            if re.search(r"(sign in|log in|continue with|verify your email|connect wallet)", trimmed, re.I):
                result = Result(
                    status="needs_user_action",
                    source_url=url,
                    message="Medoxie appears to be asking for authentication or confirmation before the feed can be read.",
                    user_message="Medoxie is asking for sign-in or confirmation. Please complete the visible login or verification step, then tell me to continue.",
                    debug=debug,
                )
                _print(result, as_json)
                browser.close()
                return 0

            items = _extract_items(page, url, limit)
            if not items:
                if len(trimmed) < 80 or re.search(r"(loading|please wait)", trimmed, re.I):
                    result = Result(
                        status="loading",
                        source_url=url,
                        message="The page loaded, but the feed still appears to be rendering.",
                        user_message="Medoxie is still loading its feed. Please try again in a moment.",
                        debug=debug,
                    )
                    _print(result, as_json)
                    browser.close()
                    return 0
                result = Result(
                    status="not_found",
                    source_url=url,
                    message="The page rendered, but the MDX Feeds section could not be confidently located.",
                    user_message="I loaded Medoxie, but I could not confidently find the MDX Feeds section on the rendered page.",
                    debug=debug,
                )
                _print(result, as_json)
                browser.close()
                return 1

            if full:
                for item in items:
                    if not item.link:
                        continue
                    try:
                        post_page = browser.new_page(viewport={"width": 1440, "height": 1200})
                        post_page.goto(item.link, wait_until="domcontentloaded", timeout=WAIT_MS)
                        post_page.wait_for_timeout(1000)
                        item.full_text = _extract_full_text(post_page)
                        post_page.close()
                    except Exception as exc:
                        item.full_text = f"[full text extraction failed: {exc}]"

            result = Result(
                status="ready",
                source_url=url,
                message=f"Extracted {len(items)} MDX feed item(s) from the rendered Medoxie page.",
                items=items,
                debug=debug,
            )
            _print(result, as_json)
            browser.close()
            return 0
        except PlaywrightTimeoutError as exc:
            result = Result(
                status="loading",
                source_url=url,
                message="Timed out while waiting for Medoxie to render.",
                user_message="Medoxie is taking too long to render right now. Please try again shortly.",
                debug={"error": repr(exc), **debug},
            )
            _print(result, as_json)
            browser.close()
            return 1
        except Exception as exc:
            result = Result(
                status="error",
                source_url=url,
                message="Browser extraction failed.",
                user_message="I could not finish reading the Medoxie feed because the browser automation hit an error.",
                debug={"error": repr(exc), **debug},
            )
            _print(result, as_json)
            browser.close()
            return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Read Medoxie MDX Feeds through a browser")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--headed", action="store_true", help="Show the browser window instead of headless mode")
    args = parser.parse_args()
    return run(url=args.url, limit=args.limit, full=args.full, as_json=args.json, headless=not args.headed)


if __name__ == "__main__":
    sys.exit(main())
