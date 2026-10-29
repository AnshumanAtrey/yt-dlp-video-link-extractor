"""Actor entry point: any video URL in, direct links + metadata out.

We never download media. ``extract_info(download=False)`` only resolves the
stream URLs and metadata over the network, so memory stays flat regardless of
video size - a paste-URL-get-links tool, not a file host. The resolve loop
lives in ``resolve.py`` (SDK-free); this module is the thin Apify wrapper that
persists records and charges per resolved video.
"""

from __future__ import annotations

from apify import Actor

from .resolve import Resolver, is_bot_check

URL_EVENT = "url-processed"
VIDEO_EVENT = "video-resolved"


def usd(amount):
    """A limit or a price as people read it: $0.043, $0.5, $5."""
    return "$" + (f"{float(amount):.4f}".rstrip("0").rstrip(".") or "0")


async def charge(event):
    """Best-effort pay-per-event charge; never let billing drop a result."""
    try:
        await Actor.charge(event)
    except Exception as exc:  # noqa: BLE001
        Actor.log.debug(f"charge({event}) skipped: {exc}")


class Budget:
    """The run's spending limit, which Apify says a run must stop at.

    A URL is started only while the limit can still pay its URL fee and one
    video, so the actor never resolves what it could not deliver. Before this,
    rows past the limit were pushed for free (2026-10-29: limit $0.05, 2 videos
    delivered, 1 charged).
    """

    def __init__(self):
        self.cm = Actor.get_charging_manager()
        info = self.cm.get_pricing_info()
        self.ppe = info.is_pay_per_event
        self.limit = info.max_total_charge_usd
        self.next_cost = sum(info.per_event_prices.get(event, 0) for event in (URL_EVENT, VIDEO_EVENT))

    def can_pay_next(self):
        return not self.ppe or self.limit - self.cm.calculate_total_charged_amount() >= self.next_cost


async def residential_proxy_url():
    """An Apify residential proxy URL, for the videos a site refused to the run's own IP.

    Only those go through it: residential traffic is billed to us per GB, about
    $0.007 per YouTube video (run LXk55Qbupcw9GQqxh, 2026-10-29).
    """
    try:
        proxy_cfg = await Actor.create_proxy_configuration(groups=["RESIDENTIAL"])
        return await proxy_cfg.new_url() if proxy_cfg else None
    except Exception as exc:  # noqa: BLE001
        Actor.log.warning(f"Residential proxy unavailable, bot-checked URLs stay failed: {exc}")
        return None


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

        budget = Budget()
        if not budget.can_pay_next():
            msg = (f"Nothing was resolved and no URL or video was charged: this run's spending limit of "
                   f"{usd(budget.limit)} cannot pay for one video ({usd(budget.next_cost)} with its URL fee). "
                   "Raise the run's maximum cost in the run options, or add credit, then run it again.")
            Actor.log.warning(msg)
            await Actor.set_status_message(msg)
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

        resolver = Resolver(
            playlist_limit=playlist_limit,
            include_formats=include_formats,
            include_subtitles=include_subtitles,
            cookie_file=cookie_file,
            logger=Actor.log.info,
        )
        residential = None  # created on the first bot check, then shared by the rest
        resolved = failed = retried = 0
        stopped = False
        try:
            for url in urls:
                if not budget.can_pay_next():
                    stopped = True
                    break
                records = resolver.records(url, proxy_url)
                # The user chose no proxy, and the site refused the run's datacenter IP:
                # retry this URL alone through a residential one.
                if not proxy_url and len(records) == 1 and is_bot_check(records[0]):
                    residential = residential or await residential_proxy_url()
                    if residential:
                        Actor.log.info(f"{url}: bot check on the run's IP, retrying through a residential proxy")
                        records = resolver.records(url, residential)
                        retried += 1

                # Charge once per input URL processed - covers the compute of every
                # attempt, including failures, so a run of dead/blocked URLs still
                # pays for its compute (no per-record bleed).
                await charge(URL_EVENT)
                for record in records:
                    if not record.get("ok"):
                        await Actor.push_data(record)
                        failed += 1
                        continue
                    # The SDK pushes the record only if the limit can pay for it.
                    result = await Actor.push_data(record, charged_event_name=VIDEO_EVENT)
                    if budget.ppe and not result.charged_count:
                        stopped = True
                        break
                    resolved += 1
                if stopped:
                    break
        finally:
            resolver.close()

        msg = f"Resolved {resolved} video(s) from {len(urls)} URL(s); {failed} URL(s) failed."
        if retried:
            msg += f" {retried} URL(s) went through a residential proxy after a bot check."
        if stopped:
            msg += (f" Stopped early: this run's spending limit of {usd(budget.limit)} was reached. "
                    "Raise the run's maximum cost to resolve the rest.")
        Actor.log.info(msg)
        await Actor.set_status_message(msg)
