# Phase 18: Competitive Intelligence UI - Research

**Researched:** 2026-02-18
**Domain:** React UI components, report card layout, data display patterns
**Confidence:** HIGH

## Summary

Phase 18 adds a "Competitive Intelligence" section to the report card in `Jobs/Show.tsx`. All backend data is already flowing to the frontend -- Phase 17 confirmed that `cc_result`, `sitemap_analysis_result`, `frequency_result`, and `news_signals_result` are passed as Inertia props. The report card (`ReportCard` component in Show.tsx) currently displays CC presence and RSL inline within the "Discovery" collapsible section, but has no dedicated Competitive Intelligence section and no display for Google News readiness or update frequency.

The work is purely frontend: add a new Card section to the `ReportCard` component with three sub-sections (CC presence, Google News readiness, update frequency), create reusable badge/indicator components where appropriate, and ensure graceful handling of null/missing data for all three signals.

**Primary recommendation:** Add a single `<Card>` with `<CardTitle>Competitive Intelligence</CardTitle>` containing three sub-sections. Remove CC presence from the Discovery section (avoid duplication). Create a `ReadinessBadge` component for the Google News readiness level and a `ConfidenceBadge` component for the frequency confidence indicator. Follow the existing FormatBadge/PaywallBadge pattern.

## Standard Stack

### Core

No new libraries needed. This phase modifies existing files only.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | ^19.1.0 | UI rendering | Already installed |
| @inertiajs/react | ^2.3.14 | Server-driven SPA | Already installed |
| lucide-react | ^0.525.0 | Icons | Already used throughout |
| tailwindcss | ^4.1.11 | Styling | Already installed |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| class-variance-authority | ^0.7.1 | Badge variants | Already used in Badge component |

### Alternatives Considered

N/A -- no choices to make. Existing component library covers all needs.

## Architecture Patterns

### Current Report Card Structure

```
ReportCard component (Jobs/Show.tsx line 422):
  - Publisher metadata info row (line 446)
  - Status overview Card (WAF, Robots, ToS, RSL, Feeds) (line 466)
  - Terms of Service Collapsible Card (line 537)
  - Discovery Collapsible Card (line 601)
      - Sitemaps
      - RSS Feeds
      - AI Bot Blocking
      - RSL (inline)
      - Common Crawl (inline)         <-- currently here, should move
  - Article Analysis Card (line 699)
      - Crawl Permission
      - Paywall Status
      - Structured Data (format badges)
      - Metadata Profile
      - Field Presence Table
```

### Pattern 1: New Competitive Intelligence Section Placement

**What:** Add a new Card between Discovery and Article Analysis.
**Why:** Competitive intelligence is publisher-level data (not article-level), so it belongs after the publisher-level Discovery section but before article-specific analysis.
**Target structure:**
```
  - Status overview Card
  - Terms of Service Collapsible Card
  - Discovery Collapsible Card (remove CC from here)
  - Competitive Intelligence Card          <-- NEW
      - Common Crawl Presence
      - Google News Readiness
      - Update Frequency
  - Article Analysis Card
```

### Pattern 2: Sub-Section Layout Within Cards

The existing report card uses a consistent pattern for sub-sections within cards:

```typescript
<div className="flex items-center gap-2 mb-2">
    <Icon className="size-4 text-muted-foreground" />
    <h4 className="text-sm font-medium">Section Title</h4>
</div>
<div className="pl-6">
    {/* Content */}
</div>
```

Source: Discovery section in Show.tsx lines 614-693.

### Pattern 3: Badge Components for Categorical Values

The codebase uses small badge components for categorical display:

- `FormatBadge`: binary present/absent with emerald/gray colors
- `PaywallBadge`: 4-value enum with semantic colors (emerald/red/amber/gray)

Both use inline `<span>` with conditional className. The same pattern should be used for:
- **ReadinessBadge**: 4-value readiness level (strong/moderate/minimal/none)
- **ConfidenceBadge**: 3-value confidence level (high/medium/low)

### Pattern 4: Graceful Null Handling

Every section in the report card handles null data via `SectionPlaceholder`:

```typescript
function SectionPlaceholder({ label, reason }: { label: string; reason: string }) {
    return (
        <p className="text-sm text-muted-foreground">
            {label}: <span className="italic">{reason}</span>
        </p>
    )
}
```

Source: Show.tsx line 120.

### Anti-Patterns to Avoid

- **Duplicating CC display:** CC is currently shown in the Discovery section (lines 680-693). If added to Competitive Intelligence, remove it from Discovery to avoid showing the same data twice.
- **Deep nesting for signal breakdown:** Google News readiness has 3 signals -- display them as a flat list with check/cross icons, not nested collapsibles.
- **Showing raw technical field names:** Display "News Sitemap" not "has_news_sitemap", "NewsArticle Schema" not "has_news_article_schema".

## Data Shapes (Backend to Frontend)

All data is available via `job.*_result` props (verified in views.py lines 228-231).

### cc_result (Common Crawl Presence)
```typescript
// When available:
{ available: true, in_index: true, page_count: 15000, latest_crawl: "2025-11", collection: "CC-MAIN-2025-...", error: null }
// When not in index:
{ available: true, in_index: false, page_count: 0, latest_crawl: null, collection: "...", error: null }
// When API error:
{ available: false, in_index: null, page_count: null, latest_crawl: null, collection: "...", error: "Connection timeout" }
```

### news_signals_result (Google News Readiness)
```typescript
{
    readiness: "strong" | "moderate" | "minimal" | "none",
    signal_count: 0 | 1 | 2 | 3,
    signals: {
        has_news_sitemap: boolean,
        has_news_article_schema: boolean,
        article_schema_type: string,    // e.g., "NewsArticle"
        has_news_media_org: boolean,
        org_schema_type: string,        // e.g., "NewsMediaOrganization"
    },
    error: null | string
}
```

### frequency_result (Update Frequency)
```typescript
// When estimated:
{
    source: "rss" | "sitemap",
    frequency_label: "~5 articles/day",  // Human-readable
    frequency_hours: 4.8,                 // Median hours between posts
    confidence: "high" | "medium" | "low",
    sample_size: 25,
    date_span_days: 14.2,
    error: null
}
// When no data:
{
    source: "none",
    frequency_label: "",
    frequency_hours: null,
    confidence: "low",
    sample_size: 0,
    date_span_days: 0,
    error: null
}
```

### sitemap_analysis_result (used indirectly via news_signals_result)
```typescript
{
    has_news_sitemap: boolean,
    news_sitemap_url: string | null,
    sitemaps_checked: number,
    lastmod_dates: string[],
    error: null | string
}
```
Note: sitemap_analysis_result is consumed by the Google News step. The UI should NOT display sitemap_analysis_result directly -- it should use news_signals_result which aggregates it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Readiness badge colors | Custom color logic | Map readiness level to Tailwind classes like PaywallBadge | Consistency with existing pattern |
| Signal check/cross icons | Custom SVG | CircleCheck/CircleX from lucide-react (already used in AI Bot Blocking, Field Presence Table) | Consistent icon language |
| Collapsible section | Custom toggle state | Radix Collapsible (already used in Discovery/ToS sections) | Accessibility, animation |

**Key insight:** Every UI pattern needed for this phase already exists somewhere in Show.tsx or the report components directory. This is about assembly, not invention.

## Common Pitfalls

### Pitfall 1: CC Display Duplication
**What goes wrong:** CC presence shows in both Discovery and Competitive Intelligence sections.
**Why it happens:** CC is currently in the Discovery section (Show.tsx lines 680-693). Adding it to CI without removing from Discovery creates redundancy.
**How to avoid:** Remove the CC inline display from the Discovery section when adding it to Competitive Intelligence.
**Warning signs:** Same data appears in two places on the report card.

### Pitfall 2: Empty Frequency Label
**What goes wrong:** Frequency section shows blank text when `frequency_label` is empty string.
**Why it happens:** When no RSS or sitemap dates are available, `frequency_label` is `""` (empty string), not null.
**How to avoid:** Check `frequency_label` truthiness, not just null. Display "Could not estimate" or similar when empty.
**Warning signs:** Blank space in the frequency sub-section.

### Pitfall 3: Null Result vs Empty Result
**What goes wrong:** Section crashes or shows wrong state when result is null vs when result exists but indicates unavailability.
**Why it happens:** `cc_result` being null means "step didn't run" while `cc_result.available === false` means "step ran but API was unavailable". These need different UI treatments.
**How to avoid:**
- `result === null` --> "Not checked" (step never ran)
- `result.available === false` --> "Unavailable: [error message]" (step failed)
- `result.in_index === false` --> "Not found in Common Crawl" (step succeeded, no data)

Apply similar three-tier handling for frequency (null / empty label / has label) and news signals (null / error / has readiness).

### Pitfall 4: Google News Signal Breakdown With Missing Article Data
**What goes wrong:** News signals result has `article_schema_type: ""` and `has_news_article_schema: false` because the article step was skipped or had no JSON-LD.
**Why it happens:** Google News step handles null inputs gracefully, setting signals to false. The UI should show this as "not detected" rather than "error".
**How to avoid:** For each signal in the breakdown, show check/cross icon with clear labels. A false signal with empty schema type is "Not detected", not an error.

### Pitfall 5: Confidence Badge Misrepresenting Data Quality
**What goes wrong:** Users see "high confidence" badge but the frequency estimate is based on a bad source.
**Why it happens:** Confidence is already computed backend-side from sample_size and date_span_days. The UI just needs to display it.
**How to avoid:** Show confidence as a small secondary indicator (not prominently), and optionally show source ("from RSS" / "from sitemap") for transparency.

## Code Examples

### Competitive Intelligence Section (recommended structure)

```typescript
{/* Competitive Intelligence */}
<Card>
    <CardHeader>
        <CardTitle>Competitive Intelligence</CardTitle>
    </CardHeader>
    <CardContent className="space-y-5">
        {/* CC Presence */}
        <div>
            <div className="flex items-center gap-2 mb-1">
                <Globe className="size-4 text-muted-foreground" />
                <span className="text-sm font-medium">Common Crawl Presence</span>
            </div>
            {!job.cc_result ? (
                <SectionPlaceholder label="Common Crawl" reason="Not checked" />
            ) : job.cc_result.available === false ? (
                <p className="text-sm text-muted-foreground pl-6">
                    Unavailable{job.cc_result.error ? `: ${job.cc_result.error}` : ''}
                </p>
            ) : job.cc_result.in_index ? (
                <p className="text-sm text-muted-foreground pl-6">
                    ~{(job.cc_result.page_count as number).toLocaleString()} pages
                    {job.cc_result.latest_crawl && ` | Last crawled ${job.cc_result.latest_crawl}`}
                </p>
            ) : (
                <p className="text-sm text-muted-foreground pl-6">Not found in Common Crawl index</p>
            )}
        </div>

        {/* Google News Readiness */}
        <div>
            <div className="flex items-center gap-2 mb-1">
                <Newspaper className="size-4 text-muted-foreground" />
                <span className="text-sm font-medium">Google News Readiness</span>
                {newsSignals?.readiness && <ReadinessBadge level={newsSignals.readiness} />}
            </div>
            {/* Signal breakdown */}
        </div>

        {/* Update Frequency */}
        <div>
            <div className="flex items-center gap-2 mb-1">
                <Clock className="size-4 text-muted-foreground" />
                <span className="text-sm font-medium">Update Frequency</span>
            </div>
            {/* Frequency display with confidence */}
        </div>
    </CardContent>
</Card>
```

### ReadinessBadge Component

```typescript
// src/components/report/ReadinessBadge.tsx
export function ReadinessBadge({ level }: { level: string }) {
    const styles: Record<string, string> = {
        strong: 'bg-emerald-50 text-emerald-700',
        moderate: 'bg-blue-50 text-blue-700',
        minimal: 'bg-amber-50 text-amber-700',
        none: 'bg-gray-100 text-gray-500',
    }
    const labels: Record<string, string> = {
        strong: 'Strong',
        moderate: 'Moderate',
        minimal: 'Minimal',
        none: 'None',
    }
    return (
        <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${styles[level] ?? styles.none}`}>
            {labels[level] ?? level}
        </span>
    )
}
```

### ConfidenceBadge Component

```typescript
// src/components/report/ConfidenceBadge.tsx
export function ConfidenceBadge({ level }: { level: string }) {
    const styles: Record<string, string> = {
        high: 'bg-emerald-50 text-emerald-700',
        medium: 'bg-amber-50 text-amber-700',
        low: 'bg-gray-100 text-gray-500',
    }
    return (
        <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${styles[level] ?? styles.low}`}>
            {level} confidence
        </span>
    )
}
```

### Google News Signal Breakdown

```typescript
const signals = newsSignals?.signals as Record<string, unknown> | undefined

{signals && (
    <div className="space-y-1 pl-6">
        <SignalRow
            label="News Sitemap"
            present={signals.has_news_sitemap as boolean}
        />
        <SignalRow
            label="NewsArticle Schema"
            present={signals.has_news_article_schema as boolean}
            detail={signals.article_schema_type as string}
        />
        <SignalRow
            label="NewsMediaOrganization"
            present={signals.has_news_media_org as boolean}
            detail={signals.org_schema_type as string}
        />
    </div>
)}

function SignalRow({ label, present, detail }: {
    label: string; present: boolean; detail?: string
}) {
    return (
        <div className="flex items-center gap-1.5 text-sm">
            {present ? (
                <CircleCheck className="size-3.5 text-emerald-600 shrink-0" />
            ) : (
                <CircleX className="size-3.5 text-gray-300 shrink-0" />
            )}
            <span className={present ? 'text-foreground' : 'text-muted-foreground'}>
                {label}
            </span>
            {detail && present && (
                <span className="text-xs text-muted-foreground">({detail})</span>
            )}
        </div>
    )
}
```

## Exact Files to Modify

| File | Change | Why |
|------|--------|-----|
| `scrapegrape/frontend/src/Pages/Jobs/Show.tsx` | Add Competitive Intelligence Card section in ReportCard component; remove CC from Discovery section | Primary deliverable |
| `scrapegrape/frontend/src/components/report/ReadinessBadge.tsx` | Create new component | Google News readiness level display (UI-03) |
| `scrapegrape/frontend/src/components/report/ConfidenceBadge.tsx` | Create new component | Update frequency confidence indicator (UI-04) |

**Optional but recommended:**
| File | Change | Why |
|------|--------|-----|
| `scrapegrape/frontend/src/Pages/Publishers/Detail.tsx` | Add Competitive Intelligence section using publisher flat fields | Parity between job report card and publisher detail page |

## Existing Icons Available

From lucide-react (already imported or available):
- `Globe` - suitable for Common Crawl (web/internet connotation)
- `Newspaper` - suitable for Google News readiness (needs import)
- `Clock` or `Timer` - suitable for update frequency
- `CircleCheck` / `CircleX` - for signal breakdown check/cross
- `TrendingUp` or `Activity` - alternative for frequency

## State of the Art

N/A -- this phase involves no new technology choices. It is pure UI composition using existing patterns.

## Open Questions

1. **Should the Competitive Intelligence section be collapsible?**
   - What we know: Discovery and ToS sections are collapsible; Status Overview and Article Analysis are not.
   - What's unclear: Whether CI section should default open or be collapsible.
   - Recommendation: Start with it NOT collapsible (always visible), matching Article Analysis. All three sub-sections are compact enough to display without overwhelming. Can add collapsible later if needed.

2. **Should the Publisher Detail page also get a Competitive Intelligence section?**
   - What we know: The serializer already exposes `cc_in_index`, `cc_page_count`, `cc_last_crawl`, `has_news_sitemap`, `google_news_readiness`, `update_frequency`, `update_frequency_hours`, `update_frequency_confidence` via `PublisherListSerializer`. But Detail.tsx does not display any of these fields.
   - What's unclear: Whether Phase 18 scope includes the publisher detail page.
   - Recommendation: Include it as an optional sub-task. The data is already there; displaying it requires minimal effort and provides consistency.

3. **Should the step card divider text be changed?**
   - What we know: Step cards (during pipeline execution) currently split at index 12 with "Article Analysis" heading. The competitive intelligence steps (cc, sitemap_analysis, frequency) are in the publisher-level group (indices 9-11). Google News is in the article group (index 15).
   - What's unclear: Whether to add a "Competitive Intelligence" heading in the step cards too.
   - Recommendation: Leave step cards as-is. The step card view is a pipeline progress tracker, not a report card. The "Competitive Intelligence" label belongs in the report card only.

## Sources

### Primary (HIGH confidence)
- Direct code reading: `Show.tsx` (full file, 1052 lines) -- ReportCard component, StepCard, stepDataSummary, PIPELINE_STEPS, JobProps interface
- Direct code reading: `Detail.tsx` (full file, 366 lines) -- PublisherData interface, existing report card patterns
- Direct code reading: `steps.py` lines 423-483 (CC step return shape), 530-596 (sitemap analysis), 658-745 (frequency), 1414-1467 (Google News)
- Direct code reading: `views.py` lines 176-236 (job_show view, props dict)
- Direct code reading: `serializers.py` (full file, 21 lines) -- publisher flat fields already exposed
- Direct code reading: `models.py` lines 29-43 -- publisher competitive intelligence fields
- Direct code reading: Report components: `StatusIndicator.tsx`, `FormatBadge.tsx`, `PaywallBadge.tsx`, `badge.tsx`
- Phase 17 verification: `17-VERIFICATION.md` -- confirms all data flows correctly to frontend

### Secondary (MEDIUM confidence)
- Phase 11 research: `11-RESEARCH.md` -- original report card architecture patterns
- Phase 17 research: `17-RESEARCH.md` -- data flow integration details

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, purely existing code
- Architecture: HIGH -- all patterns verified by reading current Show.tsx and report components
- Data shapes: HIGH -- all three result shapes verified from step functions in steps.py
- Pitfalls: HIGH -- identified from direct reading of current UI code and data shapes

**Research date:** 2026-02-18
**Valid until:** 2026-03-18 (stable -- internal UI, no external dependencies)
