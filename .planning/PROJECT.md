# itsascout

## What This Is

A publisher website analysis tool that ingests publisher URLs, runs a 3-stage AI pipeline (WAF detection, Terms of Service discovery, permissions evaluation), and displays results in an interactive data table. Built for assessing scraping feasibility and legal permissions across publisher sites at scale.

## Core Value

Automated analysis of publisher websites to determine scraping permissions and restrictions — WAF detection, ToS discovery, and permission evaluation in a single pipeline.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- Publisher URL ingestion from CSV (bulk import)
- WAF detection via wafw00f integration
- ToS URL discovery via pydantic-ai agent (GPT-4.1-nano)
- ToS permissions evaluation via pydantic-ai agent
- HTML fetching through Zyte proxy API
- Interactive React data table with sorting, filtering, expandable rows
- Django admin with custom actions (WAF scan, discover terms, evaluate, queue analysis)
- Async task pipeline (WAF → discovery → evaluation)
- PostgreSQL data persistence

### Active

<!-- Current scope. Building toward these. -->

- [ ] Refactor to django-inertia for SPA-like navigation
- [ ] Consolidate React frontend into Django project (sgui/ → scrapegrape/frontend/)
- [ ] Multi-page architecture ready for future views

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- New analysis types — this milestone is purely refactoring architecture
- UI redesign — keep existing table view, just change how it's served
- Tech debt cleanup (hardcoded secrets, etc.) — separate concern

## Current Milestone: v1.0 Inertia Refactor

**Goal:** Refactor from JSON-in-template rendering to django-inertia, consolidate sgui/ into scrapegrape/frontend/, and establish multi-page architecture.

**Target features:**
- Django-Inertia integration replacing current template-embedded JSON pattern
- Consolidated project structure (single package)
- SPA-like navigation foundation for future pages

## Context

- Current architecture: Django renders HTML template with embedded JSON, React parses it client-side
- Frontend lives in separate `sgui/` directory with its own Vite build
- Django-vite currently bridges Django templates and Vite-built assets
- Single view currently: data table at "/"
- Django admin at "/admin/"

## Constraints

- **Stack**: Stay with Django + React + Vite + TailwindCSS — no framework changes beyond adding Inertia
- **Functionality**: All existing features must work identically after refactor
- **Data**: No database schema changes needed

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| django-inertia over other SPA approaches | Keeps Django as source of truth, avoids building separate API layer | — Pending |
| Consolidate into scrapegrape/frontend/ | Single project, simpler DX, co-located code | — Pending |

---
*Last updated: 2026-02-12 after milestone v1.0 initialization*
