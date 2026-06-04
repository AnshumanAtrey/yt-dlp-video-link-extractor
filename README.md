# yt-dlp Video Link Extractor - Any URL to Links, 1000+ Sites

Paste any video URL and get back the direct stream and download links plus full metadata. No files are stored, no RAM is burned - it resolves the links, it does not host the bytes.

Available as an [Apify Actor](https://apify.com/anshumanatrey/yt-dlp-video-link-extractor). $0.002 per run + $0.003 per URL processed + $0.04 per video resolved.

---

## What does it do?

Give it one or more video URLs. For each one it returns the direct media links (a single combined audio+video file when one exists, plus the best video-only and audio-only streams), every available format with its own URL, thumbnails, subtitles, and the metadata: title, uploader, duration, view count, upload date.

It is powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp), so it works on **1,872 sites** (verified at build time) - YouTube, Vimeo, SoundCloud, Twitch, Dailymotion, Reddit, Rumble, Bilibili and far more - not just YouTube. You paste a URL, you get the links. That is the whole tool.

It never downloads the actual file. That is deliberate: downloading large videos into cloud storage is slow, expensive, and memory-heavy. Resolving the link is instant and lets you fetch, stream, or transcode the media yourself.

## How is it different from a YouTube downloader?

| | Typical YouTube downloader | This actor |
|---|---|---|
| Sites | YouTube only | Any of 1,000+ yt-dlp sites |
| Output | An .mp4 file in storage | The direct links + full metadata |
| Speed | Waits for the full download | Resolves in seconds, no transfer |
| Cost driver | Per MB downloaded | Per URL + per video resolved (flat) |
| RAM | Buffers the video | Flat - nothing is downloaded |

Most actors in this space stop at YouTube. This one hands you the raw links for almost any video site, so you can build your own download, archive, or analysis pipeline on top.

## When should I use it?

- Get a direct, playable/downloadable link for a video on almost any site
- Pull metadata (title, duration, views, upload date, uploader) in bulk
- Feed stream URLs into your own downloader, transcoder, or player
- Grab subtitle and caption track URLs across languages
- Resolve every video in a playlist or channel to its links in one run

## What does it cost?

Pay-per-event:

- **$0.002** per run
- **$0.003** per URL processed (covers the resolve attempt for any URL)
- **$0.04** per video successfully resolved

A single video costs about **$0.045**. A failed URL costs only **$0.005** (run + URL fee, never the $0.04 resolution fee). Resolving a 50-video playlist costs about **$2.00**.

## Which inputs does it take?

| Field | Required | What it does |
|---|---|---|
| `urls` | yes | One or more video URLs. Any yt-dlp site works. A playlist/channel URL expands to its videos. |
| `includeFormats` | optional | Include the full format list (every resolution + codec with its URL) and all thumbnails. Default on. |
| `includeSubtitles` | optional | Include subtitle and auto-caption URLs by language. Default off. |
| `playlistLimit` | optional | Max videos to resolve from a playlist/channel. Default 50. |
| `proxyConfiguration` | optional | Route through a proxy. Use a residential group for sites that block datacenter IPs. |
| `cookies` | optional | Netscape-format cookie contents for age-restricted or login-gated videos. |

## What does the output look like?

One record per resolved video. The link-first fields:

```json
{
  "input_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "ok": true,
  "extractor": "youtube",
  "title": "Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)",
  "uploader": "Rick Astley",
  "duration": "3:33",
  "view_count": 1779349674,
  "upload_date": "2009-10-25",
  "best_url": "https://rr3---sn-gwpa-a3ve7.googlevideo.com/videoplayback?...",
  "best_url_kind": "combined",
  "best_resolution": "640x360",
  "best_video_url": "https://...  (up to 3840x2160)",
  "best_audio_url": "https://...  (.m4a)",
  "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/sddefault.jpg",
  "formats": [ { "format_id": "...", "ext": "mp4", "resolution": "1920x1080", "url": "..." } ]
}
```

- `best_url` is the single link most people want: a combined audio+video file when the site offers one, otherwise the best audio (for music/podcasts) or best video.
- `best_video_url` + `best_audio_url` matter for high-resolution sources. YouTube and Vimeo serve 1080p/4K video and audio as **separate** streams, so `best_url` (the combined file) tops out lower - use the two separate links for maximum quality.
- A failed URL returns `{ "input_url": ..., "ok": false, "error": "..." }`.

## How reliable is it?

yt-dlp is the most actively maintained extractor project in the world, and this actor pulls the latest release on every rebuild, so extractor fixes land automatically. Validated at build time across YouTube, YouTube Shorts, Vimeo (adaptive streams correctly resolved to a progressive file), and SoundCloud, plus playlist expansion and graceful handling of dead URLs.

## Common questions

**Q: Does it download the video file?** No. It returns the direct links. Fetch, stream, or transcode the media yourself. This keeps it fast and cheap.

**Q: Do the links expire?** Often yes. Many sites (YouTube especially) issue time-limited URLs that expire in a few hours. Use them promptly.

**Q: Which sites are supported?** Anything yt-dlp supports - 1,872 extractors at last build, including YouTube, TikTok, Vimeo, Twitch, SoundCloud, Reddit, Dailymotion, Rumble, Bilibili, Facebook and more.

**Q: A TikTok / Instagram / X link failed. Why?** Those platforms aggressively block datacenter IPs. Supply a residential proxy in `proxyConfiguration` and/or `cookies` and retry. Most other sites work with no proxy.

**Q: Can I pass a whole playlist or channel?** Yes. It expands to the videos inside, capped by `playlistLimit`.

**Q: Can I get just the audio?** Yes - `best_audio_url` is the best audio-only stream. For music sites it is also the `best_url`.

**Q: Am I charged for failed URLs?** Only the small per-URL processing fee ($0.003), which covers the resolve attempt. You are never charged the $0.04 resolution fee unless a video is actually resolved.

## Limitations

- Returns links, not downloaded files (by design).
- Direct links are time-limited by the source platform - use them quickly.
- Datacenter-blocked sites (TikTok, Instagram, X) need a residential proxy and/or cookies.
- Live streams resolve to HLS/DASH manifest URLs, not a single finished file.

## Ethical use

Download and use only content you have the right to access. Respect each platform's terms of service and copyright. This tool resolves publicly reachable media links; it does not bypass paywalls or DRM.

## Other actors by the same maintainer

Part of a portfolio of cloud tools built and maintained by **Anshuman Atrey** ([@AnshumanAtrey](https://github.com/AnshumanAtrey)). Custom features shipped within 24-48h for legitimate use cases via [atrey.dev](https://atrey.dev).

| Actor | Use case |
|---|---|
| [holehe-email-osint](https://apify.com/anshumanatrey/holehe-email-osint) | Email to registered accounts across 120+ sites |
| [social-analyzer](https://apify.com/anshumanatrey/social-analyzer) | Username across 900+ social sites |
| [theharvester-osint](https://apify.com/anshumanatrey/theharvester-osint) | Domain to emails + subdomains |
| [netintel](https://apify.com/anshumanatrey/netintel) | IP/domain to WHOIS + DNS + GeoIP + ports |
| [instagram-profile-intel-no-login](https://apify.com/anshumanatrey/instagram-profile-intel-no-login) | Instagram profile fields, no login |

## License

MIT (see LICENSE). Built on top of [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Unlicense / public domain).
