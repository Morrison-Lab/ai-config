# Implementation Plan: Pre-Push AI Code Review Integration

## Phase 1: Test Suite & Core CLI Hardening (TDD)
- [x] Task: Create Unit Test Suite for `pre-push-review.py` (Red Phase)
    - [x] Create `scripts/test_pre_push_review.py` with mock subprocess fixtures
    - [x] Add test cases for diff calculation and base branch resolution
    - [x] Add test cases for engine auto-detection (`agy` -> `claude` -> `codex`)
    - [x] Add test cases verifying PR comment formatting adheres to `AGENTS.md` disclosure rules (no robot emoji)
    - [x] Run test suite and confirm expected failures
- [x] Task: Implement Engine Detection, Fallback & Disclosure in `scripts/pre-push-review.py` (Green Phase)
    - [x] Implement auto-detection and fallback priority in `scripts/pre-push-review.py`
    - [x] Update GitHub PR comment formatting to match lab disclosure standard
    - [x] Support `--engine auto` and `--model` override flags
    - [x] Run test suite and confirm all tests pass
- [x] Task: Phase Verification & Checkpoint (Refer to workflow.md)

## Phase 2: Skill Documentation & Multi-Harness Sync
- [x] Task: Refine Canonical Skill Definition
    - [x] Update `skills/pre-push-review/SKILL.md` with complete usage flags, examples, and descriptions
- [x] Task: Generate Codex Wrappers & Sync Manifests
    - [x] Run `python3 scripts/sync-codex-skill-wrappers.py` to generate `codex-skills/pre-push-review/`
    - [x] Update `.agents/skills.json` to register the new skill
- [x] Task: Phase Verification & Checkpoint (Refer to workflow.md)

## Phase 3: Repository-Wide Verification & Quality Gates
- [x] Task: Execute Repository Validation Suites
    - [x] Run `python3 scripts/validate-skills.py`
    - [x] Run `python3 scripts/check-links.py`
    - [x] Run `python3 scripts/test_pre_push_review.py`
- [x] Task: Phase Verification & Checkpoint (Refer to workflow.md)
