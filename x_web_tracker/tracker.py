"""Simple X (Twitter) web tracker that sends new tweets to Telegram.

This script scrapes a user's public profile page using Playwright's synchronous API,
tracks the last seen tweet ID in ``last_id.txt``, and posts notifications about new
tweets to Telegram via the Bot API. It is intended for low-frequency, personal use.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

BASE_URL = "https://x.com"
LAST_ID_PATH = Path(__file__).resolve().parent / "last_id.txt"


def load_config() -> Dict[str, str]:
    """Load and validate required environment variables.

    Returns a mapping with X username, Telegram bot token, and chat ID. Exits the
    process with a clear error message if any variable is missing.
    """

    load_dotenv()

    required_vars = {
        "X_USERNAME": os.getenv("X_USERNAME"),
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
        "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID"),
    }

    missing = [name for name, value in required_vars.items() if not value]
    if missing:
        print(
            "Missing required environment variables: " + ", ".join(missing),
            "\nPlease create a .env file with X_USERNAME, TELEGRAM_BOT_TOKEN, and TELEGRAM_CHAT_ID.",
        )
        sys.exit(1)

    return required_vars  # type: ignore[return-value]


def read_last_id() -> Optional[str]:
    """Return the last stored tweet ID, or None if missing/empty."""

    if not LAST_ID_PATH.exists():
        return None
    content = LAST_ID_PATH.read_text(encoding="utf-8").strip()
    return content or None


def write_last_id(tweet_id: str) -> None:
    """Persist the last seen tweet ID."""

    LAST_ID_PATH.write_text(tweet_id, encoding="utf-8")


def send_to_telegram(text: str, *, token: str, chat_id: str) -> None:
    """Send a message to Telegram using the Bot API.

    Errors are logged to the console but do not raise exceptions to keep the script
    running even if Telegram is temporarily unavailable.
    """

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code != 200:
            print(
                f"Failed to send Telegram message (status {response.status_code}): {response.text}"
            )
    except requests.RequestException as exc:
        print(f"Error sending Telegram message: {exc}")


def extract_tweets(username: str, *, max_tweets: int = 10) -> List[Dict[str, str]]:
    """Scrape the user's profile page and return latest tweets.

    Each tweet dict contains: id (str), url (absolute), text (str). The returned
    list is ordered newest-first, matching the page order.
    """

    tweets: List[Dict[str, str]] = []
    page_url = f"{BASE_URL}/{username}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.goto(page_url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            tweet_elements = page.query_selector_all('[data-testid="tweet"]')
            if not tweet_elements:
                print("No tweets found on the page. The layout may have changed.")
                return []

            seen_ids = set()
            for element in tweet_elements:
                link = element.query_selector('a[href*="/status/"]')
                if not link:
                    continue
                href = link.get_attribute("href")
                if not href or "/status/" not in href:
                    continue

                tweet_id = href.rstrip("/").split("/")[-1]
                if tweet_id in seen_ids:
                    continue
                seen_ids.add(tweet_id)

                url = href if href.startswith("http") else f"{BASE_URL}{href}"
                text = element.inner_text().strip()

                tweets.append({"id": tweet_id, "url": url, "text": text})
                if len(tweets) >= max_tweets:
                    break

            browser.close()
    except PlaywrightTimeoutError:
        print("Timed out waiting for the X profile page to load. Check the username or network.")
        return []
    except Exception as exc:  # pragma: no cover - broad for robustness
        print(f"Failed to fetch tweets: {exc}")
        return []

    return tweets


def main() -> None:
    config = load_config()
    username = config["X_USERNAME"]
    last_seen_id = read_last_id()

    tweets = extract_tweets(username)
    if not tweets:
        print("No tweets found or page failed to load.")
        return

    newest_id = tweets[0]["id"]

    if last_seen_id is None:
        write_last_id(newest_id)
        print("First run detected. Saved the latest tweet ID and will notify on the next run.")
        return

    new_tweets: List[Dict[str, str]] = []
    for tweet in tweets:
        if tweet["id"] == last_seen_id:
            break
        new_tweets.append(tweet)

    if not new_tweets:
        print("No new tweets since last check.")
    else:
        new_tweets.reverse()  # oldest first for notifications
        for tweet in new_tweets:
            message = (
                f"New tweet from @{username}:\n{tweet['url']}\n\n{tweet['text']}"
            )
            send_to_telegram(
                message,
                token=config["TELEGRAM_BOT_TOKEN"],
                chat_id=config["TELEGRAM_CHAT_ID"],
            )
        print(f"Sent {len(new_tweets)} new tweet(s) to Telegram.")

    write_last_id(newest_id)


if __name__ == "__main__":
    main()
