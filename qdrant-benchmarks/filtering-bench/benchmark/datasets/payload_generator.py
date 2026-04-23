from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

log = logging.getLogger(__name__)

REGIONS = [
    "us-east", "us-west", "eu-west", "eu-central", "asia-pac",
    "latam", "mena", "africa", "oceania", "canada",
]

COUNTRIES_BY_REGION = {
    "us-east": ["US-NY", "US-FL", "US-MA", "US-PA", "US-VA"],
    "us-west": ["US-CA", "US-WA", "US-OR", "US-CO", "US-AZ"],
    "eu-west": ["UK", "FR", "ES", "PT", "IE"],
    "eu-central": ["DE", "NL", "AT", "CH", "PL"],
    "asia-pac": ["JP", "KR", "SG", "AU", "IN"],
    "latam": ["BR", "MX", "AR", "CO", "CL"],
    "mena": ["AE", "SA", "EG", "IL", "TR"],
    "africa": ["ZA", "NG", "KE", "GH", "MA"],
    "oceania": ["AU-SYD", "AU-MEL", "NZ", "FJ", "PG"],
    "canada": ["CA-ON", "CA-BC", "CA-QC", "CA-AB", "CA-NS"],
}

CITIES_BY_COUNTRY = {
    "US-NY": ["new-york", "brooklyn", "buffalo", "albany"],
    "US-CA": ["los-angeles", "san-francisco", "san-diego", "sacramento"],
    "UK": ["london", "manchester", "birmingham", "edinburgh"],
    "DE": ["berlin", "munich", "hamburg", "frankfurt"],
    "JP": ["tokyo", "osaka", "kyoto", "yokohama"],
    "BR": ["sao-paulo", "rio", "brasilia", "salvador"],
}

DEVICE_TYPES = ["mobile", "desktop", "tablet", "ctv"]

CATEGORY_L1 = [
    "electronics", "fashion", "home", "auto", "health",
    "finance", "travel", "food", "entertainment", "education",
]

CATEGORY_L2_BY_L1 = {
    "electronics": ["phones", "laptops", "audio", "gaming", "cameras"],
    "fashion": ["mens", "womens", "kids", "accessories", "shoes"],
    "home": ["furniture", "kitchen", "garden", "decor", "tools"],
    "auto": ["cars", "parts", "insurance", "rentals", "ev"],
    "health": ["pharma", "fitness", "nutrition", "mental", "devices"],
    "finance": ["banking", "invest", "insurance", "crypto", "loans"],
    "travel": ["flights", "hotels", "packages", "cruises", "car-rental"],
    "food": ["delivery", "grocery", "restaurants", "recipes", "meal-kits"],
    "entertainment": ["streaming", "gaming", "events", "music", "sports"],
    "education": ["online", "k12", "higher-ed", "corporate", "languages"],
}

CATEGORY_L3_BY_L2 = {
    "phones": ["iphone", "android", "accessories", "cases"],
    "laptops": ["macbook", "windows", "chromebook", "parts"],
    "mens": ["shirts", "pants", "suits", "outerwear"],
    "womens": ["dresses", "tops", "bottoms", "outerwear"],
    "furniture": ["sofas", "tables", "beds", "chairs"],
    "cars": ["sedan", "suv", "truck", "sports"],
    "banking": ["checking", "savings", "credit-cards", "mortgages"],
    "flights": ["domestic", "international", "business", "budget"],
    "streaming": ["movies", "tv-shows", "live", "sports"],
    "online": ["courses", "bootcamps", "certifications", "tutorials"],
}

TAGS_POOL = [
    "premium", "budget", "new", "trending", "seasonal",
    "clearance", "exclusive", "limited", "popular", "recommended",
    "featured", "sale", "eco-friendly", "luxury", "value",
    "bestseller", "editor-pick", "flash-deal", "member-only", "local",
]

NUM_TENANTS = 50


@dataclass
class FilterPayload:
    tenant_id: str
    region: str
    country: str
    city: str
    device_type: str
    category_l1: str
    category_l2: str
    category_l3: str
    budget: int
    bid_price: float
    is_active: bool
    updated_at: int
    quality_score: float
    tags: list[str]

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "region": self.region,
            "country": self.country,
            "city": self.city,
            "device_type": self.device_type,
            "category_l1": self.category_l1,
            "category_l2": self.category_l2,
            "category_l3": self.category_l3,
            "budget": self.budget,
            "bid_price": self.bid_price,
            "is_active": self.is_active,
            "updated_at": self.updated_at,
            "quality_score": self.quality_score,
            "tags": self.tags,
        }


class PayloadGenerator:
    def __init__(self, seed: int = 42) -> None:
        self._rng = np.random.default_rng(seed)
        self._all_countries = []
        self._country_to_region: dict[str, str] = {}
        for region, countries in COUNTRIES_BY_REGION.items():
            for country in countries:
                self._all_countries.append(country)
                self._country_to_region[country] = region

        self._all_cities: dict[str, list[str]] = {}
        for country, cities in CITIES_BY_COUNTRY.items():
            self._all_cities[country] = cities

        self._all_l2: dict[str, list[str]] = CATEGORY_L2_BY_L1
        self._all_l3: dict[str, list[str]] = CATEGORY_L3_BY_L2

    def generate(self, point_id: int) -> FilterPayload:
        # Tenant assignment: zipf-like distribution (some tenants have more data)
        tenant_idx = int(self._rng.zipf(1.5)) % NUM_TENANTS
        tenant_id = f"tenant_{tenant_idx:03d}"

        # Geography: hierarchical
        region = self._rng.choice(REGIONS)
        countries = COUNTRIES_BY_REGION[region]
        country = self._rng.choice(countries)
        cities = self._all_cities.get(country, [f"{country}-city-{i}" for i in range(4)])
        city = self._rng.choice(cities)

        device_type = self._rng.choice(DEVICE_TYPES)

        # Category: hierarchical
        cat_l1 = self._rng.choice(CATEGORY_L1)
        cat_l2_options = self._all_l2.get(cat_l1, ["general"])
        cat_l2 = self._rng.choice(cat_l2_options)
        cat_l3_options = self._all_l3.get(cat_l2, [f"{cat_l2}-sub-{i}" for i in range(4)])
        cat_l3 = self._rng.choice(cat_l3_options)

        budget = int(self._rng.integers(100, 100_001))
        bid_price = round(float(self._rng.uniform(1.0, 500.0)), 2)
        is_active = bool(self._rng.random() < 0.85)  # 85% active
        # Timestamps spread over last 30 days
        base_ts = 1_700_000_000
        updated_at = base_ts + int(self._rng.integers(0, 30 * 86_400))
        quality_score = round(float(self._rng.beta(2, 5)), 4)

        num_tags = int(self._rng.integers(1, 6))
        tags = list(self._rng.choice(TAGS_POOL, size=num_tags, replace=False))

        return FilterPayload(
            tenant_id=tenant_id,
            region=region,
            country=country,
            city=city,
            device_type=device_type,
            category_l1=cat_l1,
            category_l2=cat_l2,
            category_l3=cat_l3,
            budget=budget,
            bid_price=bid_price,
            is_active=is_active,
            updated_at=updated_at,
            quality_score=quality_score,
            tags=tags,
        )

    def generate_batch(self, start_id: int, count: int) -> list[dict]:
        return [self.generate(start_id + i).to_dict() for i in range(count)]


# Pre-defined payload index configurations used during benchmark setup.
# Uses a simple dataclass to avoid importing from clients (circular dep).
@dataclass
class _IndexField:
    field_name: str
    field_type: str

PAYLOAD_INDEX_FIELDS = [
    _IndexField(field_name="tenant_id", field_type="keyword"),
    _IndexField(field_name="region", field_type="keyword"),
    _IndexField(field_name="country", field_type="keyword"),
    _IndexField(field_name="city", field_type="keyword"),
    _IndexField(field_name="device_type", field_type="keyword"),
    _IndexField(field_name="category_l1", field_type="keyword"),
    _IndexField(field_name="category_l2", field_type="keyword"),
    _IndexField(field_name="category_l3", field_type="keyword"),
    _IndexField(field_name="budget", field_type="integer"),
    _IndexField(field_name="bid_price", field_type="float"),
    _IndexField(field_name="is_active", field_type="bool"),
    _IndexField(field_name="updated_at", field_type="integer"),
    _IndexField(field_name="quality_score", field_type="float"),
]
