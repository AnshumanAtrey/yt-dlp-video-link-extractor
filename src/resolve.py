"""URL -> records orchestration. Imports yt-dlp but NOT the Apify SDK, so the
whole resolve loop is unit-testable without the platform. ``main`` wraps this
with push_data + pay-per-event charging.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import yt_dlp
from yt_dlp.extractor.vimeo import VimeoIE

from .extract import build_record

# yt-dlp's own pattern for Vimeo video links (channels, groups and unlisted hashes included).
_VIMEO_VIDEO = re.compile(VimeoIE._VALID_URL)


def build_ydl_opts(proxy_url=None, cookie_file=None, playlist_limit=50):
    opts = {
        "quiet": True,
        "no_warnings": True,
        # The platform gives the container a terminal, so yt-dlp colored every
        # error ("\x1b[0;31mERROR:\x1b[0m ...") and the codes landed in the dataset.
        "color": "never",
        "skip_download": True,
        # Bounded so a dead/hanging host fails in ~15s, not ~30-90s. This caps
        # the per-URL compute cost (the failure-bleed vector), which the
        # per-URL pricing event is sized against.
        "socket_timeout": 15,
        "retries": 1,
        "extractor_retries": 1,
        # A single video URL carrying &list= resolves to just that video; a pure
        # playlist/channel URL still expands into its entries.
        "noplaylist": True,
        "playlistend": playlist_limit,
        "extract_flat": False,
        "ignoreerrors": False,
    }
    if proxy_url:
        opts["proxy"] = proxy_url
    if cookie_file:
        opts["cookiefile"] = cookie_file
    return opts


def vimeo_player_url(url):
    """The public player page of a vimeo.com video link, or None for any other URL.

    yt-dlp needs a logged-in account for vimeo.com pages ("The web client only
    works when logged-in"), while player.vimeo.com serves the same video, title,
    uploader and formats to anyone, unlisted videos too when their hash is passed
    as ``h`` (verified 2026-10-29, yt-dlp 2026.10.26). Only view counts and upload
    dates need the account.
    """
    match = _VIMEO_VIDEO.match(url)
    if not match or urlparse(url).hostname == "player.vimeo.com":
        return None
    groups = match.groupdict()
    if groups.get("u") or not groups.get("id"):
        return None
    unlisted = groups.get("unlisted_hash")
    return f"https://player.vimeo.com/video/{groups['id']}" + (f"?h={unlisted}" if unlisted else "")


def is_bot_check(record):
    """True when the site refused the run's IP with a bot check.

    YouTube answers datacenter IPs with "Sign in to confirm you're not a bot"
    video by video (one video passed while others failed from the same run), and
    the same videos resolve through a residential IP.
    """
    return not record.get("ok") and "not a bot" in (record.get("error") or "").lower()


class Resolver:
    """Resolves input URLs with one YoutubeDL per proxy route, kept for the whole run.

    A fresh YoutubeDL per URL downloaded YouTube's player for every video; one per
    route downloads it once (3 videos: 7.5 s instead of 10.3 s, 1 player download
    instead of 3, verified 2026-10-29). That matters most on the residential route,
    which is billed per GB.
    """

    def __init__(self, *, playlist_limit=50, include_formats=True, include_subtitles=False,
                 cookie_file=None, logger=None):
        self.playlist_limit = playlist_limit
        self.include_formats = include_formats
        self.include_subtitles = include_subtitles
        self.cookie_file = cookie_file
        self.log = logger or (lambda message: None)
        self._ydls = {}

    def close(self):
        for ydl in self._ydls.values():
            ydl.close()

    def _ydl(self, proxy_url):
        if proxy_url not in self._ydls:
            self._ydls[proxy_url] = yt_dlp.YoutubeDL(
                build_ydl_opts(proxy_url, self.cookie_file, self.playlist_limit))
        return self._ydls[proxy_url]

    def records(self, url, proxy_url=None):
        """Return one dict per resolved video of one input URL, or one error dict.

        A record with ``ok: True`` is chargeable; ``ok: False`` is a free failure.
        """
        target = url if self.cookie_file else (vimeo_player_url(url) or url)
        if target != url:
            self.log(f"{url}: resolving through Vimeo's public player page {target}, which needs no account")
        ydl = self._ydl(proxy_url)
        try:
            info = ydl.extract_info(target, download=False)
            if not info:
                raise RuntimeError("No data (unsupported, private, removed, or blocked).")

            entries = info.get("entries")
            if entries is None:
                self.log(f"OK   {url} -> {info.get('title') or info.get('id')}")
                return [build_record(info, url, self.include_formats, self.include_subtitles)]

            items = [e for e in list(entries) if e][: self.playlist_limit]
            self.log(f"{url}: collection with {len(items)} item(s)")
            records = []
            for entry in items:
                # Flat entries can lack formats; resolve each one fully.
                if not entry.get("formats") and entry.get("url"):
                    try:
                        entry = ydl.extract_info(entry["url"], download=False) or entry
                    except Exception:  # noqa: BLE001
                        pass
                records.append(build_record(entry, url, self.include_formats, self.include_subtitles))
            return records
        except Exception as exc:  # noqa: BLE001
            message = " ".join(str(exc).split())[:300]
            self.log(f"FAIL {url} -> {message}")
            return [{"input_url": url, "ok": False, "error": message}]
