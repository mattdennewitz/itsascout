# Research Summary: Competitive Intelligence Features

**Project:** itsascout (scrapegrape)
**Domain:** Publisher competitive intelligence (Common Crawl, Google News, update frequency)
**Researched:** 2026-02-17
**Overall confidence:** HIGH

## Executive Summary

This milestone adds three competitive intelligence signals to the existing publisher report card: Common Crawl presence checking, Google News inclusion detection, and publisher update frequency estimation. The key finding is that these features require remarkably little new infrastructure -- **one new Python dependency** (`feedparser`) and **zero new external services**. Everything else leverages existing libraries (httpx, lxml), existing pipeline data (sitemap URLs, RSS feed URLs, structured data), and existing patterns (step functions, JSON result fields, SSE events).

Common Crawl presence is a straightforward HTTP GET to the CC CDX Index API using the already-installed `httpx`. Google News "inclusion" cannot be definitively determined programmatically, so we detect optimization signals (news sitemaps with `xmlns:news` namespace, `NewsArticle` schema types, `NewsMediaOrganization` markup) -- most of which are already captured by existing pipeline steps. Update frequency is estimated by fetching discovered RSS feeds with `feedparser` and computing publication intervals with stdlib `statistics`.

The architecture adds four new step functions and one aggregation step to the existing sequential pipeline, following the established pattern exactly: step function in `steps.py`, JSON result on `ResolutionJob`, flat fields on `Publisher`, SSE event, frontend card. The most significant risk is the CC CDX API's aggressive rate limiting, mitigated by treating the CC step as non-critical with graceful error handling.

## Key Findings

**Stack:** One new dependency (feedparser 6.0.12). CC Index API via existing httpx. News sitemap parsing via existing lxml. No cdx-toolkit needed (overkill for presence check).

**Architecture:** Four new pipeline steps + one aggregation step inserted into existing supervisor. CC step is independent (external API). Sitemap analysis and RSS frequency build on existing discovery steps. Google News signals aggregate existing data.

**Critical pitfall:** CC CDX API rate limiting. Must treat CC step as non-critical with 10-30 second timeout and graceful error handling. Never block the pipeline on CC failures.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Phase 1: Models + Migration** - Add new fields to Publisher and ResolutionJob
   - Addresses: Data model foundation for all three features
   - Avoids: Forgetting TTL skip path updates (pitfall #5 in PITFALLS.md)

2. **Phase 2: Common Crawl Presence Step** - Query CC CDX Index API
   - Addresses: CC presence check (independent, simplest feature)
   - Avoids: CC rate limiting (pitfall #1) via non-critical error handling
   - Validates: Pipeline extension pattern before adding dependent steps

3. **Phase 3: Sitemap Analysis Step** - Fetch sitemaps, detect news namespace, extract lastmod
   - Addresses: News sitemap detection, lastmod date extraction
   - Avoids: Large sitemap timeout (moderate pitfall) via 5-sitemap/500-URL limits
   - Enables: Both Google News signals and frequency estimation

4. **Phase 4: Update Frequency Step** - feedparser + interval math
   - Addresses: Publishing frequency estimation from RSS dates + sitemap lastmod fallback
   - Avoids: Unreliable lastmod (pitfall #3) by preferring RSS dates
   - New dependency: feedparser 6.0.12

5. **Phase 5: Google News Signals Aggregation** - Combine existing data
   - Addresses: Google News readiness scoring
   - Avoids: False negative framing (pitfall #4) by using "readiness" not "inclusion"
   - Pure aggregation: no new HTTP requests

6. **Phase 6: Frontend + Report Card** - Competitive Intelligence card
   - Addresses: UI presentation of all three signals
   - Avoids: SSE progress UX breakage (moderate pitfall) via step list updates

**Phase ordering rationale:**
- Models first because all steps depend on them
- CC step first among features because it is fully independent
- Sitemap analysis before frequency and Google News because both depend on its output
- Google News signals last because it is purely aggregation
- Frontend last because it renders data from all prior steps

**Research flags for phases:**
- Phase 2 (CC step): Validate CC CDX API response format against live API; NDJSON parsing is a common gotcha
- Phase 3 (Sitemap analysis): Test with real publisher sitemaps; XML encoding issues vary widely
- Phase 4 (Frequency): feedparser date parsing should be validated with real feeds; edge cases with timezone handling

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | One new dependency (feedparser, well-established). CC Index API verified against official docs. All other capabilities use existing deps. |
| Features | HIGH | CC presence is a documented public API. News sitemap namespace is stable since 2014. RSS frequency estimation is standard practice. |
| Architecture | HIGH | Follows established pipeline pattern exactly. Step functions, JSON fields, SSE events, flat Publisher fields -- all patterns proven in existing 12-step pipeline. |
| Pitfalls | MEDIUM-HIGH | CC rate limiting documented by CC themselves. Sitemap lastmod unreliability well-established. Google News detection limitations are inherent (no public API). feedparser edge cases are well-known. |

## Gaps to Address

- **CC CDX API crawl ID discovery:** The collinfo.json endpoint provides the latest crawl ID. Need to verify the response format and caching strategy during implementation.
- **Sitemap XML encoding edge cases:** Real-world sitemaps use various encodings. Need integration tests against 10+ real publisher sitemaps to validate lxml handling.
- **feedparser date format coverage:** feedparser handles most formats but some RSS feeds use non-standard dates. Need to validate with real feeds from discovered RSS URLs.
- **Google News signals weighting:** The "strong / moderate / minimal" readiness levels are a research recommendation. May need adjustment based on testing with known Google News publishers.
- **CCBot blocking correlation:** Identified as a differentiator feature but not designed in detail. Can be added as a low-effort follow-on after core features ship.
