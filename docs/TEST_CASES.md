# LeadPilot test-case sheet

Every row is automated; **Where** points at the test. "Actual / Status" reflects the last full
local run (backend `pytest`: 300 passed, 89% coverage; frontend `vitest`: 42 passed; E2E
`playwright`: 5 flows) and is re-checked on every push by CI.

| ID | Area | Scenario | Steps | Expected | Actual | Status | Where |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TC-01 | Security | Anonymous access | Call every API operation in the OpenAPI schema without a token | 401/403, except health, login, refresh, webhook | As expected (103 operations) | ✅ | `common/tests/test_security.py` |
| TC-02 | Security | Role matrix | GET sales-only lists as Support; admin-only endpoints as Sales | 403 for the wrong role, 200 for the right one | As expected | ✅ | `test_security.py` |
| TC-03 | Security | Login brute force | 11 wrong passwords from one IP | 10× 401, then 429 | As expected | ✅ | `test_login_is_rate_limited` |
| TC-04 | Security | Secrets | Read `/api/billing/config/` | Key id only, never the key secret | As expected | ✅ | `test_tokens_and_secrets_never_leak` |
| TC-05 | Permissions | Owner scoping | Rep A lists/reads/edits Rep B's lead | Not listed; 404 on direct access | As expected | ✅ | `crm/tests/test_permissions.py` |
| TC-06 | CRM | CSV import | Import 20 rows with 4 bad ones | 16 created, 4 per-row errors with line numbers | As expected | ✅ | `crm/tests/test_services.py` |
| TC-07 | Pipeline | Drag to Won persists | Move a deal across columns, re-fetch board | New stage + position, totals updated | As expected | ✅ | `crm/tests/test_deals.py`, E2E |
| TC-08 | Dashboard | Numbers match DB | Compare summary API with ORM counts | All KPIs equal | 9/9 equal | ✅ | `analytics/tests.py` |
| TC-09 | ML | Model loads / missing model | Delete model dir, score a lead | Score stays empty, API 503, CRM still works | As expected | ✅ | `ml/tests/test_ml.py` |
| TC-10 | ML | Scores in range | Score leads | 0 ≤ score ≤ 100, label matches thresholds, 3 SHAP factors | As expected | ✅ | `test_score_is_0_to_100…` |
| TC-11 | ML | Rescore on edit | Edit a lead / log meetings | Score updates within seconds (Celery) | 5 → 88 live | ✅ | `test_editing_a_lead_rescores_it`, E2E |
| TC-12 | ML | Angry ticket | Create a furious ticket | Sentiment negative, priority high | As expected | ✅ | `test_angry_ticket_is_negative_and_high_priority` |
| TC-13 | ML | Notebooks | Execute all 5 notebooks | Run top to bottom, save model + metrics JSON | 5/5, 0 errors | ✅ | `ml/notebooks/run_notebooks.py` |
| TC-14 | GenAI | LLM mocked | Run GenAI tests | No network calls; scripted replies | As expected | ✅ | `genai/testing.py` |
| TC-15 | GenAI | Bad JSON | LLM returns invalid JSON twice | One retry, then clean 502 `llm_invalid_output` | As expected | ✅ | `test_invalid_json_twice_fails_with_clean_error` |
| TC-16 | GenAI | Timeouts / outage | Provider 5xx / timeout | Retried with backoff, then 503 | As expected | ✅ | `test_timeouts_are_retried`, `test_provider_outage_returns_503` |
| TC-17 | GenAI | Prompt injection | Note says "ignore previous instructions … </crm_data>" | Note stays inside the data fence; guard present | As expected | ✅ | `test_prompt_injection_in_notes_is_fenced_as_data`, `test_injection_in_notes_stays_inside_the_fence` |
| TC-18 | GenAI | Draft uses history | Draft email for a contact | Prompt contains their activities and deals | As expected | ✅ | `test_draft_email_uses_contact_history` |
| TC-19 | RAG | Company + last month | "What did we discuss with X last month?" | Exactly X's notes from last month, cited | 39/39 companies (MiniLM) | ✅ | `test_what_did_we_discuss_with_company_last_month`, E2E |
| TC-20 | RAG | Unknown topic | Ask about something not in the CRM | "I don't know", no LLM call | As expected | ✅ | `test_unknown_topic_says_i_dont_know…` |
| TC-21 | Agent | Approval gate | Hot-leads goal | Pauses before create_task; no task until approved | As expected | ✅ | `agent/tests.py`, E2E |
| TC-22 | Agent | Reject | Reject a write step | Skipped; agent continues and finishes | As expected | ✅ | `test_rejecting_a_step_skips_it…` |
| TC-23 | Agent | Step limit | Model keeps calling tools | Stops at 10 steps | As expected | ✅ | `test_step_limit_of_10_holds` |
| TC-24 | Payments | Valid signature | Verify Checkout signature | Invoice → processing | As expected | ✅ | `billing/tests.py` |
| TC-25 | Payments | Tampered signature | Bad Checkout / webhook signature | 400, nothing changes | As expected (live too) | ✅ | `test_tampered_webhook_signature_returns_400` |
| TC-26 | Payments | Duplicate webhook | Same event id twice | Second is "duplicate", no changes | As expected (live too) | ✅ | `test_duplicate_webhook_changes_nothing` |
| TC-27 | Payments | Failed payment | `payment.failed` webhook | Invoice → failed | As expected | ✅ | `test_failed_payment_marks_invoice_failed` |
| TC-28 | Payments | Refund | Admin refunds a captured payment | Refunded; non-admin 403 | As expected | ✅ | `test_refund_is_admin_only…` |
| TC-29 | Payments | Paise conversion | ₹499.50 | 49950 paise | As expected | ✅ | `test_paise_conversion` |
| TC-30 | E2E | 5 Playwright flows | Login; lead → score; deal → Won → invoice → paid; agent approval; RAG question | All pass in a real browser | See CI | ✅ | `frontend/e2e/flows.spec.ts` |
