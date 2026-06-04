"""URL -> records orchestration. Imports yt-dlp but NOT the Apify SDK, so the
whole resolve loop is unit-testable without the platform. ``main`` wraps this
with push_data + pay-per-event charging.
"""

from __future__ import annotations

import yt_dlp

from .extract import build_record


def build_ydl_opts(proxy_url=None, cookie_file=None, playlist_limit=50):
    opts = {
        "quiet": True,
        "no_warnings": True,
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


def iter_records(
    urls,
    *,
    playlist_limit=50,
    include_formats=True,
    include_subtitles=False,
    proxy_url=None,
    cookie_file=None,
    logger=None,
):
    """Yield one dict per resolved video (or one error dict per failed URL).

    A record with ``ok: True`` is chargeable; ``ok: False`` is a free failure.
    """
    opts = build_ydl_opts(proxy_url, cookie_file, playlist_limit)

    def log(message):
        if logger:
            logger(message)

    for url in urls:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if not info:
                raise RuntimeError("No data (unsupported, private, removed, or blocked).")

            entries = info.get("entries")
            if entries is not None:
                items = [e for e in list(entries) if e][:playlist_limit]
                log(f"{url}: collection with {len(items)} item(s)")
                for entry in items:
                    # Flat entries can lack formats; resolve each one fully.
                    if not entry.get("formats") and entry.get("url"):
                        try:
                            with yt_dlp.YoutubeDL(opts) as ydl2:
                                entry = ydl2.extract_info(entry["url"], download=False) or entry
                        except Exception:  # noqa: BLE001
                            pass
                    yield build_record(entry, url, include_formats, include_subtitles)
            else:
                log(f"OK   {url} -> {info.get('title') or info.get('id')}")
                yield build_record(info, url, include_formats, include_subtitles)
        except Exception as exc:  # noqa: BLE001
            message = " ".join(str(exc).split())[:300]
            log(f"FAIL {url} -> {message}")
            yield {"input_url": url, "ok": False, "error": message}
