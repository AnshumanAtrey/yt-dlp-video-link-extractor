from src.resolve import build_ydl_opts, is_bot_check, vimeo_player_url


def test_vimeo_page_links_go_to_the_public_player():
    assert vimeo_player_url("https://vimeo.com/76979871") == "https://player.vimeo.com/video/76979871"
    assert vimeo_player_url("https://www.vimeo.com/76979871?share=copy") == "https://player.vimeo.com/video/76979871"
    assert vimeo_player_url("https://vimeo.com/channels/staffpicks/76979871") == "https://player.vimeo.com/video/76979871"
    assert vimeo_player_url("https://vimeo.com/groups/motion/videos/76979871") == "https://player.vimeo.com/video/76979871"


def test_vimeo_unlisted_hash_is_kept():
    assert (vimeo_player_url("https://vimeo.com/392479337/a52724358e")
            == "https://player.vimeo.com/video/392479337?h=a52724358e")


def test_other_links_are_left_alone():
    for url in ("https://player.vimeo.com/video/76979871", "https://vimeo.com/showcase/123",
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://www.dailymotion.com/video/x5kesuj"):
        assert vimeo_player_url(url) is None


def test_bot_check_is_recognized_only_on_failures():
    blocked = {"ok": False, "error": "ERROR: [youtube] jNQXAC9IVRw: Sign in to confirm you’re not a bot. Use --cookies"}
    assert is_bot_check(blocked)
    assert not is_bot_check({"ok": False, "error": "ERROR: [youtube] x: Sign in to confirm your age."})
    assert not is_bot_check({"ok": True, "title": "not a bot"})


def test_errors_are_never_colored():
    assert build_ydl_opts()["color"] == "never"
