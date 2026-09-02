"""Check that public URLs actually resolve, and record what they resolved to.

HEAD first, GET on refusal: some sites (GitHub release redirects among them)
answer HEAD differently or not at all, and a false "dead link" must not block
a release. Redirects are followed and the FINAL url is what gets recorded —
that is the whole point for `releases/latest`, which must land on the tag we
just published.

Usage:
    python scripts/check_links.py https://github.com/Lavr5000/Transkribator/releases/latest
    python scripts/check_links.py --json URL [URL ...]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Transkribator-link-check/1.0"
TIMEOUT = 20


def check(url: str) -> dict:
    result = {"url": url, "checked_at": datetime.now(timezone.utc).isoformat()}
    for method in ("HEAD", "GET"):
        t0 = time.monotonic()
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                result.update(method=method, status=resp.status, final_url=resp.url,
                              elapsed_s=round(time.monotonic() - t0, 2), error=None)
                return result
        except urllib.error.HTTPError as e:
            result.update(method=method, status=e.code, final_url=e.url,
                          elapsed_s=round(time.monotonic() - t0, 2), error=str(e))
            if method == "GET" or e.code not in (403, 404, 405, 501):
                return result
        except Exception as e:                      # URLError, timeout, TLS…
            result.update(method=method, status=None, final_url=None,
                          elapsed_s=round(time.monotonic() - t0, 2),
                          error=f"{type(e).__name__}: {e}")
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--expect", help="substring the final URL must contain (one URL only)")
    args = ap.parse_args()

    results = [check(u) for u in args.urls]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(f"{r['status']}  {r['method']:4}  {r['elapsed_s']:>5}s  {r['url']}")
            if r["final_url"] and r["final_url"] != r["url"]:
                print(f"      -> {r['final_url']}")
            if r["error"]:
                print(f"      !  {r['error']}")
            print(f"      at {r['checked_at']}")

    ok = all(r["status"] and 200 <= r["status"] < 400 for r in results)
    if args.expect:
        final = results[0].get("final_url") or ""
        if args.expect not in final:
            print(f"EXPECT FAILED: {args.expect!r} not in {final!r}", file=sys.stderr)
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
