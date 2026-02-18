# Phase 13: Data Foundation - Research

**Researched:** 2026-02-17
**Domain:** Django model fields, migrations, and data architecture for competitive intelligence
**Confidence:** HIGH

## Summary

Phase 13 adds model fields to the existing Publisher and ResolutionJob models so that downstream phases (14-18) have storage ready before they produce data. This is a purely structural phase: add fields, generate a migration, verify it applies cleanly. No new dependencies, no new pipeline steps, no UI changes.

The existing codebase has a well-established pattern for this exact operation. Publisher uses flat fields (BooleanField, CharField, JSONField) for publisher-level data, while ResolutionJob uses nullable JSONFields for per-run step results. Phase 13 follows this pattern exactly: add flat fields to Publisher for CC presence, news sitemap presence, Google News readiness level, and update frequency; add four JSONFields to ResolutionJob for step results.

The migration pattern is also well-established. Migrations 0002 through 0007 all add nullable or default-valued fields to Publisher and ResolutionJob. The new migration (0008) will follow the same pattern: `AddField` operations with `null=True` or `default` values, ensuring existing rows are unaffected.

**Primary recommendation:** Add exactly the fields specified in the success criteria, following the existing nullable/default patterns from prior migrations. Generate one migration. Test it applies and rolls back cleanly. No new libraries needed.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 5.2.4 | ORM, migrations | Already in use; models.py and makemigrations are the only tools needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-django | 4.11.1 | Migration and model tests | Verify fields exist with correct defaults |
| factory-boy | 3.3.3 | Test data factories | Update PublisherFactory/ResolutionJobFactory if needed |

### Alternatives Considered
None. This phase uses only Django's built-in model and migration system. No external libraries are involved.

**Installation:**
```bash
# No new packages needed
```

## Architecture Patterns

### Existing Model Location
```
scrapegrape/
├── publishers/
│   ├── models.py              # Publisher, ResolutionJob, ArticleMetadata, WAFReport
│   ├── factories.py           # PublisherFactory, ResolutionJobFactory
│   ├── migrations/
│   │   ├── 0001_initial.py
│   │   ├── ...
│   │   ├── 0007_articlemetadata_and_article_result.py  # Latest
│   │   └── 0008_competitive_intelligence_fields.py     # NEW (this phase)
│   ├── serializers.py         # PublisherListSerializer (may need field additions)
│   ├── pipeline/
│   │   ├── supervisor.py      # TTL skip path copies result fields
│   │   └── steps.py           # Step functions (not changed this phase)
│   └── tests/
│       ├── test_models.py     # Model field default tests
│       └── test_pipeline.py   # Pipeline tests
```

### Pattern 1: Publisher Flat Fields (established pattern)
**What:** Publisher-level signals stored as flat fields with safe defaults
**When to use:** Data that summarizes a publisher's overall posture (one value per publisher)
**Example from existing code:**
```python
# Existing pattern in publishers/models.py
waf_detected = models.BooleanField(default=False)
robots_txt_found = models.BooleanField(null=True)
rsl_detected = models.BooleanField(null=True)
sitemap_urls = models.JSONField(default=list, blank=True)
has_paywall = models.BooleanField(null=True)
```

### Pattern 2: ResolutionJob JSONFields (established pattern)
**What:** Per-run step results stored as nullable JSONFields on the job
**When to use:** Every pipeline step saves its full result dict here
**Example from existing code:**
```python
# Existing pattern in publishers/models.py
waf_result = models.JSONField(null=True, blank=True)
tos_result = models.JSONField(null=True, blank=True)
robots_result = models.JSONField(null=True, blank=True)
sitemap_result = models.JSONField(null=True, blank=True)
rss_result = models.JSONField(null=True, blank=True)
rsl_result = models.JSONField(null=True, blank=True)
ai_bot_result = models.JSONField(null=True, blank=True)
metadata_result = models.JSONField(null=True, blank=True)
article_result = models.JSONField(null=True, blank=True)
```

### Pattern 3: Migration with Nullable Fields (established pattern)
**What:** AddField operations with null=True or default values
**When to use:** Every migration that adds fields to existing models
**Example from migration 0005:**
```python
# From 0005_ai_bot_blocking_fields.py pattern
migrations.AddField(
    model_name='publisher',
    name='ai_bot_blocks',
    field=models.JSONField(blank=True, null=True),
),
migrations.AddField(
    model_name='resolutionjob',
    name='ai_bot_result',
    field=models.JSONField(blank=True, null=True),
),
```

### Anti-Patterns to Avoid
- **Non-nullable fields without defaults:** Every new field MUST be either `null=True` or have a `default`. Existing rows have no data for these fields.
- **Overengineering field types:** Use the same simple types (BooleanField, CharField, JSONField) already established. No need for custom field types, validators, or Pydantic models at this stage.
- **Adding fields that duplicate existing data:** The existing `sitemap_result` JSONField already stores sitemap discovery data. The new `sitemap_analysis_result` is for the Phase 15 *analysis* of those sitemaps (news namespace detection), not a duplicate.

## Specific Fields to Add

### Publisher Model - New Flat Fields

Based on the success criteria and downstream phase requirements:

| Field | Type | Default | Purpose | Consumed By |
|-------|------|---------|---------|-------------|
| `cc_in_index` | `BooleanField(null=True)` | null | Whether domain appears in Common Crawl | Phase 14, Phase 18 UI |
| `cc_page_count` | `IntegerField(null=True, blank=True)` | null | Estimated pages in Common Crawl index | Phase 14, Phase 18 UI |
| `cc_last_crawl` | `CharField(max_length=20, blank=True, default="")` | "" | Latest CC crawl identifier (e.g., "CC-MAIN-2026-05") | Phase 14, Phase 18 UI |
| `has_news_sitemap` | `BooleanField(null=True)` | null | Whether publisher has xmlns:news sitemap | Phase 15, Phase 16 |
| `google_news_readiness` | `CharField(max_length=20, blank=True, default="")` | "" | Readiness level: strong/moderate/minimal/none | Phase 16, Phase 18 UI |
| `update_frequency` | `CharField(max_length=50, blank=True, default="")` | "" | Human-readable frequency (e.g., "~3 articles/day") | Phase 15, Phase 18 UI |
| `update_frequency_hours` | `FloatField(null=True, blank=True)` | null | Numeric frequency in hours between posts | Phase 15, Phase 18 UI |
| `update_frequency_confidence` | `CharField(max_length=10, blank=True, default="")` | "" | Confidence: high/medium/low | Phase 15, Phase 18 UI |

**Design rationale:**
- `cc_in_index` as BooleanField(null=True) follows the `robots_txt_found` / `rsl_detected` / `has_paywall` pattern (null = not yet checked, True/False = checked).
- `cc_page_count` as IntegerField because it is a numeric value, not a string. Null means not checked or CC API unavailable.
- `cc_last_crawl` as CharField because CC crawl IDs are short strings like "CC-MAIN-2026-05".
- `has_news_sitemap` as BooleanField(null=True) follows the existing boolean signal pattern.
- `google_news_readiness` as CharField with choices follows the readiness level design decision (strong/moderate/minimal/none).
- `update_frequency` as CharField stores the human-readable string. `update_frequency_hours` stores the numeric value for potential sorting/filtering. `update_frequency_confidence` stores the confidence level.

### ResolutionJob Model - New JSONFields

| Field | Type | Purpose | Populated By |
|-------|------|---------|-------------|
| `cc_result` | `JSONField(null=True, blank=True)` | Common Crawl CDX API query results | Phase 14 step |
| `sitemap_analysis_result` | `JSONField(null=True, blank=True)` | News sitemap namespace analysis | Phase 15 step |
| `frequency_result` | `JSONField(null=True, blank=True)` | RSS/sitemap date frequency analysis | Phase 15 step |
| `news_signals_result` | `JSONField(null=True, blank=True)` | Google News readiness aggregation | Phase 16 step |

These follow the exact same `JSONField(null=True, blank=True)` pattern as every other result field.

## Downstream Impact Analysis

### Files That Reference Result Fields (will need updates in Phase 17, not Phase 13)

These files enumerate result fields explicitly and will need updating when pipeline integration happens in Phase 17. Phase 13 only adds the model fields and migration.

1. **`supervisor.py` TTL skip path** (lines 101-133): Copies result fields from prior jobs. New fields must be added to the `values()` call and copy logic.
2. **`views.py` job_show** (lines 186-230): Falls back to prior job results when fields are null. New fields must be added to `result_fields` list and props dict.
3. **`views.py` publisher_detail** (line 263): References result fields.
4. **`serializers.py`**: `PublisherListSerializer` fields tuple. New Publisher flat fields may need adding for API consumers.

**Important:** These changes belong in Phase 17 (Pipeline Integration), not Phase 13. Phase 13 only adds fields and migration.

### Test Impact

The existing `test_models.py` tests default values for Publisher and ResolutionJob fields. New tests should verify:
- New Publisher fields have correct defaults (null or empty string)
- New ResolutionJob JSONFields default to null
- Migration applies cleanly (`migrate` and `migrate publishers 0007` rollback)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Migration file | Manual migration Python file | `uv run python manage.py makemigrations publishers` | Django's auto-generated migrations handle field ordering, dependencies, and index names correctly |
| Field validation | Custom validators on JSONFields | Leave validation to the pipeline steps (Phases 14-16) | JSONField content schema is defined by the producing step, not the model layer |

**Key insight:** This phase is intentionally minimal. The value is in getting field names and types right so downstream phases can populate them without model changes. Resist the urge to add schema validation, custom methods, or admin integration at this stage.

## Common Pitfalls

### Pitfall 1: Migration Conflict with Concurrent Development
**What goes wrong:** If another branch adds migration 0008, this migration will conflict.
**Why it happens:** Django migration numbering is sequential per app.
**How to avoid:** Run `makemigrations` on the latest main branch. Check that `0007` is the latest migration before generating `0008`.
**Warning signs:** `CommandError: Conflicting migrations detected`.

### Pitfall 2: Forgetting to Update the TTL Skip Path
**What goes wrong:** New result fields are null on cached jobs, breaking the UI.
**Why it happens:** The TTL skip path in `supervisor.py` explicitly lists which fields to copy. New fields are silently omitted.
**How to avoid:** This is Phase 17's responsibility. Phase 13 should document this dependency clearly so Phase 17 doesn't miss it.
**Warning signs:** New report card sections show "Not checked" even for recently analyzed publishers.

### Pitfall 3: Choosing Wrong Field Types for Publisher
**What goes wrong:** Using JSONField where a flat field would be better, or vice versa.
**Why it happens:** Temptation to stuff everything into JSON "for flexibility."
**How to avoid:** Follow the established pattern: flat fields (BooleanField, CharField, IntegerField, FloatField) for publisher-level summary data that might be queried/filtered. JSONField only for complex nested data.
**Warning signs:** Queries needing JSON path lookups for simple boolean checks.

### Pitfall 4: Adding Too Many Fields
**What goes wrong:** Adding fields for data that downstream phases don't actually need.
**Why it happens:** Speculative design without checking what Phases 14-18 actually produce.
**How to avoid:** Only add fields explicitly required by the success criteria and downstream phase descriptions. The fields listed in this research are derived directly from the roadmap requirements.
**Warning signs:** Fields that remain null after all phases are implemented.

## Code Examples

### New Publisher Fields (to add to models.py)
```python
# Competitive intelligence flat fields (Phase 13: Data Foundation)
# CC presence (populated by Phase 14)
cc_in_index = models.BooleanField(null=True)
cc_page_count = models.IntegerField(null=True, blank=True)
cc_last_crawl = models.CharField(max_length=20, blank=True, default="")

# News sitemap (populated by Phase 15)
has_news_sitemap = models.BooleanField(null=True)

# Google News readiness (populated by Phase 16)
google_news_readiness = models.CharField(max_length=20, blank=True, default="")

# Update frequency (populated by Phase 15)
update_frequency = models.CharField(max_length=50, blank=True, default="")
update_frequency_hours = models.FloatField(null=True, blank=True)
update_frequency_confidence = models.CharField(max_length=10, blank=True, default="")
```

### New ResolutionJob Fields (to add to models.py)
```python
# Competitive intelligence step results (Phase 13: Data Foundation)
cc_result = models.JSONField(null=True, blank=True)
sitemap_analysis_result = models.JSONField(null=True, blank=True)
frequency_result = models.JSONField(null=True, blank=True)
news_signals_result = models.JSONField(null=True, blank=True)
```

### Migration Generation
```bash
cd /Users/matt/src/itsascout
uv run scrapegrape/manage.py makemigrations publishers --name competitive_intelligence_fields
uv run scrapegrape/manage.py migrate
```

### Migration Rollback Test
```bash
# Verify rollback works
uv run scrapegrape/manage.py migrate publishers 0007
# Re-apply
uv run scrapegrape/manage.py migrate publishers
```

### Updated Default Value Tests
```python
# In test_models.py
def test_publisher_competitive_intelligence_defaults(self, publisher):
    """New Phase 13 fields have safe defaults."""
    assert publisher.cc_in_index is None
    assert publisher.cc_page_count is None
    assert publisher.cc_last_crawl == ""
    assert publisher.has_news_sitemap is None
    assert publisher.google_news_readiness == ""
    assert publisher.update_frequency == ""
    assert publisher.update_frequency_hours is None
    assert publisher.update_frequency_confidence == ""

def test_job_competitive_intelligence_results_null(self, resolution_job):
    """New Phase 13 result fields default to null."""
    assert resolution_job.cc_result is None
    assert resolution_job.sitemap_analysis_result is None
    assert resolution_job.frequency_result is None
    assert resolution_job.news_signals_result is None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Add fields in pipeline step phases | Add all fields in a dedicated data foundation phase first | v2.1 Phase 13 | Clean separation: schema changes in one phase, logic in subsequent phases |

**Deprecated/outdated:**
- Nothing deprecated. This phase extends the existing model pattern established in Phase 6.

## Open Questions

1. **Exact CC page count field type**
   - What we know: CC CDX API returns page counts that could be large numbers. IntegerField supports up to 2,147,483,647 which should be sufficient for any single domain's page count.
   - What's unclear: Whether BigIntegerField is needed for extremely large sites.
   - Recommendation: Use IntegerField. If a site has >2 billion pages in CC, that is an extraordinary edge case and can be handled later.

2. **Whether `update_frequency_hours` should be DecimalField instead of FloatField**
   - What we know: FloatField has floating-point precision issues. DecimalField is exact.
   - What's unclear: Whether precision matters for frequency estimation (already an approximation).
   - Recommendation: Use FloatField. Frequency estimates are inherently approximate ("~3 articles/day" = ~8 hours), so float precision is more than adequate.

## Sources

### Primary (HIGH confidence)
- `/Users/matt/src/itsascout/scrapegrape/publishers/models.py` - Current model definitions, established field patterns
- `/Users/matt/src/itsascout/scrapegrape/publishers/pipeline/supervisor.py` - TTL skip path, result field copy logic
- `/Users/matt/src/itsascout/scrapegrape/publishers/views.py` - Result field enumeration in views
- `/Users/matt/src/itsascout/scrapegrape/publishers/migrations/0007_articlemetadata_and_article_result.py` - Latest migration, established migration pattern
- `/Users/matt/src/itsascout/scrapegrape/publishers/tests/test_models.py` - Existing field default tests
- `/Users/matt/src/itsascout/.planning/ROADMAP.md` - Phase 13-18 descriptions and success criteria
- `/Users/matt/src/itsascout/.planning/REQUIREMENTS.md` - v2.1 requirements (CC-01 through UI-04)

### Secondary (MEDIUM confidence)
- Phase 6 research (`.planning/phases/06-infrastructure-models/06-RESEARCH.md`) - Established model patterns and migration strategy

### Tertiary (LOW confidence)
- None. All findings are from direct codebase inspection.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new libraries; Django ORM only
- Architecture: HIGH - Exact same pattern as six prior migrations in this app
- Field design: HIGH - Derived directly from roadmap requirements and downstream phase descriptions
- Pitfalls: HIGH - Based on analysis of actual codebase patterns (TTL skip path, view field lists)

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (30 days -- Django model patterns are stable)
