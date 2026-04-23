from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from benchmark.datasets.payload_generator import (
    CATEGORY_L1,
    CATEGORY_L2_BY_L1,
    CATEGORY_L3_BY_L2,
    COUNTRIES_BY_REGION,
    DEVICE_TYPES,
    NUM_TENANTS,
    REGIONS,
)

log = logging.getLogger(__name__)


@dataclass
class FilterScenario:
    name: str
    level: int  # 1-5 complexity
    description: str
    filter_condition: dict  # system-agnostic filter


def _must(*conditions: dict) -> dict:
    return {"must": list(conditions)}


def _match(field: str, value: str | int | bool) -> dict:
    return {"field": field, "match": value}


def _match_any(field: str, values: list) -> dict:
    return {"field": field, "match_any": values}


def _range(field: str, gte: float | int | None = None, lte: float | int | None = None) -> dict:
    r: dict = {}
    if gte is not None:
        r["gte"] = gte
    if lte is not None:
        r["lte"] = lte
    return {"field": field, "range": r}


class FilterScenarioGenerator:
    def __init__(self, seed: int = 42) -> None:
        self._rng = np.random.default_rng(seed)

    def generate_l1(self) -> FilterScenario:
        """Single field: tenant isolation. ~2% selectivity."""
        tenant_idx = int(self._rng.integers(0, NUM_TENANTS))
        tenant_id = f"tenant_{tenant_idx:03d}"
        return FilterScenario(
            name="L1_tenant_only",
            level=1,
            description=f"Single tenant filter: {tenant_id}",
            filter_condition=_must(_match("tenant_id", tenant_id)),
        )

    def generate_l2(self) -> FilterScenario:
        """Two fields: tenant + region. ~0.2% selectivity."""
        tenant_idx = int(self._rng.integers(0, NUM_TENANTS))
        tenant_id = f"tenant_{tenant_idx:03d}"
        region = self._rng.choice(REGIONS)
        return FilterScenario(
            name="L2_tenant_region",
            level=2,
            description=f"Tenant + region: {tenant_id}, {region}",
            filter_condition=_must(
                _match("tenant_id", tenant_id),
                _match("region", region),
            ),
        )

    def generate_l3(self) -> FilterScenario:
        """Multi-field: tenant + geo + category + device. ~0.004% selectivity."""
        tenant_idx = int(self._rng.integers(0, NUM_TENANTS))
        tenant_id = f"tenant_{tenant_idx:03d}"
        region = self._rng.choice(REGIONS)
        country = self._rng.choice(COUNTRIES_BY_REGION[region])
        cat_l1 = self._rng.choice(CATEGORY_L1)
        device = self._rng.choice(DEVICE_TYPES)
        return FilterScenario(
            name="L3_multi_field",
            level=3,
            description=f"Tenant + country + category + device",
            filter_condition=_must(
                _match("tenant_id", tenant_id),
                _match("country", country),
                _match("category_l1", cat_l1),
                _match("device_type", device),
                _match("is_active", True),
            ),
        )

    def generate_l4(self) -> FilterScenario:
        """Full hierarchy: tenant + geo chain + category chain. ~0.0004% selectivity."""
        tenant_idx = int(self._rng.integers(0, NUM_TENANTS))
        tenant_id = f"tenant_{tenant_idx:03d}"
        region = self._rng.choice(REGIONS)
        country = self._rng.choice(COUNTRIES_BY_REGION[region])
        cat_l1 = self._rng.choice(CATEGORY_L1)
        cat_l2 = self._rng.choice(CATEGORY_L2_BY_L1.get(cat_l1, ["general"]))
        cat_l3_options = CATEGORY_L3_BY_L2.get(cat_l2, [f"{cat_l2}-sub-0"])
        cat_l3 = self._rng.choice(cat_l3_options)
        device = self._rng.choice(DEVICE_TYPES)
        return FilterScenario(
            name="L4_full_hierarchy",
            level=4,
            description=f"Full geo + category hierarchy",
            filter_condition=_must(
                _match("tenant_id", tenant_id),
                _match("region", region),
                _match("country", country),
                _match("category_l1", cat_l1),
                _match("category_l2", cat_l2),
                _match("category_l3", cat_l3),
                _match("device_type", device),
                _match("is_active", True),
            ),
        )

    def generate_l5(self) -> FilterScenario:
        """Hierarchy + range: full hierarchy + budget/quality ranges. ~0.0001% selectivity."""
        tenant_idx = int(self._rng.integers(0, NUM_TENANTS))
        tenant_id = f"tenant_{tenant_idx:03d}"
        region = self._rng.choice(REGIONS)
        country = self._rng.choice(COUNTRIES_BY_REGION[region])
        cat_l1 = self._rng.choice(CATEGORY_L1)
        cat_l2 = self._rng.choice(CATEGORY_L2_BY_L1.get(cat_l1, ["general"]))
        device = self._rng.choice(DEVICE_TYPES)
        budget_min = int(self._rng.integers(1000, 50000))
        budget_max = budget_min + int(self._rng.integers(5000, 50000))
        quality_min = round(float(self._rng.uniform(0.3, 0.6)), 2)
        return FilterScenario(
            name="L5_hierarchy_range",
            level=5,
            description=f"Full hierarchy + budget/quality range filters",
            filter_condition=_must(
                _match("tenant_id", tenant_id),
                _match("region", region),
                _match("country", country),
                _match("category_l1", cat_l1),
                _match("category_l2", cat_l2),
                _match("device_type", device),
                _match("is_active", True),
                _range("budget", gte=budget_min, lte=budget_max),
                _range("quality_score", gte=quality_min),
            ),
        )

    def generate(self, level: int) -> FilterScenario:
        generators = {
            1: self.generate_l1,
            2: self.generate_l2,
            3: self.generate_l3,
            4: self.generate_l4,
            5: self.generate_l5,
        }
        return generators[level]()

    def generate_mixed(self, weights: list[float] | None = None) -> FilterScenario:
        if weights is None:
            weights = [0.20, 0.25, 0.25, 0.20, 0.10]
        level = int(self._rng.choice([1, 2, 3, 4, 5], p=weights))
        return self.generate(level)
