#!/usr/bin/env python3
"""Publish Continental News posts to a WhatsApp Web group.

First-run safe mode:
  python whatsapp_web_publisher.py --limit 1 --confirm

The script uses a persistent Playwright browser profile, so WhatsApp Web
should stay logged in after the QR code is scanned once.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

POSTS = Path("whatsapp_posts.json")
PROFILE = Path("whatsapp_web_profile")
GROUP = "Continental News"


def load_posts():
    if not POSTS.exists():
        raise SystemExit(f"ERROR: {POSTS} not found. Run bot.py first.")
    data = json.loads(POSTS.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("ERROR: whatsapp_posts.json must contain a JSON list.")
    return data


def post_text(item, number):
    summary = item.get("summary", "") or ""
    if len(summary) > 700:
        summary = summary[:697].rstrip(" .,!?:;—-") + "…"
    return (
        f"{number}. [{item.get('category','NEWS')}] {item.get('title','')}\n\n"
        f"{summary}\n\n"
        f"📰 Quelle: {item.get('source','')}\n"
        f"🔗 {item.get('url','')}\n"
        f"📅 {item.get('published_at','')}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default=GROUP)
    ap.add_argument("--limit", type=int, default=1)
    ap.add_argument("--confirm", action="store_true", help="ask before each message")
    ap.add_argument("--dry-run", action="store_true", help="open WhatsApp but do not send")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed.")
        print("Install with: pip install playwright")
        print("Then: python -m playwright install chromium")
        sys.exit(2)

    posts = load_posts()[: max(0, args.limit)]
    if not posts:
        raise SystemExit("No posts to publish.")

    print(f"WhatsApp Web publisher")
    print(f"Target group: {args.group}")
    print(f"Messages prepared: {len(posts)}")
    print("A browser window will open. On first run, scan the WhatsApp QR code if requested.")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE),
            headless=False,
            viewport={"width": 1400, "height": 950},
            args=["--disable-notifications"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://web.whatsapp.com/", wait_until="domcontentloaded", timeout=120000)

        print("Waiting for WhatsApp Web...")
        page.wait_for_timeout(5000)
        print("If QR code is shown, scan it with WhatsApp on your phone.")

        # Wait until the main WhatsApp interface appears.
        try:
            page.locator("#pane-side").wait_for(state="visible", timeout=120000)
        except Exception:
            print("Could not detect the WhatsApp chat pane.")
            print("Leave the browser open and check whether WhatsApp Web is logged in.")
            context.close()
            sys.exit(3)

        print("WhatsApp Web is ready.")

        # Locate the chat using WhatsApp's current search UI.
        # WhatsApp Web changes its DOM attributes periodically, so use
        # semantic selectors first and keep several fallbacks.
        import re

        search_candidates = [
            page.get_by_role("textbox", name=re.compile(r"search|suche|suchen|buscar", re.I)).first,
            page.locator('div[contenteditable="true"][aria-label*="Search" i]').first,
            page.locator('div[contenteditable="true"][aria-label*="Suche" i]').first,
            page.locator('div[contenteditable="true"][title*="Search" i]').first,
            page.locator('div[contenteditable="true"]').first,
        ]

        search = None
        for candidate in search_candidates:
            try:
                candidate.wait_for(state="visible", timeout=5000)
                search = candidate
                break
            except Exception:
                continue

        if search is None:
            print("ERROR: Could not locate the WhatsApp Web search field.")
            print("The WhatsApp Web interface may have changed again.")
            context.close()
            sys.exit(4)

        search.click()
        try:
            search.fill(args.group)
        except Exception:
            search.press("Control+A")
            search.press("Backspace")
            search.type(args.group)
        page.wait_for_timeout(2500)

        # Prefer an exact visible chat title.
        exact = page.get_by_text(args.group, exact=True).first
        if not exact.count():
            print(f'ERROR: Could not find chat/group "{args.group}".')
            context.close()
            sys.exit(4)
        exact.click()
        page.wait_for_timeout(1500)

        # Find the message composer. Avoid the search box.
        composer = page.locator('footer div[contenteditable="true"]').last
        if not composer.count():
            composer = page.locator('div[contenteditable="true"]').last

        for i, item in enumerate(posts, 1):
            text = post_text(item, i)
            print(f"\n[{i}/{len(posts)}] {item.get('title','')}")
            if args.confirm:
                answer = input("Send this message? [y/N] ").strip().lower()
                if answer not in {"y", "yes", "j", "ja"}:
                    print("Skipped.")
                    continue
            if args.dry_run:
                print("DRY RUN — not sent.")
                continue

            composer.click()
            composer.fill(text)
            page.wait_for_timeout(300)
            composer.press("Enter")
            page.wait_for_timeout(1800)
            print("Sent.")

        print("Finished.")
        input("Press Enter to close the browser...")
        context.close()


if __name__ == "__main__":
    main()
