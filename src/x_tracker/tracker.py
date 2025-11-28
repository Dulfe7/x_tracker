from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv


X_API_BASE = "https://api.twitter.com/2"


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass
class TrackerConfig:
    """Configuration for the activity tracker."""

    x_bearer_token: str
    telegram_bot_token: str
    telegram_chat_id: str
    accounts: List[str]
    poll_seconds: int = 120
    state_file: Path = Path("tracker_state.json")

    @classmethod
    def from_env(cls) -> "TrackerConfig":
        """Build configuration from environment variables and optional .env file."""

        load_dotenv()
        accounts_raw = os.getenv("TRACKED_ACCOUNTS", "")
        accounts = [account.strip().lstrip("@") for account in accounts_raw.split(",") if account.strip()]
        if not accounts:
            raise RuntimeError("Provide at least one account in TRACKED_ACCOUNTS.")

        return cls(
            x_bearer_token=_require_env("X_BEARER_TOKEN"),
            telegram_bot_token=_require_env("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=_require_env("TELEGRAM_CHAT_ID"),
            accounts=accounts,
            poll_seconds=int(os.getenv("POLL_SECONDS", "120")),
            state_file=Path(os.getenv("STATE_FILE", "tracker_state.json")),
        )


class XClient:
    """Lightweight client for the X (Twitter) v2 API."""

    def __init__(self, bearer_token: str):
        self.headers = {"Authorization": f"Bearer {bearer_token}"}

    def get_user_id(self, username: str) -> str:
        response = requests.get(
            f"{X_API_BASE}/users/by/username/{username}",
            headers=self.headers,
            timeout=15,
        )
        _raise_for_status(response)
        data = response.json()
        try:
            return data["data"]["id"]
        except (TypeError, KeyError) as exc:
            raise RuntimeError(f"Unexpected response while resolving user '{username}'.") from exc

    def fetch_latest_tweets(self, user_id: str, since_id: Optional[str] = None, limit: int = 5) -> List[Dict]:
        params = {
            "exclude": "retweets,replies",
            "max_results": str(limit),
            "tweet.fields": "created_at,text,id,author_id",
        }
        if since_id:
            params["since_id"] = since_id

        response = requests.get(
            f"{X_API_BASE}/users/{user_id}/tweets",
            params=params,
            headers=self.headers,
            timeout=15,
        )
        _raise_for_status(response)
        data = response.json()
        return data.get("data", [])


def _raise_for_status(response: requests.Response) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(
            f"X API request failed ({response.status_code}): {response.text}"
        ) from exc


class TelegramNotifier:
    """Sends formatted messages to Telegram via the bot API."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send_message(self, text: str) -> None:
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}
        response = requests.post(
            f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
            json=payload,
            timeout=15,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(f"Telegram send failed ({response.status_code}): {response.text}") from exc


class ActivityTracker:
    """Polls X accounts for new posts and relays them to Telegram."""

    def __init__(self, config: TrackerConfig):
        self.config = config
        self.x_client = XClient(config.x_bearer_token)
        self.notifier = TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id)
        self._state: Dict[str, Optional[str]] = self._load_state()

    def _load_state(self) -> Dict[str, Optional[str]]:
        if self.config.state_file.exists():
            with self.config.state_file.open("r", encoding="utf-8") as handle:
                stored = json.load(handle)
            return {account: stored.get(account) for account in self.config.accounts}
        return {account: None for account in self.config.accounts}

    def _persist_state(self) -> None:
        self.config.state_file.parent.mkdir(parents=True, exist_ok=True)
        with self.config.state_file.open("w", encoding="utf-8") as handle:
            json.dump(self._state, handle, indent=2)

    def _format_message(self, username: str, tweet: Dict) -> str:
        link = f"https://twitter.com/{username}/status/{tweet['id']}"
        return (
            f"🧭 Новая активность @{username}\n"
            f"{tweet['text']}\n\n"
            f"Ссылка: {link}"
        )

    def _notify(self, username: str, tweets: List[Dict]) -> None:
        # Send oldest first to keep chronology.
        for tweet in reversed(tweets):
            message = self._format_message(username, tweet)
            self.notifier.send_message(message)

    def check_once(self) -> None:
        for username in self.config.accounts:
            user_id = self.x_client.get_user_id(username)
            since_id = self._state.get(username)
            tweets = self.x_client.fetch_latest_tweets(user_id, since_id)
            if tweets:
                self._state[username] = tweets[0]["id"]
                self._notify(username, tweets)
        self._persist_state()

    def run(self) -> None:
        while True:
            self.check_once()
            time.sleep(self.config.poll_seconds)


def build_tracker_from_env() -> ActivityTracker:
    return ActivityTracker(TrackerConfig.from_env())


__all__ = [
    "ActivityTracker",
    "TrackerConfig",
    "TelegramNotifier",
    "XClient",
    "build_tracker_from_env",
]
