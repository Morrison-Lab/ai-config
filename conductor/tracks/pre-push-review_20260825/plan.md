# Implementation Plan: Pre-Push AI Code Review Integration

## Phase 1: Test Suite & Core CLI Hardening (TDD)
- [x] Task: Create Unit Test Suite for `pre-push-review.py` (Red Phase) (Commit: 541f8ec7)
  - [x] Create `scripts/test_pre_push_review.py` with mock subprocess fixtures (Commit: 541f8ec7)
  - [x] Add test cases for diff calculation and base branch resolution (Commit: 541f8ec7)
  - [x] Add test cases for engine auto-detection (`agy` -> `claude` -> `codex`) (Commit: 541f8ec7)
  - [x] Add test cases verifying PR comment formatting adheres to `AGENTS.md` disclosure rules (no robot emoji) (Commit: 541f8ec7)
  - [x] Run test suite and confirm expected failures (Commit: 541f8ec7)
- [x] Task: Implement Engine Detection, Fallback & Disclosure in `scripts/pre-push-review.py` (Green Phase) (Commit: 541f8ec7)
  - [x] Implement auto-detection and fallback priority in `scripts/pre-push-review.py` (Commit: 541f8ec7)
  - [x] Update GitHub PR comment formatting to match lab disclosure standard (Commit: 541f8ec7)
  - [x] Support `--engine auto` and `--model` override flags (Commit: 541f8ec7)
  - [x] Run test suite and confirm all tests pass (Commit: 541f8ec7)
- [x] Task: Phase Verification & Checkpoint (Refer to workflow.md) (Commit: 541f8ec7)

## Phase 2: Skill Documentation & Multi-Harness Sync
- [x] Task: Refine Canonical Skill Definition (Commit: 541f8ec7)
  - [x] Update `skills/pre-push-review/SKILL.md` with complete usage flags, examples, and descriptions (Commit: 541f8ec7)
- [x] Task: Generate Codex Wrappers & Sync Manifests (Commit: 541f8ec7)
  - [x] Run `python3 scripts/sync-codex-skill-wrappers.py` to generate `codex-skills/pre-push-review/` (Commit: 541f8ec7)
  - [x] Update `.agents/skills.json` to register the new skill (Commit: 541f8ec7)
- [x] Task: Phase Verification & Checkpoint (Refer to workflow.md) (Commit: 541f8ec7)

## Phase 3: Repository-Wide Verification & Quality Gates
- [x] Task: Execute Repository Validation Suites (Commit: 541f8ec7)
  - [x] Run `python3 scripts/validate-skills.py` (Commit: 541f8ec7)
  - [x] Run `python3 scripts/check-links.py` (Commit: 541f8ec7)
  - [x] Run `python3 scripts/test_pre_push_review.py` (Commit: 541f8ec7)
- [x] Task: Phase Verification & Checkpoint (Refer to workflow.md) (Commit: 541f8ec7)
