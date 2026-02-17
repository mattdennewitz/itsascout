# Phase 10: Article Metadata - Research

**Researched:** 2026-02-17
**Domain:** HTML structured data extraction, paywall detection, LLM metadata profiling
**Confidence:** HIGH

## Summary

This phase adds article-level metadata extraction to the existing publisher pipeline. The codebase already has a mature pipeline supervisor pattern (9 sequential steps), extruct as a dependency (v0.18.0), and pydantic-ai agents for LLM-based analysis. The new work adds three steps (article extraction, paywall detection, metadata profile) that run after the existing publisher steps, plus a new ArticleMetadata model.

Extruct supports JSON-LD, OpenGraph, and Microdata natively but does NOT support Twitter Cards. Twitter Cards use `<meta name="twitter:*">` tags which must be extracted via a simple HTMLParser (consistent with the project's existing pattern of using stdlib html.parser). The paywall detection combines schema.org `isAccessibleForFree` markup with heuristic fallback signals. The LLM metadata profile follows the exact same pydantic-ai Agent pattern used by `terms_discovery_agent` and `terms_evaluation_agent`.

**Primary recommendation:** Follow the existing step function pattern exactly -- each new step is a function in `steps.py` returning a dict, orchestrated by the supervisor, with results saved to a new `article_result` JSONField on ResolutionJob and a new ArticleMetadata model.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Extract ~10 key fields per format: headline, author, datePublished, dateModified, image, description, publisher name, isAccessibleForFree, wordCount, articleSection, inLanguage, keywords
- Keep fields per-format (JSON-LD section, OpenGraph section, Microdata section, Twitter Cards section) -- not merged into one canonical view
- Twitter Cards treated as a 4th format alongside JSON-LD, OpenGraph, Microdata
- Store extracted key fields only -- no raw extruct dump
- Use FetchStrategyManager for article fetch; reuse homepage HTML if submitted URL matches homepage
- Three new pipeline steps: "Article Extraction", "Paywall Detection", "Metadata Profile"
- Run after all publisher steps (steps 10, 11, 12 after existing 1-9)
- Step summaries show key findings: extraction shows "headline, author, 8 fields"; paywall shows "isAccessibleForFree: true"; profile shows first ~50 chars of summary
- New ArticleMetadata model with ForeignKey to both ResolutionJob and Publisher
- pydantic-ai agent (GPT-4.1-nano) for LLM metadata profiling, consistent with existing ToS agents
- Article steps skippable by freshness TTL if the exact same article URL was analyzed recently
- Primary paywall: check isAccessibleForFree schema.org markup
- Fallback: heuristic detection with high confidence bar -- only report "paywalled" when multiple strong signals agree
- Detect metered access patterns as distinct from hard paywall
- Four paywall statuses: free, paywalled (hard), metered, unknown
- Store paywall status on ArticleMetadata, as step result on ResolutionJob, and as publisher-level signal

### Claude's Discretion
- Specific heuristic signals to use for paywall detection
- extruct configuration and parsing details
- LLM prompt design for metadata profiling
- Exact ArticleMetadata model field names and types
- How to determine publisher-level paywall signal from per-article data

### Deferred Ideas (OUT OF SCOPE)
None

</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| extruct | 0.18.0 | Extract JSON-LD, OpenGraph, Microdata from HTML | Already in project deps, battle-tested by Scrapinghub |
| pydantic-ai-slim[openai] | >=0.4.2 | LLM agent for metadata profiling | Already used for ToS discovery/evaluation agents |
| html.parser (stdlib) | N/A | Extract Twitter Card meta tags | Project convention (Phase 9 decision), no external dep |
| pydantic | >=2.11.7 | Structured output models | Already used for all agent result types |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FetchStrategyManager | existing | Fetch article HTML with TLS fingerprinting | All HTTP fetches in this phase |
| loguru | existing | Structured logging | All step functions |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| html.parser for Twitter Cards | beautifulsoup4/meta-tags-parser | Would add a dependency; html.parser is sufficient for `<meta name="twitter:*">` tags |
| Custom field extraction | Full extruct dump | Decision is locked: extract key fields only, no raw dump |

**Installation:**
No new dependencies needed. All libraries already in `pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure
```
scrapegrape/publishers/
  pipeline/
    steps.py           # Add 3 new step functions at bottom
    supervisor.py      # Add 3 new step calls after existing step 8
  models.py            # Add ArticleMetadata model
  migrations/          # New migration for ArticleMetadata + new fields
```

### Pattern 1: Step Function Convention
**What:** Each step is a module-level function returning a plain dict, with no side effects on models.
**When to use:** All three new steps must follow this pattern exactly.
**Example (from existing codebase):**
```python
# Source: scrapegrape/publishers/pipeline/steps.py (existing pattern)
def run_article_extraction_step(article_html: str, article_url: str) -> dict:
    """Extract structured metadata from article HTML."""
    # ... extraction logic ...
    return {
        "json_ld": {...},      # Extracted key fields
        "opengraph": {...},    # Extracted key fields
        "microdata": {...},    # Extracted key fields
        "twitter_cards": {...},# Extracted key fields
        "formats_found": ["json-ld", "opengraph"],
    }
```

### Pattern 2: Supervisor Orchestration
**What:** The supervisor calls each step, saves result to ResolutionJob, publishes Redis event.
**When to use:** Wiring the 3 new steps into `run_pipeline()`.
**Example (from existing codebase):**
```python
# Source: scrapegrape/publishers/pipeline/supervisor.py (existing pattern)
# Step 10: Article extraction
publish_step_event(job_id, "article_extraction", "started")
article_result = run_article_extraction_step(article_html, article_url)
# Save to ArticleMetadata model + ResolutionJob
publish_step_event(job_id, "article_extraction", "completed", article_result)
```

### Pattern 3: pydantic-ai Agent for LLM Step
**What:** Define a Pydantic output model, system prompt, and Agent at module level. Call `agent.run_sync()` in the step function.
**When to use:** The "Metadata Profile" step (step 12).
**Example (from existing codebase):**
```python
# Source: scrapegrape/ingestion/terms_discovery.py (existing pattern)
class MetadataProfileResult(BaseModel):
    summary: str = Field(..., description="Human-readable summary")
    # ...

metadata_profile_agent = Agent(
    "openai:gpt-4.1-nano",
    output_type=MetadataProfileResult,
    system_prompt=METADATA_PROFILE_PROMPT,
)

def run_metadata_profile_step(extraction_result: dict, article_url: str) -> dict:
    result = metadata_profile_agent.run_sync(
        f"Analyze metadata for {article_url}:\n{json.dumps(extraction_result)}"
    )
    return result.output.model_dump()
```

### Pattern 4: Freshness TTL for Article Steps
**What:** Skip article steps if the exact same article URL was recently analyzed.
**When to use:** Before running article steps in the supervisor.
**Example:**
```python
# Check if ArticleMetadata exists for this URL within TTL
from django.conf import settings
recent = ArticleMetadata.objects.filter(
    article_url=article_url,
    created_at__gte=timezone.now() - settings.ARTICLE_FRESHNESS_TTL,
).first()
if recent:
    # Skip article steps, publish "skipped" events
```

### Anti-Patterns to Avoid
- **Merging formats into canonical view:** Decision is locked -- keep per-format sections separate
- **Storing raw extruct output:** Decision is locked -- extract key fields only
- **Adding new dependencies for Twitter Cards:** Use stdlib html.parser, consistent with project convention
- **Calling extruct with all syntaxes:** Only request `["json-ld", "opengraph", "microdata"]` to avoid unnecessary parsing overhead

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON-LD extraction | Custom JSON-LD parser | `extruct.extract(html, syntaxes=["json-ld"])` | Handles @graph flattening, multiple scripts, edge cases |
| OpenGraph extraction | Custom meta tag parser | `extruct.extract(html, syntaxes=["opengraph"])` | Handles namespaces, multiple values |
| Microdata extraction | Custom itemprop parser | `extruct.extract(html, syntaxes=["microdata"])` | Requires DOM tree traversal, scope nesting |
| LLM structured output | Custom JSON parsing of LLM response | pydantic-ai Agent with output_type | Handles retries, validation, type coercion |

**Key insight:** Twitter Cards is the ONE format that needs hand-rolling because extruct does not support it. But it is simple -- just `<meta name="twitter:*" content="...">` tags, easily handled by stdlib HTMLParser following the project's existing FeedLinkParser/RSLLinkParser pattern.

## Common Pitfalls

### Pitfall 1: extruct Parsing Performance
**What goes wrong:** Calling `extruct.extract()` with all syntaxes is slow because microdata requires full lxml DOM parsing.
**Why it happens:** Default behavior parses all 6 formats.
**How to avoid:** Always specify `syntaxes=["json-ld", "opengraph", "microdata"]`. The existing `run_publisher_details_step` already demonstrates this -- it calls JSON-LD first, only falls back to microdata if needed.
**Warning signs:** Step taking >5 seconds on normal pages.

### Pitfall 2: JSON-LD @graph Nesting
**What goes wrong:** Article metadata is often nested inside `@graph` arrays, not at the top level.
**Why it happens:** Publishers commonly use a single JSON-LD block with `@graph` containing WebPage, Article, Organization nodes.
**How to avoid:** Use the existing `_flatten_jsonld_nodes()` helper from `steps.py` or similar logic to walk into @graph before extracting article fields.
**Warning signs:** Step returns empty JSON-LD fields despite JSON-LD being present in HTML.

### Pitfall 3: Multiple Article Types in Schema.org
**What goes wrong:** Looking only for `@type: "Article"` misses `NewsArticle`, `BlogPosting`, `TechArticle`, `ScholarlyArticle`, `OpinionNewsArticle`, etc.
**Why it happens:** schema.org has many subtypes of Article/CreativeWork.
**How to avoid:** Check against a set of known article types: `{"Article", "NewsArticle", "BlogPosting", "TechArticle", "ScholarlyArticle", "OpinionNewsArticle", "AnalysisNewsArticle", "ReportageNewsArticle", "ReviewNewsArticle", "LiveBlogPosting", "SocialMediaPosting", "WebPage", "CreativeWork"}`.
**Warning signs:** Low extraction rate on real news sites.

### Pitfall 4: isAccessibleForFree Can Be Nested
**What goes wrong:** Only checking top-level `isAccessibleForFree` misses the `hasPart` pattern.
**Why it happens:** Google's recommended markup nests `isAccessibleForFree` inside `hasPart.WebPageElement`.
**How to avoid:** Check both the top-level article node AND any `hasPart` children for `isAccessibleForFree: false`.
**Warning signs:** Missing paywall detection on sites following Google's recommended markup.

### Pitfall 5: OpenGraph Returns List of Tuples (not dict)
**What goes wrong:** Treating extruct OpenGraph output as a dict when it returns `[{"namespace": ..., "properties": [("og:title", "..."), ...]}]`.
**Why it happens:** extruct's OpenGraph format differs from JSON-LD/microdata.
**How to avoid:** Convert the properties list of tuples to a dict: `{k: v for k, v in item["properties"]}`. Or use `uniform=True` but that changes ALL output formats.
**Warning signs:** KeyError or empty fields when accessing OpenGraph data.

### Pitfall 6: Article Fetch vs Homepage HTML Reuse
**What goes wrong:** Fetching the article URL when it is the same as the homepage URL, wasting a network request.
**Why it happens:** Users sometimes submit homepage URLs for analysis.
**How to avoid:** Compare the submitted URL (after normalization) with the publisher homepage URL. If they match, reuse the already-fetched homepage HTML from the publisher steps.
**Warning signs:** Double fetch of the same URL visible in logs.

## Code Examples

### Twitter Card Extraction with HTMLParser
```python
# Source: follows existing FeedLinkParser/RSLLinkParser pattern in steps.py
from html.parser import HTMLParser

TWITTER_CARD_FIELDS = {
    "twitter:card", "twitter:title", "twitter:description",
    "twitter:image", "twitter:site", "twitter:creator",
}

class TwitterCardParser(HTMLParser):
    """Extract <meta name="twitter:*" content="..."> tags."""

    def __init__(self) -> None:
        super().__init__()
        self.cards: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "meta":
            attr_dict = {k.lower(): (v or "") for k, v in attrs}
            name = attr_dict.get("name", "")
            content = attr_dict.get("content", "")
            if name.startswith("twitter:") and content:
                self.cards[name] = content

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "meta":
            self.handle_starttag(tag, attrs)
```

### extruct Article Metadata Extraction
```python
# Source: extruct docs + existing run_publisher_details_step pattern
import extruct

def _extract_article_metadata(html: str, url: str) -> dict:
    """Extract structured metadata from article HTML using extruct."""
    extracted = extruct.extract(
        html,
        base_url=url,
        syntaxes=["json-ld", "opengraph", "microdata"],
        uniform=False,  # Keep native formats for per-format extraction
    )
    return extracted
```

### Key Field Extraction from JSON-LD Article Node
```python
ARTICLE_TYPES = {
    "Article", "NewsArticle", "BlogPosting", "TechArticle",
    "ScholarlyArticle", "OpinionNewsArticle", "AnalysisNewsArticle",
    "ReportageNewsArticle", "ReviewNewsArticle", "LiveBlogPosting",
    "WebPage", "CreativeWork",
}

KEY_FIELDS = [
    "headline", "author", "datePublished", "dateModified",
    "image", "description", "isAccessibleForFree",
    "wordCount", "articleSection", "inLanguage", "keywords",
]

def _extract_jsonld_article_fields(jsonld_items: list, url: str) -> dict | None:
    """Extract key fields from the first article-type JSON-LD node."""
    nodes = _flatten_jsonld_nodes(jsonld_items)
    for node in nodes:
        types = _normalize_types(node)
        if any(t.split("/")[-1] in ARTICLE_TYPES for t in types):
            fields = {}
            for field in KEY_FIELDS:
                val = node.get(field)
                if val is not None:
                    # Flatten nested objects (e.g., author: {name: "..."})
                    if isinstance(val, dict):
                        fields[field] = val.get("name") or val.get("@id") or str(val)
                    elif isinstance(val, list):
                        fields[field] = [
                            item.get("name") if isinstance(item, dict) else str(item)
                            for item in val
                        ]
                    else:
                        fields[field] = val
            # Also extract publisher name if present
            pub = node.get("publisher")
            if isinstance(pub, dict):
                fields["publisher_name"] = pub.get("name")
            return fields
    return None
```

### OpenGraph Key Field Extraction
```python
OG_FIELD_MAP = {
    "og:title": "headline",
    "og:description": "description",
    "og:image": "image",
    "og:type": "type",
    "og:site_name": "publisher_name",
    "og:locale": "inLanguage",
    "article:published_time": "datePublished",
    "article:modified_time": "dateModified",
    "article:author": "author",
    "article:section": "articleSection",
    "article:tag": "keywords",
}

def _extract_opengraph_fields(og_items: list) -> dict | None:
    """Extract key fields from OpenGraph metadata."""
    if not og_items:
        return None
    # extruct returns list of dicts with "properties" as list of tuples
    props = {}
    for item in og_items:
        for key, val in item.get("properties", []):
            if key in OG_FIELD_MAP:
                mapped = OG_FIELD_MAP[key]
                if mapped == "keywords":
                    props.setdefault(mapped, []).append(val)
                else:
                    props[mapped] = val
    return props if props else None
```

### Paywall Heuristic Detection
```python
def _detect_paywall_heuristics(html: str) -> tuple[str, list[str]]:
    """Detect paywall signals from HTML content. Returns (status, signals).

    Only reports 'paywalled' when multiple strong signals agree.
    Single signal alone -> 'unknown'.
    """
    signals = []

    html_lower = html.lower()

    # Signal: Login/subscribe wall patterns
    login_patterns = [
        "subscribe to continue reading",
        "sign in to read",
        "create an account to continue",
        "already a subscriber?",
        "subscription required",
        "members only",
    ]
    for pattern in login_patterns:
        if pattern in html_lower:
            signals.append(f"login_wall:{pattern[:30]}")

    # Signal: Truncated body (article cut short with "...")
    # Look for common paywall CSS classes
    paywall_classes = [
        "paywall", "subscriber-only", "premium-content",
        "gated-content", "meter-", "regwall",
    ]
    for cls in paywall_classes:
        if cls in html_lower:
            signals.append(f"paywall_class:{cls}")

    # Signal: Metered access patterns
    meter_patterns = [
        "articles remaining", "free articles",
        "monthly limit", "article limit",
    ]
    for pattern in meter_patterns:
        if pattern in html_lower:
            signals.append(f"metered:{pattern[:20]}")

    # Decision logic: high confidence bar
    has_login = any(s.startswith("login_wall:") for s in signals)
    has_paywall_class = any(s.startswith("paywall_class:") for s in signals)
    has_meter = any(s.startswith("metered:") for s in signals)

    if has_meter:
        return "metered", signals
    if has_login and has_paywall_class:
        return "paywalled", signals  # Multiple strong signals
    if len(signals) == 0:
        return "free", signals  # No signals at all (combined with schema check)
    return "unknown", signals  # Single signal alone
```

### ArticleMetadata Model
```python
# Recommended model structure
class ArticleMetadata(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resolution_job = models.ForeignKey(
        "ResolutionJob", on_delete=models.CASCADE, related_name="article_metadata"
    )
    publisher = models.ForeignKey(
        "Publisher", on_delete=models.CASCADE, related_name="article_metadata"
    )
    article_url = models.URLField(db_index=True)

    # Per-format extracted fields (JSONField for each)
    jsonld_fields = models.JSONField(null=True, blank=True)
    opengraph_fields = models.JSONField(null=True, blank=True)
    microdata_fields = models.JSONField(null=True, blank=True)
    twitter_cards = models.JSONField(null=True, blank=True)

    # Formats present (for quick boolean checks)
    has_jsonld = models.BooleanField(default=False)
    has_opengraph = models.BooleanField(default=False)
    has_microdata = models.BooleanField(default=False)
    has_twitter_cards = models.BooleanField(default=False)

    # Paywall status
    PAYWALL_CHOICES = [
        ("free", "Free"),
        ("paywalled", "Paywalled (hard)"),
        ("metered", "Metered"),
        ("unknown", "Unknown"),
    ]
    paywall_status = models.CharField(
        max_length=20, choices=PAYWALL_CHOICES, default="unknown"
    )
    paywall_signals = models.JSONField(default=list, blank=True)

    # LLM metadata profile
    metadata_profile = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["article_url"]),
            models.Index(fields=["publisher", "created_at"]),
        ]
```

### LLM Metadata Profile Agent
```python
# Source: follows existing terms_discovery_agent / terms_evaluation_agent pattern

class MetadataProfileResult(BaseModel):
    summary: str = Field(
        ...,
        description="Human-readable 2-4 sentence summary of what metadata formats "
                    "are present, what key fields are populated, and overall metadata quality",
    )
    quality_score: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Overall metadata quality score",
    )

METADATA_PROFILE_PROMPT = """You are a structured data analyst. Given the extracted metadata
from a news article page, write a concise human-readable summary of what metadata is available.

Focus on:
1. Which formats are present (JSON-LD, OpenGraph, Microdata, Twitter Cards)
2. Key fields populated vs missing (headline, author, dates, images)
3. Whether the metadata is well-structured or minimal
4. Paywall status if detected

Be factual and concise. 2-4 sentences maximum."""

metadata_profile_agent = Agent(
    "openai:gpt-4.1-nano",
    output_type=MetadataProfileResult,
    system_prompt=METADATA_PROFILE_PROMPT,
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Parse JSON-LD manually | extruct with syntaxes filter | extruct 0.17+ | Handles edge cases, @graph, multiple scripts |
| isAccessibleForFree only | isAccessibleForFree + hasPart.WebPageElement | Google updated docs 2024 | Must check nested hasPart for accurate detection |
| gpt-4o-mini for cheap tasks | gpt-4.1-nano | April 2025 | Lower cost, faster, 1M context, good at structured output |

**Deprecated/outdated:**
- extruct's `uniform=True` changes OpenGraph output format in ways that lose information -- avoid for this use case
- The existing agents use `gpt-5-mini` but the decision calls for `gpt-4.1-nano` for this phase (cheaper, sufficient for profiling)

## Open Questions

1. **Publisher-level paywall signal aggregation**
   - What we know: Per-article paywall status stored on ArticleMetadata. Publisher needs a `has_paywall` field for quick cross-publisher lookups.
   - What's unclear: How to aggregate from multiple articles -- latest article? Majority vote? Any paywalled = True?
   - Recommendation: Use the latest article's paywall status. Add a `has_paywall` NullBooleanField to Publisher, updated after each article analysis. Simple, deterministic, and can be refined later.

2. **ResolutionJob field for article results**
   - What we know: Current `metadata_result` JSONField stores publisher details (Organization data).
   - What's unclear: Should article results go in a new `article_result` JSONField or repurpose `metadata_result`?
   - Recommendation: Add a new `article_result` JSONField on ResolutionJob to avoid breaking existing publisher_details data in `metadata_result`. The naming is clearer too.

3. **Article freshness TTL value**
   - What we know: Publisher freshness TTL is 24 hours. Article TTL should be separate since article content changes less frequently.
   - What's unclear: Exact TTL value.
   - Recommendation: Use a separate `ARTICLE_FRESHNESS_TTL` setting, defaulting to 24 hours (same as publisher). Easy to adjust independently.

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `scrapegrape/publishers/pipeline/steps.py` -- existing step function pattern, extruct usage, HTMLParser patterns
- Codebase analysis: `scrapegrape/publishers/pipeline/supervisor.py` -- orchestration pattern, event publishing, result saving
- Codebase analysis: `scrapegrape/ingestion/terms_discovery.py`, `terms_evaluation.py` -- pydantic-ai Agent pattern
- Codebase analysis: `scrapegrape/publishers/models.py` -- existing model structure, ResolutionJob fields
- [Google Structured Data for Paywalled Content](https://developers.google.com/search/docs/appearance/structured-data/paywalled-content) -- isAccessibleForFree markup specification
- [extruct GitHub README](https://github.com/scrapinghub/extruct) -- supported syntaxes, API, NO Twitter Cards support

### Secondary (MEDIUM confidence)
- [OpenAI GPT-4.1-nano docs](https://platform.openai.com/docs/models/gpt-4.1-nano) -- model capabilities, context window
- [pydantic-ai OpenAI integration](https://ai.pydantic.dev/models/openai/) -- model name format verification

### Tertiary (LOW confidence)
- Paywall heuristic signals: derived from common patterns observed across news sites, not from an authoritative source. Should be validated against real publisher HTML during development.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in project, API verified
- Architecture: HIGH - following existing codebase patterns exactly
- Pitfalls: HIGH - identified from real extruct behavior and schema.org spec
- Paywall heuristics: MEDIUM - based on common patterns, needs real-world validation
- LLM prompt: MEDIUM - follows existing pattern, but prompt content is discretionary

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (stable domain, libraries not fast-moving)
