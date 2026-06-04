"""Pure extraction + record-shaping logic.

No Apify or yt-dlp imports here on purpose. This module turns a raw yt-dlp
``info`` dict (from ``YoutubeDL.extract_info(..., download=False)``) into a
clean, flat dataset record. Keeping it dependency-free makes it unit-testable
without the Apify SDK or a network call.
"""

from __future__ import annotations


def fmt_duration(seconds):
    """Seconds -> "H:MM:SS" or "M:SS"."""
    if seconds is None:
        return None
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return None
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def fmt_date(yyyymmdd):
    """yt-dlp upload_date "20091025" -> "2009-10-25"."""
    s = str(yyyymmdd or "")
    if len(s) != 8 or not s.isdigit():
        return yyyymmdd
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"


def _absent(value):
    """True if a codec field means "this stream has none of that track"."""
    return value in (None, "none", "")


def _progressive(fmt):
    """A directly-fetchable file (not an HLS/DASH manifest)."""
    return (fmt.get("protocol") or "") in ("https", "http")


def _classify(fmt):
    """Bucket a format as combined / video / audio.

    The subtle case: a progressive file often leaves BOTH vcodec and acodec as
    ``None`` (unknown) rather than naming them - that is a single muxed file
    carrying audio+video, so it counts as combined. yt-dlp does this for legacy
    progressive downloads (Vimeo http-720p, many direct-mp4 sites).
    """
    v = fmt.get("vcodec")
    a = fmt.get("acodec")
    has_v = not _absent(v)
    has_a = not _absent(a)
    if has_v and has_a:
        return "combined"
    if has_v:
        return "video"
    if has_a:
        return "audio"
    if v is None and a is None:
        return "combined"  # progressive file / muxed manifest, codecs unlabeled
    return "other"


def _vscore(fmt):
    # height first, then prefer a direct file over a manifest, then bitrate
    return (fmt.get("height") or 0, 1 if _progressive(fmt) else 0, fmt.get("tbr") or 0)


def _ascore(fmt):
    return (fmt.get("abr") or fmt.get("tbr") or 0, 1 if _progressive(fmt) else 0)


def _resolution(fmt):
    if not fmt:
        return None
    if fmt.get("resolution"):
        return fmt["resolution"]
    width, height = fmt.get("width"), fmt.get("height")
    if width and height:
        return f"{width}x{height}"
    if height:
        return f"{height}p"
    return None


def pick_links(info):
    """Pull the most useful direct URLs out of the format list.

    ``best_url`` is the single link a person most likely wants: a combined
    audio+video file when one exists, else the best audio (for music/podcasts),
    else best video. ``best_video_url`` + ``best_audio_url`` are exposed too,
    because high-res sources (YouTube, Vimeo) serve those tracks separately.
    """
    formats = [f for f in (info.get("formats") or []) if f.get("url")]

    combined, video_only, audio_only = [], [], []
    for fmt in formats:
        kind = _classify(fmt)
        if kind == "combined":
            combined.append(fmt)
        elif kind == "video":
            video_only.append(fmt)
        elif kind == "audio":
            audio_only.append(fmt)

    best_combined = max(combined, key=_vscore) if combined else None
    best_video = max(video_only, key=_vscore) if video_only else None
    best_audio = max(audio_only, key=_ascore) if audio_only else None

    # The headline link: prefer a self-contained file, fall back gracefully.
    primary = best_combined or best_audio or best_video
    primary_kind = (
        "combined" if primary is best_combined and best_combined
        else "audio" if primary is best_audio and best_audio
        else "video" if primary else None
    )
    if primary is None and info.get("url"):
        primary = {"url": info["url"], "ext": info.get("ext"),
                   "protocol": info.get("protocol")}
        primary_kind = "combined"

    return {
        "best_url": (primary or {}).get("url"),
        "best_url_kind": primary_kind,
        "best_url_protocol": (primary or {}).get("protocol"),
        "best_ext": (primary or {}).get("ext"),
        "best_resolution": _resolution(primary),
        "best_video_url": (best_video or {}).get("url"),
        "best_video_resolution": _resolution(best_video),
        "best_audio_url": (best_audio or {}).get("url"),
        "best_audio_ext": (best_audio or {}).get("ext"),
    }


def clean_formats(formats):
    """Trim each format from ~40 noisy fields down to the 10 that matter."""
    out = []
    for f in formats or []:
        if not f.get("url"):
            continue
        out.append(
            {
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "resolution": _resolution(f),
                "fps": f.get("fps"),
                "vcodec": f.get("vcodec"),
                "acodec": f.get("acodec"),
                "filesize": f.get("filesize") or f.get("filesize_approx"),
                "tbr": f.get("tbr"),
                "note": f.get("format_note"),
                "url": f.get("url"),
            }
        )
    return out


def _subs(subs_dict):
    return {
        lang: [t.get("url") for t in tracks if t.get("url")]
        for lang, tracks in (subs_dict or {}).items()
    }


def build_record(info, input_url, include_formats=True, include_subtitles=False):
    """Shape a raw yt-dlp info dict into a flat, link-first dataset record."""
    record = {
        "input_url": input_url,
        "ok": True,
        "extractor": info.get("extractor"),
        "id": info.get("id"),
        "title": info.get("title"),
        "uploader": info.get("uploader") or info.get("channel") or info.get("uploader_id"),
        "channel_url": info.get("channel_url") or info.get("uploader_url"),
        "webpage_url": info.get("webpage_url") or input_url,
        "duration_seconds": info.get("duration"),
        "duration": fmt_duration(info.get("duration")),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "upload_date": fmt_date(info.get("upload_date")),
        "is_live": bool(info.get("is_live")),
        "thumbnail": info.get("thumbnail"),
    }
    record.update(pick_links(info))
    description = (info.get("description") or "")[:500]
    record["description"] = description or None

    if include_formats:
        record["formats"] = clean_formats(info.get("formats"))
        record["thumbnails"] = [
            t.get("url") for t in (info.get("thumbnails") or []) if t.get("url")
        ]
    if include_subtitles:
        record["subtitles"] = _subs(info.get("subtitles"))
        record["auto_captions"] = _subs(info.get("automatic_captions"))

    return record
