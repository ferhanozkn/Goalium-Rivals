#!/usr/bin/env python3
"""Small, dependency-free HTTP baseline for the local/staging health and modes API."""

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_once(url: str, timeout: float) -> tuple[bool, float, str]:
    started = time.perf_counter()
    try:
        with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=timeout) as response:
            body = response.read()
            elapsed = (time.perf_counter() - started) * 1000
            if response.status != 200:
                return False, elapsed, f"HTTP {response.status}"
            json.loads(body)
            return True, elapsed, ""
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        return False, (time.perf_counter() - started) * 1000, str(exc)


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/v1/health")
    parser.add_argument("--requests", type=int, default=80)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("requests ve concurrency pozitif olmalıdır")

    timings: list[float] = []
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [executor.submit(request_once, args.url, args.timeout) for _ in range(args.requests)]
        for future in as_completed(futures):
            ok, elapsed, error = future.result()
            timings.append(elapsed)
            if not ok:
                failures.append(error)

    summary = {
        "url": args.url,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "successes": len(timings) - len(failures),
        "failures": len(failures),
        "median_ms": round(statistics.median(timings), 2) if timings else None,
        "p95_ms": round(percentile(timings, 0.95), 2),
        "max_ms": round(max(timings), 2) if timings else None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if failures:
        print(json.dumps({"first_errors": failures[:3]}, ensure_ascii=False, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
