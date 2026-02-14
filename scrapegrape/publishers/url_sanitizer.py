"""URL sanitization and domain extraction using w3lib.

Normalizes URLs to canonical forms for deduplication:
- Strips www. from hostname
- Enforces https scheme
- Strips fragments
- Sorts query parameters
- Strips tracking parameters (utm_*, fbclid, gclid, etc.)
- Preserves trailing slashes
"""

from urllib.parse import urlparse, urlunparse

from w3lib.url import canonicalize_url, url_query_cleaner


TRACKING_PARAMS = [
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "gclsrc",
    "dclid",
    "gbraid",
    "wbraid",
    "msclkid",
    "twclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "oly_anon_id",
    "oly_enc_id",
    "_openstat",
    "vero_id",
    "wickedid",
    "yclid",
    "rb_clickid",
    "s_cid",
    "mkt_tok",
    "trk",
    "trkCampaign",
    "trkInfo",
]


def sanitize_url(url: str) -> str:
    """Normalize a URL to its canonical form for deduplication.

    Applies the following transformations:
    1. Canonicalize (sort query params, strip fragments, normalize encoding)
    2. Strip tracking parameters
    3. Strip www. from hostname
    4. Enforce https scheme

    Args:
        url: The URL to sanitize.

    Returns:
        The canonical URL string.
    """
    # Step 1: Canonicalize - sorts query params, strips fragments, normalizes encoding
    canonical = canonicalize_url(url, keep_fragments=False)

    # Step 2: Strip tracking params (remove=True means remove these params)
    canonical = url_query_cleaner(canonical, TRACKING_PARAMS, remove=True)

    # Step 3 & 4: Strip www. and enforce https
    parsed = urlparse(canonical)

    hostname = parsed.hostname or ""
    if hostname.startswith("www."):
        hostname = hostname[4:]

    cleaned = urlunparse((
        "https",
        hostname + (f":{parsed.port}" if parsed.port and parsed.port != 443 else ""),
        parsed.path,
        parsed.params,
        parsed.query,
        "",  # no fragment
    ))

    return cleaned


def extract_domain(url: str) -> str:
    """Extract the canonical domain from a URL.

    Strips www. prefix but preserves other subdomains.

    Args:
        url: The URL to extract the domain from.

    Returns:
        The canonical domain string (e.g., 'nytimes.com', 'blog.example.com').
    """
    sanitized = sanitize_url(url)
    parsed = urlparse(sanitized)
    return parsed.hostname or ""
