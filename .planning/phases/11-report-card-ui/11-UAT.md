---
status: diagnosed
phase: 11-report-card-ui
source: 11-01-SUMMARY.md, 11-02-SUMMARY.md
started: 2026-02-17T21:10:00Z
updated: 2026-02-17T21:18:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Report Card Layout for Completed Jobs
expected: Navigate to a completed job page. Instead of individual step cards, you should see a wider report card layout with a status overview grid at the top showing WAF, ToS, robots.txt, and other check results.
result: issue
reported: "metadata profile should have a table showing fields and presence categorized by headline and byline - things like that"
severity: major

### 2. ToS Permissions in Report Card
expected: In the completed job report card, a ToS section shows permission details — allowed/prohibited status and relevant ToS URL if found.
result: pass

### 3. Discovery Section (Robots, Sitemap, RSS, RSL)
expected: Report card shows a discovery section with robots.txt rules, sitemap URLs, RSS feed URLs, and RSL licensing status. Items with data show values; items not checked show "Not checked" placeholder.
result: pass

### 4. Article Analysis Section
expected: Report card shows article analysis with format badges (JSON-LD, OpenGraph, Microdata) indicating which formats were found, plus paywall status badge (free/paywalled/metered/unknown).
result: pass

### 5. Publisher Name Links to Detail Page
expected: The completed job report card header shows the publisher name as a clickable link that navigates to the publisher detail page.
result: pass

### 6. Running Job Still Shows Step Cards
expected: Submit a new URL or view a job that is still running/pending. You should see individual step cards with SSE streaming progress — NOT the report card view.
result: pass

### 7. Duplicate URL Redirects to Existing Job
expected: Submit the same URL that was already analyzed. Instead of creating a new job, you are redirected to the existing job's results page.
result: pass

## Summary

total: 7
passed: 6
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "Report card displays metadata profile with field-level presence table"
  status: failed
  reason: "User reported: metadata profile should have a table showing fields and presence categorized by headline and byline - things like that"
  severity: major
  test: 1
  root_cause: "ReportCard component in Show.tsx (lines 613-629) only renders profile.summary text. Per-format field dicts (jsonld_fields, opengraph_fields, microdata_fields, twitter_cards) are already in article_result and reach the frontend, but no table UI renders them."
  artifacts:
    - path: "scrapegrape/frontend/src/Pages/Jobs/Show.tsx"
      issue: "Lines 613-629 only render profile.summary, no field presence table"
    - path: "scrapegrape/publishers/pipeline/steps.py"
      issue: "KEY_FIELDS (line 734-738) and OG_FIELD_MAP (line 740-752) define canonical fields already"
  missing:
    - "Add field-presence table to ReportCard showing canonical fields (headline, author, datePublished, image, description, etc.) with checkmark/X columns per format (JSON-LD, OpenGraph, Microdata, Twitter)"
  debug_session: ".planning/debug/metadata-profile-missing.md"
