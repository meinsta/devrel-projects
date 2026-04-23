"""Product text construction for encoding"""

from typing import Dict, List, Optional


def build_product_text(
    title: str,
    brand: str = "",
    description: str = "",
    bullets: Optional[List[str]] = None,
    attributes: Optional[Dict[str, str]] = None,
    max_length: int = 512,
) -> str:
    """
    Construct product text for encoding.

    Format: [brand] title | description | bullet1 | bullet2 | attr=val

    This creates a consistent text representation for products that works well
    with sparse encoders like SPLADE. The format preserves important lexical
    signals (brand names, SKUs) while providing semantic context.

    Args:
        title: Product title (required)
        brand: Brand name (optional)
        description: Product description (optional)
        bullets: List of bullet points (optional)
        attributes: Dict of attribute name -> value (optional)
        max_length: Maximum character length for the final text

    Returns:
        Formatted product text string
    """
    parts = []

    # Add brand prefix if available
    if brand and brand.strip():
        parts.append(f"[{brand.strip()}]")

    # Add title (required)
    if title and title.strip():
        parts.append(title.strip())

    # Add truncated description
    if description and description.strip():
        desc_text = description.strip()[:200]
        parts.append(desc_text)

    # Add top bullet points
    if bullets:
        clean_bullets = [b.strip() for b in bullets if b and b.strip()]
        parts.extend(clean_bullets[:3])

    # Add key attributes
    if attributes:
        attr_parts = [f"{k}={v}" for k, v in list(attributes.items())[:5] if v]
        parts.extend(attr_parts)

    # Join with separator
    text = " | ".join(parts)

    # Truncate to max length (approximate - actual tokenization may differ)
    if len(text) > max_length * 4:  # ~4 chars per token estimate
        text = text[: max_length * 4]

    return text


def build_query_text(query: str) -> str:
    """
    Process query text for encoding.

    For most cases, queries are used as-is. This function is here
    for consistency and future query preprocessing needs.

    Args:
        query: Raw query string

    Returns:
        Processed query string
    """
    return query.strip()


def build_training_example(
    query: str,
    positive_product: Dict,
    negative_products: Optional[List[Dict]] = None,
) -> Dict:
    """
    Build a training example with query, positive, and optionally negative products.

    Args:
        query: Query text
        positive_product: Dict with product fields (title, brand, description, etc.)
        negative_products: Optional list of negative product dicts

    Returns:
        Dict with anchor, positive, and optionally negative texts
    """
    example = {
        "anchor": build_query_text(query),
        "positive": build_product_text(
            title=positive_product.get("title", ""),
            brand=positive_product.get("brand", ""),
            description=positive_product.get("description", ""),
            bullets=positive_product.get("bullets", []),
        ),
    }

    if negative_products:
        example["negative"] = [
            build_product_text(
                title=p.get("title", ""),
                brand=p.get("brand", ""),
                description=p.get("description", ""),
                bullets=p.get("bullets", []),
            )
            for p in negative_products
        ]

    return example
