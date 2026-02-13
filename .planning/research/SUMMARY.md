# Project Research Summary

**Project:** itsascout (scrapegrape) v2.0
**Domain:** URL analysis workflow for scraping feasibility assessment
**Researched:** 2026-02-13
**Confidence:** HIGH

## Executive Summary

The v2.0 milestone adds single-URL analysis with real-time streaming progress to the existing Django-Inertia bulk publisher management system. The recommended architecture is a hybrid approach: django-rq (Redis-backed task queue) orchestrates a sequential pipeline of 10-11 analysis steps, publishing progress events to Redis pub/sub, which a separate async Django SSE endpoint streams to the browser via EventSource. Inertia handles page navigation and initial data loading, while SSE operates as a parallel channel for real-time updates.

The critical technical decisions are: (1) migrate from django_tasks (database backend) to django-rq (Redis backend) for job.meta progress tracking and pub/sub capabilities; (2) use curl-cffi as the primary HTTP client with TLS fingerprinting to reduce Zyte API costs, falling back to Zyte only on WAF blocks; (3) serve SSE endpoints via an ASGI server (Daphne/Uvicorn) to avoid worker exhaustion, while keeping sync Inertia views under WSGI; (4) implement a single orchestrator RQ job that executes steps sequentially rather than chaining dependent jobs, simplifying error handling and progress reporting.

The highest risks are: (1) SSE middleware interference causing event batching instead of streaming; (2) WSGI worker exhaustion from long-lived SSE connections; (3) curl-cffi segfaults from streaming mode crashes; (4) URL normalization duplicates creating fragmented publisher data; (5) orphaned dependent RQ jobs silently failing without user-visible errors. All risks have concrete mitigation strategies validated through research.

## Key Findings

### Recommended Stack

**Core additions to existing Django 5.2 + Inertia.js + React 19 stack:**

The new stack elements integrate with the proven v1.0 foundation (Django, DRF, Inertia, React, PostgreSQL, pydantic-ai, wafw00f). The additions are purpose-selected to enable streaming progress UX and robust publisher intelligence gathering.

**Core technologies:**
- **curl-cffi (>=0.14.0)**: Primary HTTP client with browser TLS impersonation — bypasses bot detection via JA3 fingerprinting, 15x higher evasion rate than httpx/requests, reduces Zyte API costs by 70-80% through successful direct fetching
- **django-rq (>=3.0) + Redis 7**: Redis-backed task queue replacing django_tasks — enables job.meta progress tracking, pub/sub for SSE updates, worker pools, retry logic, and built-in Django admin monitoring
- **Django StreamingHttpResponse + EventSource**: Server-sent events for real-time progress — no additional dependencies needed, native browser support, unidirectional streaming sufficient for progress updates
- **extruct (>=0.18.0)**: Metadata extraction from JSON-LD, OpenGraph, Microdata — single library covering all structured data formats, battle-tested by Zyte/Scrapinghub at scale
- **protego (>=0.3.1)**: robots.txt parsing per RFC 9309 — Scrapy's proven parser, handles wildcards/anchors correctly unlike stdlib urllib.robotparser
- **ultimate-sitemap-parser (>=1.8.0)**: Sitemap discovery and parsing — handles all formats (XML, News, indexes), memory-efficient streaming, pluggable HTTP client for curl-cffi integration
- **url-normalize (>=2.2.1)**: URL canonicalization — handles IDN, percent-encoding, query param sorting, prevents publisher duplication
- **feedparser (>=6.0.12) + BeautifulSoup4**: RSS/Atom feed discovery and validation — de facto standard feed parser with robust error handling

**Infrastructure additions:**
- Redis 7 (redis:7-alpine) for RQ message broker and SSE pub/sub
- ASGI server (Daphne or Uvicorn) for async SSE endpoints
- RQ worker service (docker-compose rqworker)

**Alternatives rejected:**
- Celery: Overkill complexity for sequential 10-step pipeline
- WebSockets/Channels: Bidirectional not needed, adds ASGI migration complexity
- httpx/requests: No TLS fingerprinting, blocked by bot detection
- feedsearch-crawler: Unmaintained, heavy aiohttp dependency
- Custom RSL library: None exists yet, custom lxml implementation sufficient

### Expected Features

The research identified a clear MVP path focused on the core "paste URL → streaming progress → report card" workflow.

**Must have (table stakes):**
- Single URL input with prominent "Analyze" action — standard pattern across all website analysis tools (Lighthouse, SecurityHeaders, BuiltWith)
- Real-time progress indication with per-step status — users expect feedback during 15-60s pipeline execution, blank screen = perceived failure
- WAF detection display (existing data, new presentation) — critical technical barrier assessment
- ToS permissions display (existing data, new presentation) — core legal value proposition
- robots.txt analysis with rule-by-rule display — universally present crawling policy signal
- Overall scraping feasibility grade (A-F or traffic light) — single at-a-glance indicator pattern from SecurityHeaders/Lighthouse
- Publisher-level data caching with freshness TTL — prevents redundant API costs for repeat analyses
- Publisher report card page with progressive section reveal — streaming UX standard from LLM interfaces

**Should have (competitive differentiators):**
- Article metadata profiling (URL-specific) — shows what's extractable from a specific page before building scraper
- RSS/Atom feed discovery — signals structured content access, pagination-free monitoring
- Sitemap discovery and URL count — enumeration goldmine for scrapers
- Paywall detection via isAccessibleForFree schema.org markup — critical for content accessibility assessment
- Structured data inventory (JSON-LD types present) — shows machine-readable data already available
- Streaming progressive reveal (cards appear as steps complete) — creates engagement during wait

**Defer (v2+):**
- RSL (Really Simple Licensing) detection — novel standard finalized Dec 2025 but adoption still early, revisit in 6 months
- Historical trend tracking — "WAF changed over time" interesting but not core value
- Competitor comparison — different product scope
- Automated scraper generation — scope creep, this is assessment tool not scraper builder
- Content extraction/display — legal risk from copyright concerns

### Architecture Approach

The architecture integrates new capabilities into the existing Django-Inertia foundation through a hybrid pattern: Inertia handles page navigation and initial data loading, while a separate async SSE endpoint streams real-time progress. The ResolutionJob model acts as the central orchestration record, tracking the multi-step pipeline and storing accumulated results. The Publisher model extends with discovery fields (robots_txt_content, sitemap_urls, rss_urls, rsl_status, metadata_capabilities, fetch_strategy) that accumulate intelligence over repeated analyses.

**Major components:**

1. **ResolutionJob model** — UUID-keyed job tracking record with status, current_step, steps_completed, results JSONField, optional Publisher FK (null until resolution succeeds), timestamps for freshness checks
2. **URL sanitizer service** — Pure function normalizing URLs to canonical form (lowercase hostname, strip www., remove tracking params, sort query params, handle IDN) to prevent duplicate publishers
3. **Fetch strategy manager** — Encapsulates curl-cffi-first/Zyte-fallback logic, remembers working strategy per publisher domain in Publisher.fetch_strategy field
4. **RQ pipeline task** — Single orchestrator job executing 10-11 steps sequentially (publisher resolution, fetch strategy discovery, WAF check, robots.txt, sitemap, RSS, RSL, ToS discovery, ToS evaluation, metadata extraction, metadata profiling), publishing progress to Redis pub/sub after each step
5. **SSE endpoint (async Django view)** — Subscribes to Redis pub/sub channel `job:<uuid>`, streams events as text/event-stream, bypasses Inertia middleware, runs under ASGI
6. **Jobs/Show.tsx (Inertia page)** — Results page component using EventSource to consume SSE updates, progressively renders result cards as job.results accumulates, handles completed jobs without SSE (shareable URLs)

**Critical architectural patterns:**
- SSE endpoints are separate `/api/` routes outside Inertia's protocol (Inertia handles page loads, SSE streams updates)
- Single supervisor RQ job (not chained dependent jobs) for simpler error handling and shared pipeline state
- Progress stored in Redis pub/sub for SSE (not job.meta which requires full job object fetch)
- Publisher data cached with freshness TTL, article-level data always fetched fresh
- EventSource cleanup in React useEffect return function to prevent zombie connections on Inertia navigation

### Critical Pitfalls

Research identified 6 critical pitfalls that would break core functionality if not addressed proactively.

1. **InertiaMiddleware interfering with SSE StreamingHttpResponse** — Inertia middleware (especially custom `inertia_share` calling session.pop() on every request) and GZipMiddleware buffer streaming responses, causing events to batch instead of stream. **Mitigation:** Modify inertia_share to skip /api/ routes, never add GZipMiddleware, set Cache-Control: no-cache and X-Accel-Buffering: no headers, verify with single-event test.

2. **WSGI worker exhaustion from long-lived SSE connections** — Each SSE connection holds a WSGI worker for 30-120 seconds. With 3-5 concurrent analyses, all workers occupied, app becomes unresponsive. **Mitigation:** Use async Django view with ASGI server (Daphne/Uvicorn) for SSE routes specifically, keep sync Inertia views under WSGI coexistence, or implement polling fallback as simplified alternative.

3. **RQ dependent jobs silently abandoned on parent failure** — Job chains break when parent fails (moved to FailedJobRegistry), dependents stuck in DeferredJobRegistry forever, no error visible to user. **Mitigation:** Use single supervisor job pattern executing steps sequentially rather than chaining, implement explicit try/except per step with progress event on failure, set job_timeout on all jobs.

4. **curl-cffi session crashes Python process on streaming connection close** — Known bug (GitHub #675): closing Session during incomplete streaming request causes segfault, entire RQ worker process dies without Python exception. **Mitigation:** Never use stream=True, always consume full response, use Session as context manager, set explicit timeout on every request, test against slow/chunked-response sites early.

5. **URL normalization creating duplicate publishers** — Existing normalize_url() only strips to scheme://netloc, but URLs arrive as https://WWW.Example.COM/, http://example.com, etc., creating duplicate Publisher records. **Mitigation:** Implement proper normalization (lowercase hostname, strip www., remove default ports, sort query params), use url-normalize library for IDN/edge cases, migrate existing publishers before deployment, add unique constraint.

6. **SSE connection not cleaned up on React component unmount** — Inertia client-side navigation unmounts component, EventSource stays open without cleanup function, users accumulate zombie connections. **Mitigation:** Store EventSource in useRef (not useState), always return cleanup function from useEffect calling es.close(), send 'complete' event type from server for proactive client-side close, test with Inertia navigation explicitly.

## Implications for Roadmap

Based on research, suggested phase structure follows dependency chains from infrastructure → models → pipeline → frontend.

### Phase 1: Infrastructure & Models
**Rationale:** Redis, RQ, ASGI server, and data models are foundational dependencies for everything else. URL sanitizer is needed before any job creation. SSE endpoint must be validated early before building pipeline on top of it.

**Delivers:**
- Redis 7 + RQ worker services in docker-compose
- ASGI server config (Daphne) for SSE endpoints
- ResolutionJob model with UUID, status, results JSONField
- Publisher model extensions (fetch_strategy, robots_txt_content, sitemap_urls, rss_urls, metadata_capabilities, freshness fields)
- URL sanitizer service with comprehensive normalization
- SSE endpoint with Redis pub/sub streaming (smoke test with mock events)

**Addresses:**
- Pitfall #1 (middleware interference) — SSE endpoint verified streaming immediately
- Pitfall #2 (worker exhaustion) — ASGI server architecture decision made
- Pitfall #5 (URL duplication) — normalization implemented upfront
- Pitfall #6 (SSE cleanup) — React hook pattern established

**Avoids:** Building pipeline before infrastructure proven, discovering WSGI exhaustion after SSE implemented

### Phase 2: Fetch Strategy & HTTP Client
**Rationale:** curl-cffi is the foundation for all page fetching (robots.txt, homepage, article HTML). Fetch strategy manager with Zyte fallback must work before pipeline steps depend on it. Early validation prevents discovering curl-cffi segfault issues deep in pipeline testing.

**Delivers:**
- curl-cffi integration with browser impersonation
- Fetch strategy manager service (try curl-cffi → fallback Zyte → remember per publisher)
- Zyte fallback path using existing fetch_html_via_proxy
- FetchResult dataclass normalizing curl-cffi/Zyte responses
- Smoke tests against slow/chunked-response sites to validate no segfaults

**Addresses:**
- Pitfall #4 (curl-cffi crash) — validated early with segfault tests
- STACK.md curl-cffi recommendation — TLS fingerprinting reducing Zyte costs

**Uses:**
- curl-cffi (STACK.md)
- Existing Zyte proxy integration (ingestion/services.py)

### Phase 3: Core Pipeline (Publisher Resolution + WAF + ToS)
**Rationale:** Reuses existing pipeline steps (publisher resolution, WAF check, ToS discovery/evaluation) with minimal changes. Establishes RQ task pattern and progress publishing before adding new discovery steps. Validates supervisor job pattern and SSE progress flow end-to-end.

**Delivers:**
- run_resolution_pipeline RQ job (single supervisor pattern)
- publish_progress/publish_complete/publish_error to Redis pub/sub
- Step 1: Publisher resolution (get-or-create, freshness check, LLM name extraction reuse)
- Step 2: Fetch strategy discovery (uses Phase 2 manager)
- Step 3: WAF check (reuses existing wafw00f integration)
- Step 8-9: ToS discovery + evaluation (reuses existing pydantic-ai agents)
- SSE endpoint subscribed to job:<uuid> channel streaming step progress
- Jobs/Show.tsx page with EventSource consuming SSE, rendering progress checklist

**Addresses:**
- Pitfall #3 (job abandonment) — supervisor pattern avoids dependent job chains
- FEATURES.md table stakes — WAF and ToS display (existing data, new streaming presentation)

**Implements:**
- ARCHITECTURE.md RQ pipeline task pattern
- ARCHITECTURE.md SSE + Inertia coexistence

### Phase 4: Discovery Steps (robots.txt + Sitemap + RSS)
**Rationale:** These three steps are independent of each other and can be built in any order. They're publisher-level checks that cache on the Publisher model. robots.txt is highest value (universally present crawling policy). Sitemap discovery depends on robots.txt Sitemap: directives but is otherwise independent.

**Delivers:**
- Step 4: robots.txt fetch + parse (protego), cache on Publisher.robots_txt_content, check if submitted URL allowed
- Step 5: Sitemap discovery (ultimate-sitemap-parser), use robots.txt Sitemap: directives + common paths, store URLs on Publisher.sitemap_urls
- Step 6: RSS/Atom feed discovery (BeautifulSoup link tag parsing + feedparser validation), store on Publisher.rss_urls
- RobotsTxtCard, SitemapCard, RSSCard components in Jobs/Show.tsx
- Progressive card rendering as each step completes via SSE

**Addresses:**
- FEATURES.md table stakes — robots.txt analysis
- FEATURES.md differentiators — RSS/sitemap discovery

**Uses:**
- protego (STACK.md) for RFC 9309 robots.txt parsing
- ultimate-sitemap-parser (STACK.md) with curl-cffi HTTP client
- feedparser + BeautifulSoup (STACK.md)

### Phase 5: Article Metadata Extraction
**Rationale:** This is URL-specific (not publisher-level), always fetched fresh. Depends on fetch strategy manager from Phase 2. Implements core differentiator — "what can I extract from this specific page?"

**Delivers:**
- Step 10: Article metadata extraction (extruct for JSON-LD/OpenGraph/Microdata, title/author/date/thumbnail, paywall detection via isAccessibleForFree, structured data inventory)
- ArticleMetadataCard component with Tier 1/2/3 attribute display
- Metadata profiling (LLM assessment of publisher capabilities stored in Publisher.metadata_capabilities)
- Try/except error handling for malformed JSON-LD (Pitfall from PITFALLS.md extruct crash)

**Addresses:**
- FEATURES.md differentiators — article metadata profiling, paywall detection, structured data inventory
- Pitfall from PITFALLS.md — extruct crash on malformed JSON-LD (wrap in try/except)

**Uses:**
- extruct (STACK.md) for multi-format metadata extraction
- Fetch strategy manager (Phase 2) for article HTML fetch

### Phase 6: Overall Feasibility Grade & Polish
**Rationale:** Grade computation requires all pipeline results. This phase adds the "report card" payoff and UX polish.

**Delivers:**
- Overall feasibility grade computation (weighted: ToS 30%, WAF 20%, robots.txt 20%, RSL 15%, metadata 10%, RSS/sitemap 5%)
- Grade display (A-F letter or traffic light) on Jobs/Show page
- PublisherCard component showing publisher-level summary
- Freshness indicators ("Last checked: 3 days ago") with re-analyze action
- URL entry form (Analyze/Index.tsx) with validation and auto-prepend https://
- Error handling UX (failed step visibility, partial results display)
- Connection lost / retry UX for SSE failures

**Addresses:**
- FEATURES.md table stakes — overall feasibility grade, publisher report card page
- FEATURES.md table stakes — re-analyze with freshness indicator
- UX pitfalls from PITFALLS.md — progress context, error visibility, duplicate analysis prevention

**Implements:**
- FEATURES.md UX patterns — report card presentation, progress bar + step list

### Phase 7 (Optional/Defer): RSL Detection
**Rationale:** RSL standard finalized Dec 2025 but adoption still early (~1500 publishers). Novel feature with no mainstream tool precedent. Can be added later as RSL adoption grows without architectural changes.

**Delivers:**
- Step 7: RSL detection (check HTML <script type="application/rsl+xml">, HTTP Link header, robots.txt License: directive, fetch external RSL XML if found)
- rsl_detector.py module using lxml for HTML/XML parsing
- RSL badge display ("RSL: Free", "RSL: Attribution Required", "RSL: Pay-per-Crawl")
- Store on Publisher.rsl_status JSONField

**Addresses:**
- FEATURES.md differentiators — RSL detection (deferred based on early adoption stage)

**Uses:**
- lxml (transitive via extruct) for RSL XML parsing

### Phase Ordering Rationale

- **Infrastructure first (Phase 1):** Redis/RQ/ASGI/models are blocking dependencies for all subsequent work. SSE endpoint validated early prevents discovering worker exhaustion after pipeline built.
- **Fetch strategy early (Phase 2):** curl-cffi is the HTTP foundation for all pipeline steps. Validating segfault risk early prevents pipeline rebuild if curl-cffi proves unusable.
- **Existing pipeline first (Phase 3):** Reusing proven publisher resolution, WAF, ToS steps establishes RQ supervisor pattern and SSE flow with low risk before adding new discovery steps.
- **Discovery steps grouped (Phase 4):** robots.txt/sitemap/RSS are independent publisher-level checks that can be built in parallel by multiple developers or sequentially without blocking each other.
- **Article metadata separate (Phase 5):** URL-specific logic is architecturally distinct from publisher-level caching. Depends on fetch strategy being proven.
- **Grade computation last (Phase 6):** Requires all pipeline results to compute weighted score. Adds polish after core functionality proven.
- **RSL optional (Phase 7):** Can be added anytime without architectural changes. Adoption still early, revisit in 6 months.

### Research Flags

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Infrastructure):** django-rq, Redis, ASGI server all have official documentation and established Django integration patterns
- **Phase 2 (Fetch):** curl-cffi usage verified through official docs and GitHub examples
- **Phase 3 (Core Pipeline):** Reuses existing agents and models, RQ supervisor pattern verified
- **Phase 4 (Discovery):** protego, ultimate-sitemap-parser, feedparser all have official docs and examples
- **Phase 5 (Metadata):** extruct documentation comprehensive, JSON-LD/OpenGraph schemas well-defined

**Phases with potential research needs during planning:**
- **Phase 6 (Grade Computation):** Grade weighting is opinionated recommendation (ToS 30%, WAF 20%, robots 20%, RSL 15%, metadata 10%, RSS/sitemap 5%) — may need validation against user priorities during implementation
- **Phase 7 (RSL):** Custom implementation since no library exists, RSL spec verified but real-world edge cases unknown — may need deeper research during implementation if RSL adoption accelerates

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All core dependencies verified through official docs, PyPI release notes, and GitHub repos. curl-cffi and django-rq versions confirmed compatible with Python 3.12 and Django 5.2. ASGI server requirement verified through Django docs and SSE implementation examples. |
| Features | MEDIUM-HIGH | UX patterns verified across multiple real-world tools (SecurityHeaders, Lighthouse, BuiltWith, SE Ranking). Metadata fields verified against Zyte API docs and schema.org. RSL spec verified against official standard but adoption data limited. Grade weighting is opinionated recommendation requiring validation. |
| Architecture | HIGH | SSE + Inertia coexistence pattern verified through multiple blog posts and GitHub examples. RQ supervisor pattern vs. dependency chaining trade-offs documented in RQ GitHub issues. WSGI/ASGI coexistence confirmed in Django docs. ResolutionJob/Publisher model design follows established Django patterns. |
| Pitfalls | MEDIUM | All 6 critical pitfalls sourced from official Django tickets, RQ GitHub issues, curl-cffi GitHub issues, and verified blog posts. Middleware interference verified through Django ticket #36655/36656. Worker exhaustion pattern verified through gunicorn issues. curl-cffi streaming crash verified through GitHub issue #675. URL normalization duplicates pattern inferred from domain analysis (not from single verified source). |

**Overall confidence:** HIGH

The recommended stack and architecture are built on proven technologies with official documentation. The critical pitfalls are sourced from verified bug reports and production experience documented in GitHub issues and Django tickets. The main uncertainty is in feature prioritization (grade weighting, RSL adoption timeline) rather than technical feasibility.

### Gaps to Address

**During planning:**
- **Grade computation weighting validation:** The suggested weights (ToS 30%, WAF 20%, robots 20%, RSL 15%, metadata 10%, RSS/sitemap 5%) are research-based recommendations but not empirically validated. Consider user research or stakeholder input during roadmap planning to adjust weights based on actual use cases (content aggregation vs. AI training vs. search indexing).

**During implementation:**
- **curl-cffi browser version selection:** Research recommends `impersonate="chrome"` (latest) but does not specify fallback profiles if specific sites block newer Chrome fingerprints. May need experimentation during Phase 2 to identify optimal profile rotation strategy.
- **LLM publisher name hallucination handling:** Existing publisher resolution uses pydantic-ai LLM for name extraction. Research flags this as a risk (CDN domains, subdomains, URL shorteners may cause hallucinations) but does not provide mitigation beyond "manual override UI". May need confidence scoring or existing publisher database lookup during Phase 3 implementation.
- **RSL adoption tracking:** If RSL detection is deferred to Phase 7, establish monitoring for RSL adoption metrics (number of publishers implementing RSL) to inform decision on when to prioritize this feature. Revisit in Q2 2026 based on adoption growth.
- **SSE connection limits:** Research notes browser limit of 6 concurrent SSE connections per domain over HTTP/1.1. If multiple users from same organization run analyses simultaneously, may hit this limit. Consider connection pooling or HTTP/2 upgrade during Phase 6 if this becomes an issue in testing.

**During testing:**
- **Real-world robots.txt validation:** Phase 4 must test against known edge cases: facebook.com (empty robots.txt), bloomberg.com (wildcard patterns), sites returning 403 for robots.txt, sites with malformed syntax. Research flags urllib.robotparser bugs but actual protego edge case handling needs validation.
- **extruct malformed JSON-LD handling:** Phase 5 must test against pages with: no structured data, malformed JSON in script tags, multiple conflicting schemas, HTML entities in JSON-LD, trailing semicolons. Research confirms extruct has parsing error handling but real-world robustness needs validation.

## Sources

### Primary (HIGH confidence)
- [RSL 1.0 Specification](https://rslstandard.org/rsl) — Really Simple Licensing standard (official spec)
- [curl-cffi GitHub](https://github.com/lexiforest/curl_cffi) — Browser impersonation library (official repo, issue #675 segfault verified)
- [django-rq GitHub](https://github.com/rq/django-rq) — Django integration for RQ (official repo, v3.0+ changelog)
- [RQ GitHub](https://github.com/rq/rq) — Redis queue library (official repo, issues #2006, #1224, #1503 on dependency handling)
- [Django ticket #36655](https://code.djangoproject.com/ticket/36655) — GZipMiddleware buffers streaming responses (official Django bug tracker)
- [Django ticket #36656](https://code.djangoproject.com/ticket/36656) — GZipMiddleware drops async streaming content
- [extruct GitHub](https://github.com/scrapinghub/extruct) — Metadata extraction library (Scrapinghub official repo, issues #45, #87 on JSON parsing errors)
- [protego GitHub](https://github.com/scrapy/protego) — robots.txt parser (Scrapy official)
- [ultimate-sitemap-parser GitHub](https://github.com/GateNLP/ultimate-sitemap-parser) — Sitemap parsing (official repo)
- [Django ASGI Deployment Docs](https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/) — Official ASGI documentation
- [MDN EventSource API](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) — Official specification
- [feedparser GitHub](https://github.com/kurtmckee/feedparser) — Feed parsing library (official repo)
- [url-normalize GitHub](https://github.com/niksite/url-normalize) — URL canonicalization library

### Secondary (MEDIUM confidence)
- [Django Streaming HTTP Responses](https://blog.pecar.me/django-streaming-responses) — SSE pattern with StreamingHttpResponse
- [SSE Minimalist Django](https://minimalistdjango.com/TIL/2024-04-21-server-sent-events/) — WSGI considerations for SSE
- [SSE in React 2026](https://oneuptime.com/blog/post/2026-01-15-server-sent-events-sse-react/view) — React EventSource patterns
- [Lightweight Django Task Queues 2025](https://medium.com/@g.suryawanshi/lightweight-django-task-queues-in-2025-beyond-celery-74a95e0548ec) — django-rq vs Celery comparison
- [Django 6.0 Tasks review](https://www.loopwerk.io/articles/2026/django-tasks-review/) — django_tasks limitations
- [Advanced Django-RQ Example](https://stuartm.com/2020/05/advanced-django-rq-example/) — Progress tracking pattern
- [Zyte Compliant Web Scraping Checklist](https://www.zyte.com/learn/compliant-web-scraping-checklist/) — Assessment methodology
- [SecurityHeaders.com](https://securityheaders.com/) — A+ to F grading UX pattern
- [SE Ranking Robots.txt Tester](https://seranking.com/free-tools/robots-txt-tester.html) — robots.txt analysis UI pattern
- [Trafilatura Metadata Module](https://trafilatura.readthedocs.io/en/latest/_modules/trafilatura/metadata.html) — Metadata extraction fields
- [Newspaper4k](https://github.com/AndyTheFactory/newspaper4k) — Article metadata extraction library

### Tertiary (LOW confidence)
- Grade computation weights (ToS 30%, WAF 20%, robots 20%, RSL 15%, metadata 10%, RSS/sitemap 5%) — Author's recommendation based on domain analysis, not established standard, needs validation

---
*Research completed: 2026-02-13*
*Ready for roadmap: yes*
