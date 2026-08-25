# Implementation Plan: Pre-Push AI Code Review Integration

## Phase 1: Test Suite & Core CLI Hardening (TDD)
- [ ] Task: Create Unit Test Suite for `pre-push-review.py` (Red Phase)
    - [ ] Create `scripts/test_pre_push_review.py` with mock subprocess fixtures
    - [ ] Add test cases for diff calculation and base branch resolution
    - [ ] Add test cases for engine auto-detection (`agy` -> `claude` -> `codex`)
    - [ ] Add test cases verifying PR comment formatting adheres to `AGENTS.md` disclosure rules (no robot emoji)
    - [ ] Run test suite and confirm expected failures
- [ ] Task: Implement Engine Detection, Fallback & Disclosure in `scripts/pre-push-review.py` (Green Phase)
    - [ ] Implement auto-detection and fallback priority in `scripts/pre-push-review.py`
    - [ ] Update GitHub PR comment formatting to match lab disclosure standard
    - [ ] Support `--engine auto` and `--model` override flags
    - [ ] Run test suite and confirm all tests pass
- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)

## Phase 2: Skill Documentation & Multi-Harness Sync
- [ ] Task: Refine Canonical Skill Definition
    - [ ] Update `skills/pre-push-review/SKILL.md` with complete usage flags, examples, and descriptions
- [ ] Task: Generate Codex Wrappers & Sync Manifests
    - [ ] Run `python3 scripts/sync-codex-skill-wrappers.py` to generate `codex-skills/pre-push-review/`
    - [ ] Update `.agents/skills.json` to register the new skill
- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)

## Phase 3: Repository-Wide Verification & Quality Gates
- [ ] Task: Execute Repository Validation Suites
    - [ ] Run `python3 scripts/validate-skills.py`
    - [ ] Run `python3 scripts/check-links.py`
    - [ ] Run `python3 scripts/test_pre_push_review.py`
- [ ] Task: Phase Verification & Checkpoint (Refer to workflow.md)
