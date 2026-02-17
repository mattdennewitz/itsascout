# Roadmap: itsascout

## Milestones

- ✅ **v1.0 Inertia Refactor** -- Phases 1-5 (shipped 2026-02-13)
- 🚧 **v2.0 Core Workflow** -- Phases 6-11 (in progress)

## Phases

<details>
<summary>v1.0 Inertia Refactor (Phases 1-5) -- SHIPPED 2026-02-13</summary>

- [x] Phase 1: Inertia Infrastructure (1/1 plans) -- completed 2026-02-12
- [x] Phase 2: Frontend Consolidation (1/1 plans) -- completed 2026-02-12
- [x] Phase 3: Core View Migration (2/2 plans) -- completed 2026-02-12
- [x] Phase 4: Interactive Features (2/2 plans) -- completed 2026-02-12
- [x] Phase 5: Cleanup & Verification (2/2 plans) -- completed 2026-02-13

</details>

### v2.0 Core Workflow

**Milestone Goal:** Build the end-to-end URL analysis workflow with streaming progress, durable publisher intelligence, and a report card UI.

- [x] **Phase 6: Infrastructure & Models** -- Redis, RQ, data models, pytest setup, URL sanitization -- completed 2026-02-14
- [x] **Phase 7: Fetch Strategy** -- curl-cffi with browser TLS fingerprinting and Zyte fallback -- completed 2026-02-14
- [x] **Phase 8: Core Pipeline & SSE** -- End-to-end URL entry through streaming results with publisher resolution, WAF, and ToS -- completed 2026-02-14
- [x] **Phase 9: Publisher Discovery** -- robots.txt, sitemap, RSS, and RSL pipeline steps -- completed 2026-02-14
- [ ] **Phase 10: Article Metadata** -- Structured data extraction, paywall detection, and LLM metadata profiling
- [ ] **Phase 11: Report Card UI** -- Publisher and article report cards with full end-to-end integration test

## Phase Details

### Phase 6: Infrastructure & Models
**Goal:** Developer has a working Redis/RQ/pytest foundation with data models and URL normalization, ready for pipeline development
**Depends on:** v1.0 complete (Phase 5)
**Requirements:** INFRA-01, INFRA-02, INFRA-03, ENTRY-02, TEST-01, TEST-03
**Success Criteria** (what must be TRUE):
  1. `docker compose up` starts Redis, RQ worker, and Django services with all three healthy
  2. An RQ job queued from Django code executes in the worker and completes successfully
  3. RQ job queue and worker status are visible in Django admin via django-rq
  4. `uv run pytest` runs a passing test suite with factory-created Publisher and ResolutionJob instances
  5. URL sanitizer normalizes variant URLs (http vs https, www vs bare, mixed case, query param order) to identical canonical forms
**Plans:** 2 plans

Plans:
- [x] 06-01-PLAN.md -- Redis, RQ worker, and django-rq Docker infrastructure
- [x] 06-02-PLAN.md -- Data models, URL sanitizer, and pytest setup (TDD)

### Phase 7: Fetch Strategy
**Goal:** Pipeline steps can fetch any page through a strategy manager that tries curl-cffi first, falls back to Zyte, and remembers what works per publisher
**Depends on:** Phase 6
**Requirements:** FETCH-01, FETCH-02, FETCH-03
**Success Criteria** (what must be TRUE):
  1. Fetch strategy manager retrieves a page using curl-cffi with browser TLS impersonation as the default path
  2. When curl-cffi fails (connection error, WAF block), fetch automatically falls back to Zyte proxy API and succeeds
  3. After a successful fetch, the working strategy is saved on the Publisher record and used for subsequent fetches against the same publisher
**Plans:** 1 plan

Plans:
- [x] 07-01-PLAN.md -- Fetch strategy manager with curl-cffi, Zyte fallback, and per-publisher memory (TDD)

### Phase 8: Core Pipeline & SSE
**Goal:** User can paste a URL and watch real-time progress as the pipeline resolves the publisher, checks WAF, and evaluates ToS -- with results at a shareable URL
**Depends on:** Phase 7
**Requirements:** ENTRY-01, ENTRY-03, PIPE-01, PIPE-02, PIPE-03, PIPE-04, DISC-01, DISC-02, DISC-03, RPRT-01, RPRT-02, RPRT-05, TEST-02, TEST-05
**Success Criteria** (what must be TRUE):
  1. User submits a URL from the homepage and sees a streaming progress page at a unique job URL (e.g., /jobs/<uuid>)
  2. As each pipeline step completes (publisher resolution, WAF, ToS discovery, ToS evaluation), an SSE event updates the progress UI in real time
  3. Submitting a duplicate URL redirects to the existing job results instead of re-running the pipeline
  4. Pipeline skips publisher-level steps when the publisher was analyzed within the configured freshness TTL
  5. Existing publisher table and admin actions continue working unchanged
**Plans:** 3 plans

Plans:
- [x] 08-01-PLAN.md -- Pipeline supervisor with WAF and ToS steps (TDD)
- [x] 08-02-PLAN.md -- Daphne ASGI, URL submission, SSE endpoint, and job views
- [x] 08-03-PLAN.md -- Jobs/Show.tsx with EventSource and homepage URL input

### Phase 9: Publisher Discovery
**Goal:** Pipeline discovers and caches publisher crawling policy signals -- robots.txt rules, sitemap locations, RSS feeds, and RSL licensing
**Depends on:** Phase 8
**Requirements:** DISC-04, DISC-05, DISC-06, DISC-07
**Success Criteria** (what must be TRUE):
  1. Pipeline fetches robots.txt, parses rules with protego, and reports whether the submitted URL is allowed or disallowed
  2. Pipeline discovers sitemap URLs from robots.txt directives and common paths, storing found URLs on the publisher
  3. Pipeline discovers RSS/Atom feed URLs from HTML link tags, storing found URLs on the publisher
  4. Pipeline detects RSL licensing indicators via HTML tags, HTTP headers, and robots.txt directives
**Plans:** 2 plans

Plans:
- [x] 09-01-PLAN.md -- robots.txt and sitemap discovery pipeline steps (TDD)
- [x] 09-02-PLAN.md -- RSS feed discovery, RSL detection, and frontend update (TDD)

### Phase 10: Article Metadata
**Goal:** Pipeline extracts structured data from the submitted article URL -- what metadata is available, whether it is paywalled, and an LLM-generated human-readable profile
**Depends on:** Phase 8 (uses fetch strategy from Phase 7)
**Requirements:** ART-01, ART-02, ART-03, ART-04
**Success Criteria** (what must be TRUE):
  1. Pipeline extracts article metadata via extruct (JSON-LD, OpenGraph, Microdata) and stores structured results on the job
  2. Pipeline detects paywall status from isAccessibleForFree schema.org markup
  3. LLM generates a human-readable summary of what metadata is available on the publisher's article pages
  4. Report shows yes/no indicators for each structured data format present (JSON-LD, OpenGraph, Microdata)
**Plans:** 2 plans

Plans:
- [ ] 10-01-PLAN.md -- ArticleMetadata model and article step functions with TDD
- [ ] 10-02-PLAN.md -- Supervisor wiring, frontend article steps, and integration tests

### Phase 11: Report Card UI
**Goal:** User sees a complete, polished report card with publisher-level and article-level findings, and the full pipeline is verified end-to-end
**Depends on:** Phase 9, Phase 10
**Requirements:** RPRT-03, RPRT-04, TEST-04
**Success Criteria** (what must be TRUE):
  1. Report card displays all publisher-level findings in distinct sections: WAF status, ToS permissions, robots.txt rules, sitemap URLs, RSS feeds, RSL status, and metadata profile
  2. Report card displays article-level findings: extracted metadata fields, paywall status, and crawl permission from robots.txt
  3. Full integration test passes: submitting a URL creates a job, pipeline executes all steps, and completed results are retrievable at the job URL
**Plans:** TBD

Plans:
- [ ] 11-01: Publisher and article report card components
- [ ] 11-02: End-to-end integration test and polish

## Progress

**Execution Order:** 6 -> 7 -> 8 -> 9 -> 10 -> 11
(Phase 10 depends on Phase 8 but not Phase 9; phases 9 and 10 could overlap but are sequenced for simplicity.)

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Inertia Infrastructure | v1.0 | 1/1 | Complete | 2026-02-12 |
| 2. Frontend Consolidation | v1.0 | 1/1 | Complete | 2026-02-12 |
| 3. Core View Migration | v1.0 | 2/2 | Complete | 2026-02-12 |
| 4. Interactive Features | v1.0 | 2/2 | Complete | 2026-02-12 |
| 5. Cleanup & Verification | v1.0 | 2/2 | Complete | 2026-02-13 |
| 6. Infrastructure & Models | v2.0 | 2/2 | Complete | 2026-02-14 |
| 7. Fetch Strategy | v2.0 | 1/1 | Complete | 2026-02-14 |
| 8. Core Pipeline & SSE | v2.0 | 3/3 | Complete | 2026-02-14 |
| 9. Publisher Discovery | v2.0 | 2/2 | Complete | 2026-02-14 |
| 10. Article Metadata | v2.0 | 0/2 | Not started | - |
| 11. Report Card UI | v2.0 | 0/2 | Not started | - |

**v2.0 Overall:** 27/34 requirements complete (79%)

### Phase 12: Django Built-in Authentication

**Goal:** [To be planned]
**Depends on:** Phase 11
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd:plan-phase 12 to break down)

---

*Roadmap created: 2026-02-12*
*v1.0 shipped: 2026-02-13*
*v2.0 roadmap created: 2026-02-13*
*Full v1.0 details: .planning/milestones/v1.0-ROADMAP.md*
