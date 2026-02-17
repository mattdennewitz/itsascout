# Phase 11: Report Card UI - Research

**Researched:** 2026-02-17
**Domain:** React/Inertia.js UI rendering, Django view props, end-to-end integration testing
**Confidence:** HIGH

## Summary

Phase 11 transforms the existing Jobs/Show page from a pipeline-progress tracker (step cards showing SSE events) into a polished report card that displays all publisher-level and article-level findings. The current Jobs/Show.tsx already receives all result data via Inertia props (`waf_result`, `tos_result`, `robots_result`, `sitemap_result`, `rss_result`, `rsl_result`, `ai_bot_result`, `metadata_result`, `article_result`) and renders one-line summaries inside step cards. The task is to replace/augment these summaries with rich, structured report card sections once the job is completed.

The project already has a strong UI pattern established in `Publishers/Detail.tsx` -- it uses Card, Collapsible, Table, Tooltip, and Badge components from the existing shadcn/ui component library, plus lucide-react icons. The report card should follow this same design language. No new libraries are needed.

**Primary recommendation:** Refactor Jobs/Show.tsx to show step cards during pipeline execution (current behavior) and switch to a rich report card view when `job.status === 'completed'`. Reuse component patterns from Publishers/Detail.tsx. Write a Django integration test that POSTs to /submit and verifies the job reaches "completed" with populated result fields.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | ^19.1.0 | UI rendering | Already installed |
| @inertiajs/react | ^2.3.14 | Server-driven SPA navigation | Already installed, all pages use it |
| lucide-react | ^0.525.0 | Icons | Already used in Detail.tsx |
| radix-ui | ^1.4.3 | Collapsible, Tooltip, etc. | Already installed via shadcn/ui |
| tailwindcss | ^4.1.11 | Styling | Already installed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| class-variance-authority | ^0.7.1 | Badge/Button variants | Already used in Badge component |
| pytest + factory_boy | existing | Integration tests | Already configured in project |

### Alternatives Considered
None needed -- the existing stack covers all requirements.

**Installation:**
No new packages required.

## Architecture Patterns

### Current Page Structure
```
src/Pages/
  Jobs/
    Show.tsx          # Pipeline progress + report card (this phase)
  Publishers/
    Detail.tsx        # Publisher detail page (pattern to follow)
    Index.tsx         # Publisher list with URL submit form
```

### Pattern 1: Conditional Rendering Based on Job Status
**What:** Show step cards during pipeline execution, show report card when completed.
**When to use:** Jobs/Show.tsx already checks `job.status` to decide SSE behavior.
**Example:**
```typescript
function Show({ job }: JobProps) {
    const isCompleted = job.status === 'completed'

    if (isCompleted) {
        return <ReportCard job={job} />
    }

    // ... existing step cards + SSE logic
}
```

### Pattern 2: Section-Based Report Card Layout (from Detail.tsx)
**What:** Each finding category is a Card with Collapsible sections.
**When to use:** For the completed report card view.
**Example:**
```typescript
// Status overview row (like Detail.tsx grid)
<Card className="mb-6">
    <div className="grid grid-cols-2 md:grid-cols-5 divide-x divide-gray-300">
        <StatusIndicator icon={Shield} label="WAF" value="..." />
        <StatusIndicator icon={Bot} label="Robots.txt" value="..." />
        ...
    </div>
</Card>

// Collapsible detail sections
<Collapsible>
    <Card className="mb-6">
        <CollapsibleTrigger className="w-full group">
            <CardHeader>...</CardHeader>
        </CollapsibleTrigger>
        <CollapsibleContent>
            <CardContent>...</CardContent>
        </CollapsibleContent>
    </Card>
</Collapsible>
```

### Pattern 3: Data Shape Awareness
**What:** The job's JSON result fields have specific structures that the UI must understand.
**Key data shapes from the pipeline:**

```typescript
// waf_result
{ waf_detected: boolean, waf_type: string, error?: string }

// tos_result (merged discovery + evaluation)
{ tos_url: string | null, confidence: number, permissions?: Permission[],
  scraping_permitted?: boolean, document_type?: string }

// robots_result
{ robots_found: boolean, url_allowed: boolean, sitemaps_from_robots: string[],
  crawl_delay: number | null, license_directives: string[] }

// ai_bot_result
{ robots_found: boolean, bots: Record<string, {company: string, blocked: boolean}>,
  blocked_count: number, total_count: number }

// sitemap_result
{ sitemap_urls: string[], source: string, count: number }

// rss_result
{ feeds: Array<{url: string, type: string, title: string}>, count: number }

// rsl_result
{ rsl_detected: boolean, indicators: Array<{source: string, url: string}>, count: number }

// metadata_result (publisher details)
{ found: boolean, source: string, score: number,
  organization: { name, type, url, id, logo, same_as } | null }

// article_result (combined extraction + paywall + profile)
{ jsonld_fields: Record | null, opengraph_fields: Record | null,
  microdata_fields: Record | null, twitter_cards: Record | null,
  formats_found: string[],
  paywall: { paywall_status: string, signals: string[], schema_accessible: boolean | null },
  profile: { summary: string, quality_score: number } }
```

### Pattern 4: Existing Component Reuse from Detail.tsx
**What:** Detail.tsx already has reusable component patterns that can be extracted or copied.
**Components to reuse/adapt:**
- `StatusIndicator` -- compact icon+label+value row item
- `PermissionStatus` -- green/red/amber permission badge
- `UrlList` with Collapsible for 3+ URLs
- `FormatBadge` -- emerald/gray presence indicator
- `PaywallBadge` -- color-coded paywall status

### Anti-Patterns to Avoid
- **Duplicating logic between Detail.tsx and Jobs/Show.tsx:** Extract shared components into `/components/` directory if the same rendering logic is needed in both places.
- **Deeply nested conditional rendering:** Use early returns and separate components for each report card section.
- **Displaying raw JSON fields:** Always map pipeline result fields to human-readable labels.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Collapsible sections | Custom accordion | Radix Collapsible (already installed) | Accessibility, animation built-in |
| Tooltips | Custom hover popover | Radix Tooltip (already installed) | Positioning, accessibility |
| Status badges | Custom styled spans | Existing Badge component + FormatBadge/PaywallBadge patterns | Consistency |
| Icon library | SVG sprites | lucide-react (already installed) | Tree-shakeable, consistent with codebase |

## Common Pitfalls

### Pitfall 1: Null/Missing Result Fields
**What goes wrong:** Report card crashes when a result field is null (e.g., job completed but a step was skipped due to freshness TTL).
**Why it happens:** When publisher steps are skipped, `waf_result`, `tos_result`, etc. remain null on the job. Article steps can also be skipped.
**How to avoid:** Every section must handle null gracefully. Check `job.waf_result` before accessing `.waf_detected`. Show "Skipped (recently checked)" or "N/A" for null sections.
**Warning signs:** TypeScript `Record<string, unknown> | null` type annotations on all result fields.

### Pitfall 2: Merged tos_result Shape
**What goes wrong:** Expecting separate discovery and evaluation fields, but they're merged into one `tos_result` JSON field.
**Why it happens:** The supervisor merges `tos_discovery_result` and `tos_eval_result` into a single `job.tos_result` (line 136 of supervisor.py).
**How to avoid:** Check for both `tos_url` (discovery) and `permissions`/`scraping_permitted` (evaluation) within the same `tos_result` object.

### Pitfall 3: Article Result Nesting
**What goes wrong:** Accessing paywall/profile data at the wrong level.
**Why it happens:** `article_result` nests paywall under `.paywall` and profile under `.profile` (supervisor lines 260-264).
**How to avoid:** Always access as `job.article_result.paywall.paywall_status` and `job.article_result.profile.summary`.

### Pitfall 4: Step Cards vs Report Card State Transition
**What goes wrong:** SSE step cards flash briefly then disappear when job completes and Inertia reloads.
**Why it happens:** On `router.reload()` after SSE 'done' event, the page re-renders with `job.status === 'completed'` and should switch to report card view.
**How to avoid:** Make the transition clean -- the existing `initialStatuses` memo already hydrates step cards from completed job props. The report card view should be the default for completed jobs from the start.

### Pitfall 5: Integration Test Requires Running Pipeline
**What goes wrong:** Test tries to POST to /submit and wait for pipeline completion, but pipeline requires Redis, external HTTP fetches, and LLM calls.
**Why it happens:** The pipeline calls wafw00f, Zyte, and GPT-4.1-nano.
**How to avoid:** Mock the pipeline steps (monkeypatch) and/or mock `run_pipeline.delay` to execute synchronously with mocked step functions. Existing test_pipeline.py shows the monkeypatch pattern.

## Code Examples

### Report Card Section for WAF Status
```typescript
function WafSection({ result }: { result: Record<string, unknown> | null }) {
    if (!result) return <SectionPlaceholder label="WAF Detection" reason="Not checked" />

    const detected = result.waf_detected as boolean
    const wafType = result.waf_type as string

    return (
        <div className="flex items-center gap-3 py-3 px-4">
            <Shield className="size-4 text-muted-foreground shrink-0" />
            <div>
                <p className="text-xs text-muted-foreground">WAF</p>
                <p className="text-sm font-medium">
                    {detected ? (wafType || 'Detected') : 'None detected'}
                </p>
            </div>
        </div>
    )
}
```

### Integration Test Pattern (Django + pytest)
```python
@pytest.mark.django_db
class TestFullPipelineIntegration:
    def test_submit_url_creates_job_pipeline_completes(self, client, monkeypatch):
        """TEST-04: Submit URL -> job created -> pipeline runs -> results retrievable."""
        # Mock pipeline to run synchronously with mocked steps
        from publishers.pipeline.supervisor import run_pipeline as real_pipeline

        def mock_run_pipeline_sync(job_id):
            # Set job to completed with mock results
            job = ResolutionJob.objects.get(id=job_id)
            job.status = "completed"
            job.waf_result = {"waf_detected": False, "waf_type": ""}
            job.tos_result = {"tos_url": "https://example.com/tos"}
            # ... populate all result fields
            job.save()

        mock_delay = MagicMock(side_effect=lambda job_id: mock_run_pipeline_sync(job_id))
        monkeypatch.setattr("publishers.views.run_pipeline.delay", mock_delay)

        # Submit URL
        response = client.post("/submit", {"url": "https://example.com/article"})
        assert response.status_code == 302

        # Follow redirect to job page
        job = ResolutionJob.objects.first()
        response = client.get(f"/jobs/{job.id}")
        assert response.status_code == 200

        # Verify job completed with results
        job.refresh_from_db()
        assert job.status == "completed"
        assert job.waf_result is not None
```

### Extracting Shared Components Pattern
```typescript
// src/components/report/StatusIndicator.tsx
// Extracted from Detail.tsx for reuse in Jobs/Show.tsx
export function StatusIndicator({ label, value, icon: Icon, tooltip }: {
    label: string
    value: string
    icon: React.ElementType
    tooltip?: string
}) {
    // ... same implementation as Detail.tsx
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Step cards only | Step cards during progress, report card when done | Phase 11 | Users see structured findings, not just status |
| Data on Publisher model only | Data on both Publisher + ResolutionJob | Phase 8 | Job page can show results without Publisher lookup |

**Current state:**
- Jobs/Show.tsx shows step cards with one-line summaries for both running and completed jobs
- Publishers/Detail.tsx shows rich publisher-level findings with collapsible sections
- Both pages receive data via Inertia props from Django views
- No shared component library between the two pages (duplication opportunity)

## Open Questions

1. **Should report card components be shared with Publishers/Detail.tsx?**
   - What we know: Detail.tsx has StatusIndicator, PermissionStatus, UrlList, FormatBadge, PaywallBadge components. Jobs/Show report card needs similar components.
   - What's unclear: Whether to extract into shared components or accept some duplication.
   - Recommendation: Extract shared components (StatusIndicator, PermissionStatus, UrlList, FormatBadge, PaywallBadge) into `src/components/report/` and import from both pages. This reduces maintenance burden.

2. **Should the step cards still be visible on completed jobs?**
   - What we know: Currently completed jobs show step cards hydrated from props. The phase goal says "report card displays findings."
   - What's unclear: Whether to keep step cards as a secondary view or replace entirely.
   - Recommendation: Replace step cards with the report card view for completed jobs. Step cards are only useful during pipeline execution. Users visiting a completed job want findings, not pipeline steps.

3. **What does the robots.txt crawl permission for the article URL look like in the report card?**
   - What we know: `robots_result.url_allowed` is a boolean for the submitted URL. RPRT-04 requires "crawl permission from robots.txt" in article-level findings.
   - What's unclear: The robots_result is stored at job level (publisher step), but the requirement lists it as article-level.
   - Recommendation: Display it in the article section as "Crawl Permission: Allowed/Disallowed by robots.txt" since it's specific to the submitted article URL.

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `Jobs/Show.tsx` (current step card UI, data shapes)
- Codebase inspection: `Publishers/Detail.tsx` (report card design patterns)
- Codebase inspection: `publishers/pipeline/supervisor.py` (result data structures)
- Codebase inspection: `publishers/pipeline/steps.py` (all step return shapes)
- Codebase inspection: `publishers/views.py` (job_show prop serialization)
- Codebase inspection: `publishers/models.py` (ResolutionJob, ArticleMetadata models)

### Secondary (MEDIUM confidence)
- Codebase inspection: `publishers/tests/test_views.py` (test patterns for views)
- Codebase inspection: `publishers/tests/test_pipeline.py` (monkeypatch patterns)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new libraries needed, everything already installed and in use
- Architecture: HIGH - Clear patterns established in Detail.tsx and existing Jobs/Show.tsx
- Data shapes: HIGH - All result structures verified from pipeline step functions and supervisor
- Pitfalls: HIGH - Identified from direct code reading (null handling, nesting, merging)
- Integration test: MEDIUM - Pattern clear from existing tests, but full pipeline mock complexity is moderate

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (stable -- internal UI, no external API changes expected)
