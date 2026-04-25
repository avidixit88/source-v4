from __future__ import annotations

import pandas as pd

from services.search_service import (
    build_cas_supplier_queries,
    direct_supplier_search_urls,
    filter_likely_supplier_results,
    serpapi_search,
    discover_product_links_from_page,
)
from services.page_extractor import extract_product_data_from_url


def discover_live_suppliers(
    cas_number: str,
    chemical_name: str | None = None,
    serpapi_key: str | None = None,
    max_pages_to_extract: int = 12,
    include_direct_links: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Discover supplier pages and extract visible product/pricing fields.

    Returns:
        extracted_df: rows suitable for normalization/ranking
        discovery_df: raw search/direct URLs for auditability
    """
    queries = build_cas_supplier_queries(cas_number, chemical_name)
    discovered = serpapi_search(queries, serpapi_key or "")
    discovered = filter_likely_supplier_results(discovered)

    if include_direct_links:
        discovered.extend(direct_supplier_search_urls(cas_number))

    # v4: expand search pages into likely product-detail pages before extraction.
    # Keep originals too for audit/source links, but prioritize expanded product pages.
    expanded = []
    for result in discovered[:20]:
        expanded.extend(discover_product_links_from_page(result, cas_number, max_links=4))

    candidate_results = expanded + discovered

    # De-dupe by URL while preserving order.
    seen = set()
    unique_results = []
    for result in candidate_results:
        if result.url in seen:
            continue
        seen.add(result.url)
        unique_results.append(result)

    discovery_df = pd.DataFrame([r.__dict__ for r in unique_results])

    extracted_rows = []
    for result in unique_results[:max_pages_to_extract]:
        extracted = extract_product_data_from_url(
            cas_number,
            result.url,
            supplier_hint=result.supplier_hint or None,
            discovery_title=result.title,
            discovery_snippet=result.snippet,
        )
        extracted_rows.append(
            {
                "cas_number": cas_number,
                "chemical_name": chemical_name or "",
                "supplier": extracted.supplier,
                "region": "Unknown",
                "purity": extracted.purity or "Not visible",
                "pack_size": extracted.pack_size,
                "pack_unit": extracted.pack_unit,
                "listed_price_usd": extracted.listed_price_usd,
                "stock_status": extracted.stock_status,
                "lead_time": "Not visible",
                "product_url": extracted.product_url,
                "notes": extracted.evidence,
                "page_title": extracted.title,
                "cas_exact_match": extracted.cas_exact_match,
                "extraction_status": extracted.extraction_status,
                "extraction_confidence": extracted.confidence,
                "extraction_method": extracted.extraction_method,
                "raw_matches": extracted.raw_matches,
                "data_source": "live_extraction",
            }
        )

    return pd.DataFrame(extracted_rows), discovery_df
