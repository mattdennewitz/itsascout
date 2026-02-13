# Requirements: itsascout

**Defined:** 2026-02-13
**Core Value:** Paste a URL, get a comprehensive scraping report card -- what's allowed, what's blocked, and what structured data is available -- with real-time progress as each check completes.

## v2.0 Requirements

Requirements for the Core Workflow milestone. Each maps to roadmap phases.

### Infrastructure

- [ ] **INFRA-01**: Redis 7 service runs in Docker Compose with persistent volume
- [ ] **INFRA-02**: RQ worker service runs in Docker Compose processing queued jobs
- [ ] **INFRA-03**: django-rq replaces django_tasks as the task backend with admin monitoring

### URL Entry

- [ ] **ENTRY-01**: User can submit a single URL from a prominent input on the homepage
- [ ] **ENTRY-02**: Submitted URLs are sanitized and normalized (lowercase hostname, strip www, normalize scheme, sort query params)
- [ ] **ENTRY-03**: Duplicate URL submissions resolve to existing job results instead of re-running

### Pipeline

- [ ] **PIPE-01**: Submitting a URL creates a ResolutionJob with UUID and queues the analysis pipeline
- [ ] **PIPE-02**: Pipeline executes as a single supervisor RQ job running steps sequentially
- [ ] **PIPE-03**: User receives real-time SSE progress updates as each pipeline step completes
- [ ] **PIPE-04**: Pipeline skips publisher-level steps if publisher was checked within configurable TTL

### Fetch Strategy

- [ ] **FETCH-01**: Pipeline fetches pages using curl-cffi with browser TLS fingerprinting as primary strategy
- [ ] **FETCH-02**: Pipeline falls back to Zyte proxy API when curl-cffi fails
- [ ] **FETCH-03**: Working fetch strategy is remembered per publisher for future jobs

### Publisher Discovery

- [ ] **DISC-01**: Pipeline resolves publisher identity from domain (metadata extraction or LLM inference)
- [ ] **DISC-02**: Pipeline detects WAF type via wafw00f (existing capability, integrated into new pipeline)
- [ ] **DISC-03**: Pipeline discovers ToS/privacy URLs and evaluates scraping permissions (existing capability, integrated into new pipeline)
- [ ] **DISC-04**: Pipeline fetches and parses robots.txt, checking if submitted URL is permitted
- [ ] **DISC-05**: Pipeline discovers sitemap URLs from robots.txt directives and common paths
- [ ] **DISC-06**: Pipeline discovers RSS/Atom feed URLs from HTML link tags
- [ ] **DISC-07**: Pipeline detects RSL (Really Simple Licensing) indicators via HTML tags, HTTP headers, and robots.txt directives

### Article Analysis

- [ ] **ART-01**: Pipeline extracts article metadata via extruct (JSON-LD, OpenGraph, Microdata)
- [ ] **ART-02**: Pipeline detects paywall status via isAccessibleForFree schema.org markup
- [ ] **ART-03**: LLM generates human-readable summary of what metadata is available on publisher article pages (article details, byline, paywall, thumbnail, etc.)
- [ ] **ART-04**: Report shows yes/no indicators for structured data formats (JSON-LD, OpenGraph, Microdata)

### Report Card

- [ ] **RPRT-01**: User views analysis results at a unique URL keyed by job UUID
- [ ] **RPRT-02**: Results page progressively reveals cards as pipeline steps complete via SSE
- [ ] **RPRT-03**: Report card displays publisher-level findings (WAF, ToS, robots.txt, sitemap, RSS, RSL, metadata profile)
- [ ] **RPRT-04**: Report card displays article-level findings (extracted metadata, paywall status, crawl permission)
- [ ] **RPRT-05**: Existing publisher table continues working as admin/management view

### Testing

- [ ] **TEST-01**: pytest configured with Django test database, fixtures, and factory patterns for Publisher/ResolutionJob
- [ ] **TEST-02**: Each pipeline step has unit tests with mocked external services (curl-cffi, Zyte, wafw00f, LLM)
- [ ] **TEST-03**: URL sanitization has comprehensive edge case tests (unicode, IDN, www stripping, query param sorting, fragments)
- [ ] **TEST-04**: Integration test verifies full pipeline execution from URL submission to completed job
- [ ] **TEST-05**: SSE endpoint has tests verifying event streaming and connection lifecycle

## Future Requirements

Deferred to future milestones. Tracked but not in current roadmap.

### Grade & Scoring

- **GRADE-01**: Overall feasibility grade (A-F) computed from weighted pipeline results
- **GRADE-02**: Grade breakdown showing contribution of each factor

### History & Trends

- **HIST-01**: User can view analysis history for a publisher over time
- **HIST-02**: Publisher report card shows when findings last changed

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| RSS feed crawling | Just discover and remember URLs, don't fetch content |
| Sitemap crawling/parsing entries | Discover existence and count, don't enumerate all URLs |
| Batch/bulk URL analysis | Single-URL flow first, batch later |
| Automated scraper generation | Assessment tool, not scraper builder |
| Content extraction/display | Legal risk from copyright concerns |
| Mobile app | Web-first approach |
| SSR setup | Adds Node.js process complexity |
| Competitor comparison | Different product scope |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 6 | Pending |
| INFRA-02 | Phase 6 | Pending |
| INFRA-03 | Phase 6 | Pending |
| ENTRY-01 | Phase 8 | Pending |
| ENTRY-02 | Phase 6 | Pending |
| ENTRY-03 | Phase 8 | Pending |
| PIPE-01 | Phase 8 | Pending |
| PIPE-02 | Phase 8 | Pending |
| PIPE-03 | Phase 8 | Pending |
| PIPE-04 | Phase 8 | Pending |
| FETCH-01 | Phase 7 | Pending |
| FETCH-02 | Phase 7 | Pending |
| FETCH-03 | Phase 7 | Pending |
| DISC-01 | Phase 8 | Pending |
| DISC-02 | Phase 8 | Pending |
| DISC-03 | Phase 8 | Pending |
| DISC-04 | Phase 9 | Pending |
| DISC-05 | Phase 9 | Pending |
| DISC-06 | Phase 9 | Pending |
| DISC-07 | Phase 9 | Pending |
| ART-01 | Phase 10 | Pending |
| ART-02 | Phase 10 | Pending |
| ART-03 | Phase 10 | Pending |
| ART-04 | Phase 10 | Pending |
| RPRT-01 | Phase 8 | Pending |
| RPRT-02 | Phase 8 | Pending |
| RPRT-03 | Phase 11 | Pending |
| RPRT-04 | Phase 11 | Pending |
| RPRT-05 | Phase 8 | Pending |
| TEST-01 | Phase 6 | Pending |
| TEST-02 | Phase 8 | Pending |
| TEST-03 | Phase 6 | Pending |
| TEST-04 | Phase 11 | Pending |
| TEST-05 | Phase 8 | Pending |

**Coverage:**
- v2.0 requirements: 34 total
- Mapped to phases: 34
- Unmapped: 0

---
*Requirements defined: 2026-02-13*
*Last updated: 2026-02-13 after roadmap creation*
