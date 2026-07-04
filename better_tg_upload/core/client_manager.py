from argparse import Namespace
from json import load
from pathlib import Path
from typing import Any

from ..profiles.store import ensure_session_dir
from .exceptions import CliError


class TelegramClientManager:
    def __init__(self, args: Namespace):
        self.args = args
        self.client: Any = None

    def _load_proxy(self) -> dict | None:
        if not self.args.proxy:
            return None
        proxy_file = Path("proxy.json")
        if not proxy_file.exists():
            raise CliError("proxy.json not found while --proxy is set.")
        with proxy_file.open("r", encoding="utf-8") as fp:
            data = load(fp)
        if self.args.proxy not in data:
            raise CliError(f"Proxy profile not found in proxy.json: {self.args.proxy}")
        return data[self.args.proxy]

    def _build_client(self):
        try:
            from pyrogram.client import Client, enums
        except ImportError as exc:
            raise CliError(
                "Kurigram is required. Install with: pip install kurigram"
            ) from exc

        session_dir = ensure_session_dir(self.args.session_dir).resolve()
        # Pyrogram stores sessions at workdir / f"{name}.session" — name must be
        # the profile basename only, not a path inside workdir.
        session_name = self.args.profile
        proxy = self._load_proxy()

        common_kwargs = {
            "ipv6": self.args.ipv6,
            "proxy": proxy,
            "workdir": session_dir,
            "sleep_threshold": 0,
            "parse_mode": enums.ParseMode.DEFAULT,
            "max_concurrent_transmissions": 10,
        }

        if self.args.login_string:
            return Client(session_name, session_string=self.args.login_string, **common_kwargs)

        if self.args.api_id and self.args.api_hash:
            if self.args.phone:
                return Client(
                    session_name,
                    api_id=self.args.api_id,
                    api_hash=self.args.api_hash,
                    phone_number=self.args.phone,
                    hide_password=self.args.hide_pswd,
                    app_version="better-tg-upload",
                    device_model=self.args.device_model,
                    system_version=self.args.system_version,
                    in_memory=self.args.tmp_session,
                    **common_kwargs,
                )
            if self.args.bot:
                return Client(
                    session_name,
                    api_id=self.args.api_id,
                    api_hash=self.args.api_hash,
                    bot_token=self.args.bot,
                    in_memory=self.args.tmp_session,
                    **common_kwargs,
                )
            return Client(
                session_name,
                api_id=self.args.api_id,
                api_hash=self.args.api_hash,
                in_memory=self.args.tmp_session,
                **common_kwargs,
            )

        return Client(session_name, in_memory=self.args.tmp_session, **common_kwargs)

    async def __aenter__(self):
        self.client = self._build_client()
        await self.client.start()
        return self.client

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.client is not None:
            await self.client.stop()
