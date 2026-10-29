#!/usr/bin/env bash
# Run a built actor image locally (Apify SDK local storage, no platform) on a fixed set of public
# videos and print a score: videos resolved, plus those with a combined audio+video link (the
# YouTube one needs the Deno runtime, so a broken JS challenge solver lowers the score).
#
#   scripts/smoke-test.sh <image>      -> prints an integer on stdout, one line per video on stderr
#
# Exits non-zero if the container fails. The score alone proves little, since sites are flaky and
# YouTube may refuse runner IPs; .github/workflows/yt-dlp-update.yml runs the current and the
# candidate image back to back and compares the two scores.
set -euo pipefail
image=$1
dir=$(mktemp -d)
mkdir -p "$dir/key_value_stores/default"
cat > "$dir/key_value_stores/default/INPUT.json" <<'EOF'
{"urls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://player.vimeo.com/video/76979871",
          "https://www.dailymotion.com/video/x5kesuj", "https://soundcloud.com/ethmusic/lostin-powers-she-so-heavy"],
 "includeFormats": false}
EOF
timeout 600 docker run --rm -v "$dir:/usr/src/app/storage" "$image" >&2
sudo chown -R "$(id -u)" "$dir" 2>/dev/null || true
python3 - "$dir" <<'EOF'
import json, pathlib, sys
rows = [json.loads(p.read_text()) for p in pathlib.Path(sys.argv[1], 'datasets', 'default').glob('*.json')
        if p.name != '__metadata__.json']
for r in rows:
    print(('ok  ' if r.get('ok') else 'FAIL'), r.get('best_url_kind') or (r.get('error') or '')[:150], r.get('input_url'),
          file=sys.stderr)
print(sum(bool(r.get('ok')) for r in rows) + sum(r.get('best_url_kind') == 'combined' for r in rows))
EOF
