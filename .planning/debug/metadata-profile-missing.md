---
status: diagnosed
trigger: "Report card for completed jobs should display metadata profile table showing field-level presence but currently does not"
created: 2026-02-17T00:00:00Z
updated: 2026-02-17T00:00:00Z
symptoms_prefilled: true
goal: find_root_cause_only
---

## Current Focus

hypothesis: CONFIRMED - field-level presence data exists in article_result but UI only renders a text summary, not a field-by-field table
test: compared data structure from pipeline vs what ReportCard renders
expecting: mismatch between available data and rendered UI
next_action: return diagnosis

## Symptoms

expected: Report card shows metadata profile table with field-level presence (headline, byline, published date, author, etc.)
actual: No metadata profile table displayed - only a text summary paragraph from the LLM profile agent
errors: none reported
reproduction: Complete a resolution job and view the report card
started: Phase 11 report card UI implementation

## Eliminated

## Evidence

- timestamp: 2026-02-17
  checked: pipeline/steps.py run_article_extraction_step (line 835-894)
  found: extraction produces per-format field dicts - jsonld_fields, opengraph_fields, microdata_fields, twitter_cards - each containing actual field names and values (headline, author, datePublished, etc.)
  implication: field-level presence data IS available in article_result

- timestamp: 2026-02-17
  checked: pipeline/steps.py run_metadata_profile_step (line 1051-1060)
  found: LLM profile agent only returns {summary: str, quality_score: float} - no structured field-level presence data
  implication: the profile sub-object is just a text summary, not a field breakdown table

- timestamp: 2026-02-17
  checked: pipeline/supervisor.py (line 260-264)
  found: article_result = {**extraction_result, "paywall": paywall_result, "profile": profile_result} so article_result contains jsonld_fields, opengraph_fields, microdata_fields, twitter_cards as top-level keys alongside paywall and profile
  implication: all per-format field dicts are available in article_result on the job

- timestamp: 2026-02-17
  checked: views.py job_show (line 175-206)
  found: article_result is passed directly to frontend as-is (no filtering)
  implication: all field data reaches the frontend

- timestamp: 2026-02-17
  checked: Show.tsx ReportCard (line 613-629)
  found: Metadata Profile section only renders profile.summary as a <p> text and profile.quality_score as a badge. No table of individual fields.
  implication: UI has no code to render field-level presence table

- timestamp: 2026-02-17
  checked: Show.tsx ReportCard (line 314-317)
  found: ar (article_result) is destructured to get formatsFound, paywall, and profile. The per-format field dicts (jsonld_fields, opengraph_fields, etc.) are available via ar but never rendered in the report card.
  implication: data is right there, just not displayed

## Resolution

root_cause: The report card UI renders only the LLM-generated text summary (profile.summary) and quality score for the Metadata Profile section. It does NOT render a field-level presence table showing which individual metadata fields (headline, author, datePublished, byline, image, etc.) are present/absent. The per-format field data (jsonld_fields, opengraph_fields, microdata_fields, twitter_cards) IS already available in article_result and reaches the frontend, but the ReportCard component has no code to extract and display individual field presence from these dicts.
fix:
verification:
files_changed: []
