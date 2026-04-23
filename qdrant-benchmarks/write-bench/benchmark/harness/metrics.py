from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from hdrh.histogram import HdrHistogram

HIST_MIN_VALUE_US = 1
HIST_MAX_VALUE_US = 60_000_000  # 60 seconds
HIST_SIGNIFICANT_DIGITS = 3

WRITE_LATENCY = "write_latency_us"
READ_LATENCY = "read_latency_us"
FRESHNESS_LATENCY = "freshness_latency_us"


@dataclass
class PercentileReport:
    p50: float  # milliseconds
    p95: float
    p99: float
    p999: float
    max: float
    count: int
    mean: float


@dataclass
class TimelineEntry:
    elapsed_s: float
    op: str  # "write" | "read" | "freshness" | "rate_limit"
    latency_us: int
    success: bool
    recall: float = 1.0


class MetricsCollector:
    def __init__(self) -> None:
        self._histograms: dict[str, HdrHistogram] = {}
        self._counters: dict[str, int] = defaultdict(int)
        self._start_time: float | None = None
        self._timeline: list[TimelineEntry] = []

    def _get_or_create_hist(self, name: str) -> HdrHistogram:
        if name not in self._histograms:
            self._histograms[name] = HdrHistogram(
                HIST_MIN_VALUE_US, HIST_MAX_VALUE_US, HIST_SIGNIFICANT_DIGITS
            )
        return self._histograms[name]

    def start(self) -> None:
        self._start_time = time.monotonic()

    def _elapsed(self) -> float:
        if self._start_time is None:
            return 0.0
        return time.monotonic() - self._start_time

    def record_write(self, latency_us: int, success: bool) -> None:
        latency_us = max(1, latency_us)
        self._get_or_create_hist(WRITE_LATENCY).record_value(latency_us)
        self._counters["write_total"] += 1
        if not success:
            self._counters["write_error"] += 1
        self._timeline.append(
            TimelineEntry(self._elapsed(), "write", latency_us, success)
        )

    def record_read(self, latency_us: int, success: bool, recall: float = 1.0) -> None:
        latency_us = max(1, latency_us)
        self._get_or_create_hist(READ_LATENCY).record_value(latency_us)
        self._counters["read_total"] += 1
        if not success:
            self._counters["read_error"] += 1
        self._timeline.append(
            TimelineEntry(self._elapsed(), "read", latency_us, success, recall)
        )

    def record_freshness(self, latency_us: int, success: bool) -> None:
        latency_us = max(1, latency_us)
        self._get_or_create_hist(FRESHNESS_LATENCY).record_value(latency_us)
        self._counters["freshness_total"] += 1
        if not success:
            self._counters["freshness_timeout"] += 1
        self._timeline.append(
            TimelineEntry(self._elapsed(), "freshness", latency_us, success)
        )

    def record_rate_limit(self, system: str, retry_after_s: float | None) -> None:
        self._counters["rate_limit_total"] += 1
        self._timeline.append(
            TimelineEntry(self._elapsed(), "rate_limit", 0, False)
        )

    def get_percentiles(self, histogram_name: str) -> PercentileReport:
        hist = self._histograms.get(histogram_name)
        if hist is None or hist.total_count == 0:
            return PercentileReport(0, 0, 0, 0, 0, 0, 0)

        return PercentileReport(
            p50=hist.get_value_at_percentile(50) / 1000.0,
            p95=hist.get_value_at_percentile(95) / 1000.0,
            p99=hist.get_value_at_percentile(99) / 1000.0,
            p999=hist.get_value_at_percentile(99.9) / 1000.0,
            max=hist.get_value_at_percentile(100) / 1000.0,
            count=hist.total_count,
            mean=hist.get_mean_value() / 1000.0,
        )

    def export_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "histograms": {},
            "counters": dict(self._counters),
            "timeline": [asdict(e) for e in self._timeline],
            "metadata": {
                "duration_s": self._elapsed(),
            },
        }

        for hist_name in [WRITE_LATENCY, READ_LATENCY, FRESHNESS_LATENCY]:
            report = self.get_percentiles(hist_name)
            data["histograms"][hist_name] = asdict(report)

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def export_hdr(self, path: Path, histogram_name: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        hist = self._histograms.get(histogram_name)
        if hist is None:
            return
        encoded = hist.encode()
        with open(path, "wb") as f:
            f.write(encoded)
