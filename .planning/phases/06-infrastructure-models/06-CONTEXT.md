# Phase 6: Infrastructure & Models - Context

**Gathered:** 2026-02-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Developer foundation for the v2.0 pipeline: Redis/RQ infrastructure, data models (Publisher extension, ResolutionJob), pytest setup, and URL normalization. No UI, no pipeline logic, no fetch strategies -- just the building blocks.

</domain>

<decisions>
## Implementation Decisions

### Data modeling -- Publisher
- Extend the existing Publisher model in place (preserve existing data and admin functionality)
- One domain = one publisher (keyed by canonical domain, not a multi-domain publisher group)
- Publisher-level discovery results (WAF, ToS, robots.txt, etc.) stored as flat fields on Publisher, not separate models or JSON
- Freshness TTL configured as a single Django setting (`PUBLISHER_FRESHNESS_TTL`), same for all publishers

### Data modeling -- ResolutionJob
- Every URL always resolves to a publisher (create on the fly if it doesn't exist)
- Job identified by UUID (e.g., `/jobs/550e8400-e29b...`)
- Pipeline step results (waf_result, tos_result, etc.) stored on the job itself -- job is the complete record of what happened for that URL submission
- Duplicate URL submissions redirect to the existing job's results (no new job created)

### URL normalization
- Use a well-established third-party package -- don't hand-roll normalization logic
- Strip known tracking parameters (utm_*, fbclid, etc.) but keep other query params
- www and bare domain treated as same publisher (strip www)
- Strip URL fragments (#section)
- Preserve trailing slashes as-is

### Claude's Discretion
- Docker/services topology and docker-compose structure
- Test conventions, factory patterns, fixture strategy
- Choice of URL normalization package
- Exact fields and types on Publisher and ResolutionJob models

</decisions>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 06-infrastructure-models*
*Context gathered: 2026-02-14*
