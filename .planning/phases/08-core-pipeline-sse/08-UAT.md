---
status: testing
phase: 08-core-pipeline-sse
source: [08-01-SUMMARY.md, 08-02-SUMMARY.md, 08-03-SUMMARY.md]
started: 2026-02-14T16:00:00Z
updated: 2026-02-14T16:00:00Z
---

## Current Test

number: 1
name: Homepage URL Input Form
expected: |
  Visit the homepage (/). A URL input form with an "Analyze" button appears above the existing publisher table. The form has placeholder text "https://example.com/article".
awaiting: user response

## Tests

### 1. Homepage URL Input Form
expected: Visit the homepage (/). A URL input form with an "Analyze" button appears above the existing publisher table. The form has placeholder text "https://example.com/article".
result: [pending]

### 2. URL Submission Creates Job and Redirects
expected: Paste a URL (e.g., https://www.nytimes.com/2024/01/01/technology/ai-news.html) into the form and click Analyze. You are redirected to a job page at /jobs/<uuid> showing the submitted URL, publisher name, and a status badge.
result: [pending]

### 3. Job Page Step Cards
expected: On the job page, you see 4 step cards stacked vertically: Publisher Resolution, WAF Detection, ToS Discovery, ToS Evaluation. Each starts as gray/pending.
result: [pending]

### 4. Real-Time SSE Progress
expected: While the pipeline runs, step cards update in real time -- turning blue with a pulse animation when started, then green when completed. A green "Connected" dot appears while streaming.
result: [pending]

### 5. Pipeline Completion
expected: After all steps complete, the page reloads automatically with final results. Status badge shows "completed". Step cards show results (e.g., "Detected: Cloudflare" for WAF, or "No WAF detected").
result: [pending]

### 6. Completed Job Page (Direct Visit)
expected: Visit the same /jobs/<uuid> URL directly (e.g., copy-paste or refresh). The page renders immediately with all completed step results from server data -- no SSE connection needed, no loading spinners.
result: [pending]

### 7. Duplicate URL Redirect
expected: Submit the same URL again from the homepage. Instead of creating a new job, you are redirected to the existing completed job page.
result: [pending]

### 8. Publisher Table Unchanged
expected: The existing publisher table below the URL input still works -- shows publisher list, search works, create/edit/bulk upload actions still function.
result: [pending]

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0

## Gaps

[none yet]
