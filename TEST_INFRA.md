# E2E Test Infra: instajetload_bot

## Test Philosophy
- Opaque-box, requirement-driven. Derived from user acceptance criteria in `ORIGINAL_REQUEST.md`, independent of internal implementation code.
- Systematic 4-tier methodology: Category-Partition, Boundary Value Analysis, Pairwise Combinations, and Real-World Application Workloads.
- Standalone programmatic verification runnable in the container or local virtualenv via `pytest` or standalone Python runner.

## Feature Inventory & Test Matrix
| # | Feature | Source | Tier 1 (Coverage) | Tier 2 (Boundary) | Tier 3 (Cross) |
|---|---------|--------|:-----------------:|:-----------------:|:--------------:|
| F1 | YouTube Video Download (Multi-Res) | R1 | 5 | 5 | ✓ |
| F2 | YouTube Audio Extraction (MP3) | R1 | 5 | 5 | ✓ |
| F3 | YouTube Shorts Extraction | R1 | 5 | 5 | ✓ |
| F4 | YouTube Metadata Resolution | R1 | 5 | 5 | ✓ |
| F5 | Datacenter Anti-Bot Resilience | R1, R3 | 5 | 5 | ✓ |
| F6 | External Helper Fallback (Loader) | R3 | 5 | 5 | ✓ |
| F7 | Multi-Tier Failover Cascade | R3 | 5 | 5 | ✓ |
| F8 | Spotify Single Track Metadata | R2 | 5 | 5 | ✓ |
| F9 | Spotify Single Track Audio & ID3 | R2 | 5 | 5 | ✓ |
| F10 | Spotify Album Extraction & Loop | R2 | 5 | 5 | ✓ |
| F11 | Telegram 50MB File Limit Guard | R4 | 5 | 5 | ✓ |
| F12 | Scratch Cleanup & No Disk Leak | R4 | 5 | 5 | ✓ |
| F13 | Telegram Cache (cached_media) | R4 | 5 | 5 | ✓ |
| F14 | Render Web Server & Keepalive | R4 | 5 | 5 | ✓ |

## Test Architecture
- **Directory**: `instajetload_bot/tests/`
- **Runner**: `pytest tests/` or `python tests/run_e2e_tests.py`
- **Output**: JSON report + JUnit XML + console summary with exit code 0 on pass.
- **Tiers Structure**:
  - `tests/test_tier1_features.py`: Happy path verification of each feature in isolation (≥70 tests).
  - `tests/test_tier2_boundaries.py`: Edge cases, invalid inputs, network timeouts, huge durations, 0s shorts, empty cookies (≥70 tests).
  - `tests/test_tier3_combinations.py`: Cross-feature combinations (e.g. YouTube fallback -> Spotify matching, caching -> second hit, concurrent downloads under semaphore).
  - `tests/test_tier4_workloads.py`: Realistic end-user flows (e.g. user downloads album, user requests 1080p then cancels, cache hits across users).

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Full Spotify Album Download Workflow | F8, F9, F10, F12, F13 | High |
| 2 | High-Res YouTube Video Download & Cache Hit | F1, F4, F11, F13 | High |
| 3 | Simulated Datacenter 429 Bot Block Triggering Fallback | F1, F5, F6, F7 | Critical |
| 4 | Oversized Video Handling & Adaptive Warning | F1, F11, F12 | Medium |
| 5 | Concurrent Mixed Downloads under RAM Semaphore | F1, F2, F9, F12, F14 | High |

## Coverage Thresholds
- Tier 1: ≥70 test cases
- Tier 2: ≥70 test cases
- Tier 3: ≥14 test cases (pairwise)
- Tier 4: ≥5 realistic scenarios
- Total Test Suite Target: ≥160 test cases
