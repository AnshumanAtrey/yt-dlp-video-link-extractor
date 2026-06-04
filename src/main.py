"""Actor entry point: any video URL in, direct links + metadata out.

We never download media. ``extract_info(download=False)`` only resolves the
stream URLs and metadata over the network, so memory stays flat regardless of
video size - a paste-URL-get-links tool, not a file host. The resolve loop
lives in ``resolve.py`` (SDK-free); this module is the thin Apify wrapper that
persists records and charges per resolved video.
"""

from __future__ import annotations

from apify import Actor

from .resolve import iter_records


async def charge(event):
    """Best-effort pay-per-event charge; never let billing drop a result."""
    try:
        await Actor.charge(event)
    except Exception as exc:  # noqa: BLE001
        Actor.log.debug(f"charge({event}) skipped: {exc}")


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        urls = actor_input.get("urls") or []
        if isinstance(urls, str):
            urls = [urls]
        urls = [u.strip() for u in urls if isinstance(u, str) and u.strip()]

        playlist_limit = int(actor_input.get("playlistLimit") or 50)
        include_formats = bool(actor_input.get("includeFormats", True))
        include_subtitles = bool(actor_input.get("includeSubtitles", False))

        if not urls:
            Actor.log.warning('No URLs given. Add at least one video URL to "urls".')
            return

        # Optional proxy - helps with sites that block datacenter IPs.
        proxy_url = None
        proxy_input = actor_input.get("proxyConfiguration")
        if proxy_input:
            proxy_cfg = await Actor.create_proxy_configuration(actor_proxy_input=proxy_input)
            if proxy_cfg:
                proxy_url = await proxy_cfg.new_url()

        # Optional cookies (Netscape cookie-file contents) for auth-gated videos.
        cookie_file = None
        cookies = actor_input.get("cookies")
        if cookies and cookies.strip():
            cookie_file = "/tmp/cookies.txt"
            with open(cookie_file, "w", encoding="utf-8") as handle:
                handle.write(cookies)

        resolved = 0
        failed = 0
        charged_urls = set()
        for record in iter_records(
            urls,
            playlist_limit=playlist_limit,
            include_formats=include_formats,
            include_subtitles=include_subtitles,
            proxy_url=proxy_url,
            cookie_file=cookie_file,
            logger=Actor.log.info,
        ):
            # Charge once per input URL processed - covers the compute of every
            # attempt, including failures, so a run of dead/blocked URLs still
            # pays for its compute (no per-record bleed).
            input_url = record.get("input_url")
            if input_url and input_url not in charged_urls:
                charged_urls.add(input_url)
                await charge("url-processed")

            await Actor.push_data(record)
            if record.get("ok"):
                await charge("video-resolved")
                resolved += 1
            else:
                failed += 1

        Actor.log.info(f"Done. resolved={resolved}, failed={failed}, inputs={len(urls)}")
