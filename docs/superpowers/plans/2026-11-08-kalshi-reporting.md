# Kalshi Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** View real Kalshi positions and scores in the existing Telegram bot and retain Pacific daily balance snapshots.

**Architecture:** Separate signed account client, contract/score reporting, and SQLite history. Add authorized Telegram handlers and a dedicated midnight snapshot command/timer without altering paper grading.

**Tech Stack:** Python, requests, cryptography RSA-PSS, SQLite, zoneinfo, python-telegram-bot, unittest.

**Spec:** docs/superpowers/specs/2026-11-08-kalshi-reporting-design.md

**Implementation status:** Account client, reports, history, commands, migration,
and generic unit templates are implemented. Independent review found an optional
event-lookup fallback bug, now fixed with a regression test. The 55-test full suite
passes with fixture HTTP responses. Server installation, live account/Telegram
checks, registry update, and first midnight observation remain activation tasks.

## Global Constraints
- GET-only account client; no orders or transfers.
- America/Los_Angeles throughout reports and cutoffs.
- Existing central env; credentials never in git or logs.
- Preserve paper scans, grading, authorization, and existing token routing.
- No server activation, merge or restart without separate approval.

## Review Focus
- NO sides and fractional quantities must not be inverted or rounded to integers.
- Integer strikes, ambiguous teams and unsupported props must not produce false wins.
- UTC/Pacific day boundaries and DST must not misassign games or history dates.
- Late timer catchup must never masquerade as a midnight balance.
- HTTP errors, malformed JSON and partial pagination must not expose secrets or appear as empty portfolios.

## Task 1: Signed account reads
Files: create football_v2/kalshi_account.py, tests/test_kalshi_account.py; modify requirements.txt.
Interface: AccountClient.get_balance() -> dict; positions() -> list[dict]; market(ticker) -> dict; event(ticker) -> dict.
- [ ] Write tests for RSA signed GET, query-free signature, decimal positions, pagination, HTTP sanitization and missing credentials.
- [ ] Run unittest test file, confirm missing implementation failure.
- [ ] Implement restricted endpoints, finite decimal parsing, bounded requests and lazy cryptography loading.
- [ ] Run tests and full baseline suite, commit.

## Task 2: Position and score reports
Files: create football_v2/kalshi_reports.py, tests/test_kalshi_reports.py.
Interface: build_account_report() -> str; build_scores_report() -> str; compare_score(view, game, now) -> str.
- [ ] Test YES/NO, total equality, supported scope, stale/missing scores, aliases, two-team/date matching, live-first order and Pacific formatting.
- [ ] Run tests RED; implement account report and cached Odds API score retrieval without changing parse_result.
- [ ] Test partial market lookup failures preserve other positions and unmatched contracts retain source titles.
- [ ] Run tests and suite; commit.

## Task 3: Daily history and Telegram integration
Files: create football_v2/kalshi_history.py, kalshi_snapshot.py, deploy/kalshi-daily-snapshot.service.in, deploy/kalshi-daily-snapshot.timer; modify football_telegram.py; add tests/test_kalshi_history.py and tests/test_kalshi_telegram.py.
Interface: record_snapshot(path, balance, observed_at, cutoff) -> bool; build_history(path) -> str.
- [ ] Test Pacific cutoff, missing days, duplicate-run idempotence, late/missing timer, raw change label, authorization and Telegram chunking.
- [ ] Run tests RED; implement SQLite transaction, UTC storage/Pacific display and timer cutoff validation.
- [ ] Add three authorized async commands with sanitized failures and chunked messages.
- [ ] Run tests/full suite and commit.

## Task 4: Installation preparation and review
Files: create docs/kalshi-reporting.md and scripts/configure_kalshi.py.
- [ ] Add central-env migration with private backup, absent-key-only edits and no secret output; test conflicts do not overwrite.
- [ ] Document backup, dependency install, on-demand smoke tests, timer activation, registry fragment and rollback.
- [ ] Verify full suite, git diff checks and inspect secrets; review changes independently of implementation pass.
- [ ] Push feature branch/create reviewable PR; report limitations and exact approval-dependent server activation steps.
