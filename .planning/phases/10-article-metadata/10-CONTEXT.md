# Phase 10: Article Metadata - Context

**Gathered:** 2026-02-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract structured data from the submitted article URL — what metadata formats are present, whether it is paywalled, and an LLM-generated human-readable profile. This phase adds article-level analysis to the existing publisher-level pipeline. Report card display is Phase 11.

</domain>

<decisions>
## Implementation Decisions

### Metadata scope
- Extract ~10 key fields per format: headline, author, datePublished, dateModified, image, description, publisher name, isAccessibleForFree, wordCount, articleSection, inLanguage, keywords
- Keep fields per-format (JSON-LD section, OpenGraph section, Microdata section, Twitter Cards section) — not merged into one canonical view
- Twitter Cards treated as a 4th format alongside JSON-LD, OpenGraph, Microdata
- Store extracted key fields only — no raw extruct dump
- Use FetchStrategyManager for article fetch; reuse homepage HTML if submitted URL matches homepage

### Pipeline integration
- Three new pipeline steps: "Article Extraction", "Paywall Detection", "Metadata Profile"
- Run after all publisher steps (steps 10, 11, 12 after existing 1-9)
- Step summaries show key findings: extraction shows "headline, author, 8 fields"; paywall shows "isAccessibleForFree: true"; profile shows first ~50 chars of summary
- New ArticleMetadata model with ForeignKey to both ResolutionJob and Publisher
- pydantic-ai agent (GPT-4.1-nano) for LLM metadata profiling, consistent with existing ToS agents
- Article steps skippable by freshness TTL if the exact same article URL was analyzed recently

### Paywall handling
- Primary: check isAccessibleForFree schema.org markup
- Fallback: heuristic detection with high confidence bar — only report "paywalled" when multiple strong signals agree (login wall + truncated body, etc.). Single signal alone → "unknown"
- Detect metered access patterns (freemium, N articles/month) as distinct from hard paywall
- Three paywall statuses: free, paywalled (hard), metered, unknown
- Store paywall status on ArticleMetadata, as step result on ResolutionJob, and as publisher-level signal (e.g., publisher.has_paywall) for quick cross-publisher lookups

### Claude's Discretion
- Specific heuristic signals to use for paywall detection
- extruct configuration and parsing details
- LLM prompt design for metadata profiling
- Exact ArticleMetadata model field names and types
- How to determine publisher-level paywall signal from per-article data

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-article-metadata*
*Context gathered: 2026-02-17*
