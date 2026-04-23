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

FILTERED_SEARCH_LATENCY = "filtered_search_latency_us"
UNFILTERED_SEARCH_LATENCY = "unfiltered_search_latency_us"
UPDATE_LATENCY = "update_latency_us"

# Per-level histograms
FILTER_LEVEL_LATENCIES = {
    i: f"filter_l{i}_latency_us" for i in range(1, 6)
}


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
    op: str  # "filtered_search" | "unfiltered_search" | "update" | "rate_limit"
    latency_us: int
    success: bool
    filter_level: int = 0
    result_count: int = 0


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

    def record_filtered_search(
        self, latency_us: int, success: bool, filter_level: int, result_count: int = 0,
    ) -> None:
        latency_us = max(1, latency_us)
        self._get_or_create_hist(FILTERED_SEARCH_LATENCY).record_value(latency_us)
        # Also record in per-level histogram
        level_hist_name = FILTER_LEVEL_LATENCIES.get(filter_level)
        if level_hist_name:
            self._get_or_create_hist(level_hist_name).record_value(latency_us)

        self._counters["filtered_search_total"] += 1
        self._counters[f"filter_l{filter_level}_total"] += 1
        if not success:
            self._counters["filtered_search_error"] += 1
        self._timeline.append(TimelineEntry(
            self._elapsed(), "filtered_search", latency_us, success,
            filter_level=filter_level, result_count=result_count,
        ))

    def record_unfiltered_search(self, latency_us: int, success: bool, result_count: int = 0) -> None:
        latency_us = max(1, latency_us)
        self._get_or_create_hist(UNFILTERED_SEARCH_LATENCY).record_value(latency_us)
        self._counters["unfiltered_search_total"] += 1
        if not success:
            self._counters["unfiltered_search_error"] += 1
        self._timeline.append(TimelineEntry(
            self._elapsed(), "unfiltered_search", latency_us, success,
            result_count=result_count,
        ))

    def record_update(self, latency_us: int, success: bool) -> None:
        latency_us = max(1, latency_us)
        self._get_or_create_hist(UPDATE_LATENCY).record_value(latency_us)
        self._counters["update_total"] += 1
        if not success:
            self._counters["update_error"] += 1
        self._timeline.append(
            TimelineEntry(self._elapsed(), "update", latency_us, success)
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
            "metadata": {"duration_s": self._elapsed()},
        }

        all_hists = [FILTERED_SEARCH_LATENCY, UNFILTERED_SEARCH_LATENCY, UPDATE_LATENCY]
        all_hists.extend(FILTER_LEVEL_LATENCIES.values())
        for hist_name in all_hists:
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
