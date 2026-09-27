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
import re
import tempfile
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


def find_image_url(item, browser_context=None):
    """Find the publisher article image, even when the stored URL is Google News."""
    for key in ("image_url", "image", "thumbnail", "media_url", "og_image"):
        value = item.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value

    title = (item.get("title") or "").strip()
    url = item.get("url", "") or ""
    if not title or browser_context is None:
        return None

    page = None
    try:
        page = browser_context.new_page()
        # Google News search is used only to resolve the publisher URL. This
        # avoids depending on the opaque news.google.com RSS article wrapper.
        from urllib.parse import quote_plus
        search_url = "https://www.google.com/search?q=" + quote_plus(title)
        page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)

        # Prefer a result from the source named in the item.
        source_name = (item.get("source") or "").lower()
        links = page.locator('a[href^="http"]')
        count = min(links.count(), 80)
        candidates = []
        for i in range(count):
            a = links.nth(i)
            try:
                href = a.get_attribute("href") or ""
                txt = (a.inner_text(timeout=500) or "").strip()
                if not href.startswith("http") or "google.com" in href:
                    continue
                score = 0
                low = (href + " " + txt).lower()
                if source_name and source_name.split(".")[0] in low:
                    score += 10
                # Strong title-word overlap.
                words = [w for w in re.findall(r"[\wÄÖÜäöüß-]{5,}", title.lower())]
                score += sum(1 for w in words if w in low)
                candidates.append((score, href))
            except Exception:
                pass
        candidates.sort(reverse=True)

        # Try the best external result(s) and read Open Graph image.
        tried = 0
        for _, candidate_url in candidates[:8]:
            tried += 1
            article = None
            try:
                article = browser_context.new_page()
                article.goto(candidate_url, wait_until="domcontentloaded", timeout=45000)
                article.wait_for_timeout(1800)
                final_url = article.url
                for selector in (
                    'meta[property="og:image"]',
                    'meta[property="og:image:url"]',
                    'meta[name="twitter:image"]',
                    'meta[name="twitter:image:src"]',
                ):
                    value = article.locator(selector).first.get_attribute("content")
                    if value and value.startswith(("http://", "https://")):
                        print(f"Image found from publisher page: {value}")
                        article.close()
                        page.close()
                        return value
                print(f"No image on candidate: {final_url}")
            except Exception as exc:
                print(f"Candidate page failed: {exc}")
            finally:
                try:
                    if article:
                        article.close()
                except Exception:
                    pass

        print(f"No publisher image found after trying {tried} search result(s).")
    except Exception as exc:
        print(f"Article image search failed: {exc}")
    finally:
        try:
            if page:
                page.close()
        except Exception:
            pass
    return None


def download_image(url):
    if not url:
        return None
    try:
        import requests
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153 Safari/537.36"})
        r.raise_for_status()
        content_type = r.headers.get("content-type", "").lower()
        ext = ".jpg"
        if "png" in content_type: ext = ".png"
        elif "webp" in content_type: ext = ".webp"
        elif "gif" in content_type: ext = ".gif"
        fd, path = tempfile.mkstemp(prefix="conti_news_", suffix=ext)
        with open(fd, "wb", closefd=True) as f:
            f.write(r.content)
        return path
    except Exception as exc:
        print(f"Image download failed: {exc}")
        return None


def attach_and_send_image(page, image_path, caption):
    """Use WhatsApp Web's real Attach -> Photos & Videos flow."""
    # WhatsApp creates the actual file input after the Attach menu is opened.
    attach_candidates = [
        page.get_by_role("button", name=re.compile(r"attach|anhängen|anheften|add|hinzufügen", re.I)).last,
        page.locator('button[aria-label*="Attach" i]').last,
        page.locator('button[aria-label*="Anhängen" i]').last,
        page.locator('button[aria-label*="Add" i]').last,
        page.locator('[data-testid*="attach" i]').last,
    ]
    attach = None
    for loc in attach_candidates:
        try:
            loc.wait_for(state="visible", timeout=2500)
            attach = loc
            break
        except Exception:
            continue
    if attach is None:
        print("PHOTO ERROR: WhatsApp Attach button not found.")
        return False

    try:
        attach.click()
        page.wait_for_timeout(700)
    except Exception as exc:
        print(f"PHOTO ERROR: could not open Attach menu: {exc}")
        return False

    # The menu item is normally named Photos & Videos (localized variants included).
    photo_menu_candidates = [
        page.get_by_text(re.compile(r"photos?\s*(?:&|and)\s*videos?|fotos?\s*(?:&|und)\s*videos?", re.I)).last,
        page.get_by_role("button", name=re.compile(r"photos?\s*(?:&|and)\s*videos?|fotos?\s*(?:&|und)\s*videos?", re.I)).last,
        page.get_by_role("menuitem", name=re.compile(r"photos?|fotos?", re.I)).last,
    ]
    photo_menu = None
    for loc in photo_menu_candidates:
        try:
            loc.wait_for(state="visible", timeout=2500)
            photo_menu = loc
            break
        except Exception:
            continue

    if photo_menu is not None:
        try:
            with page.expect_file_chooser(timeout=5000) as fc_info:
                photo_menu.click()
            chooser = fc_info.value
            chooser.set_files(image_path)
            print("PHOTO: selected through Photos & Videos.")
        except Exception as exc:
            print(f"PHOTO: menu selection failed: {exc}")
            return False
    else:
        # Fallback for versions where the file input is already present after Attach.
        file_input = page.locator('input[type="file"]').last
        try:
            file_input.wait_for(state="attached", timeout=3000)
            file_input.set_input_files(image_path)
            print("PHOTO: selected through file input.")
        except Exception as exc:
            print(f"PHOTO ERROR: no image file input after Attach: {exc}")
            return False

    # Wait for WhatsApp's media preview to appear.
    page.wait_for_timeout(1800)

    # Caption field in the media preview is contenteditable, but the normal
    # chat composer may also exist. Prefer the visible textbox that is NOT footer.
    caption_candidates = [
        page.locator('div[contenteditable="true"][role="textbox"]').filter(has_not=page.locator('footer')).last,
        page.locator('[contenteditable="true"][aria-label*="caption" i]').last,
        page.locator('[contenteditable="true"][aria-label*="beschrift" i]').last,
    ]
    caption_box = None
    for loc in caption_candidates:
        try:
            loc.wait_for(state="visible", timeout=3000)
            caption_box = loc
            break
        except Exception:
            continue
    if caption_box is None:
        # Last resort: visible contenteditable that is not the search field.
        boxes = page.locator('div[contenteditable="true"]')
        for i in range(boxes.count()-1, -1, -1):
            loc = boxes.nth(i)
            try:
                if loc.is_visible():
                    caption_box = loc
                    break
            except Exception:
                pass

    if caption_box is not None and caption:
        try:
            caption_box.click()
            caption_box.fill(caption)
        except Exception as exc:
            print(f"PHOTO WARNING: could not fill caption: {exc}")

    send_candidates = [
        page.get_by_role("button", name=re.compile(r"send|senden|enviar|abschicken", re.I)).last,
        page.locator('button[aria-label*="Send" i]').last,
        page.locator('button[aria-label*="Senden" i]').last,
        page.locator('[data-testid*="send" i]').last,
    ]
    for send in send_candidates:
        try:
            send.wait_for(state="visible", timeout=4000)
            send.click()
            page.wait_for_timeout(1500)
            print("PHOTO: image sent.")
            return True
        except Exception:
            continue

    if caption_box is not None:
        try:
            caption_box.press("Enter")
            page.wait_for_timeout(1500)
            print("PHOTO: sent via Enter fallback.")
            return True
        except Exception as exc:
            print(f"PHOTO ERROR: send fallback failed: {exc}")

    return False

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

            image_url = find_image_url(item, context)
            image_path = download_image(image_url) if image_url else None
            sent_as_image = False
            if image_path:
                print(f"Image found: {image_url}")
                try:
                    sent_as_image = attach_and_send_image(page, image_path, text)
                finally:
                    try:
                        Path(image_path).unlink(missing_ok=True)
                    except Exception:
                        pass
            if not sent_as_image:
                if image_url:
                    print("Could not attach image; sending text only.")
                composer.click()
                composer.fill(text)
                page.wait_for_timeout(300)
                composer.press("Enter")
            page.wait_for_timeout(1800)
            print("Sent with photo." if sent_as_image else "Sent (text only).")

        print("Finished.")
        input("Press Enter to close the browser...")
        context.close()


if __name__ == "__main__":
    main()
