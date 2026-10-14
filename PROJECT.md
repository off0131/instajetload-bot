# Project: instajetload_bot

## Architecture
- **Framework & Runtime**: Python 3.12, aiogram 3.14+ (asynchronous Telegram bot framework), aiohttp (health check & keep-alive web server on `$PORT`).
- **Media Extraction Layer (`downloader.py`)**:
  - Multi-tier YouTube Engine: Tier 1 (Optimized native yt-dlp with Node.js runtime and visitor cookies) -> Tier 2 (Mobile DASH client spoofing) -> Tier 3 (External Loader.to/SaveNow unblocked REST API helper).
  - Spotify Engine: Unblocked Embed Next.js metadata resolution (`open.spotify.com/embed/{track|album}`) -> YouTube Music/SoundCloud matching with $\le 5\text{s}$ duration filter -> 320kbps MP3 encoding -> Mutagen ID3 tagging (title, artist, album, cover art) -> Sequential album delivery pipeline.
  - Scratch Cleanup: Atomic `try...finally` scratch directory management preventing disk leaks.
- **Persistence & Caching Layer (`database.py`)**:
  - SQLite database with `aiosqlite`.
  - Tables: `users`, `cached_media` (caching Telegram `file_id` for Instagram, YouTube, and Spotify), `downloads_log`.
- **Telegram Presentation Layer (`main.py`)**:
  - Long-polling dispatcher with drop_pending_updates.
  - Multi-resolution inline keyboard selectors for YouTube (1080p, 720p, 480p, 360p, MP3).
  - Pre-flight 50MB file size checks and adaptive downgrade/warning.
  - Concurrency limiter (`asyncio.Semaphore(2)`) to respect 512MB RAM constraints on Render.
- **Container Infrastructure (`Dockerfile`, `requirements.txt`)**:
  - `python:3.12-slim` with `ffmpeg`, `nodejs`, `ca-certificates`, `mutagen`, and all Python dependencies.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | YouTube Metadata Extraction | Extract title, duration, thumbnail, and available resolutions | M1 | Survey (R1) |
| 2 | YouTube Multi-Resolution MP4 | Download up to 720p/1080p MP4 with FFmpeg audio merging | M1 | Survey (R1) |
| 3 | YouTube MP3 Audio Extraction | Extract high-fidelity audio as playable MP3 with metadata | M1 | Survey (R1) |
| 4 | YouTube Shorts Support | Download shorts as video or audio seamlessly | M1 | Survey (R1) |
| 5 | Datacenter Anti-Bot Mitigation | Relaxed cookie matching (visitor tokens) & mobile client spoofing | M1 | Survey (R1, R3) |
| 6 | External Helper Fallback Engine | Asynchronous Loader.to/SaveNow REST client for 720p/1080p/MP3 | M1 | Survey (R3) |
| 7 | Multi-Provider Fallback Orchestration | State machine failing over Tier 1 -> Tier 2 -> Tier 3 on 429/bot block | M1 | Survey (R3) |
| 8 | Spotify Track Metadata Resolution | Zero-auth Next.js embed scraper (`__NEXT_DATA__`) for track info | M1 | Survey (R2) |
| 9 | Spotify Album Support | Extract complete tracklists from album URLs and process sequentially | M1 | Survey (R2) |
| 10 | Spotify 320kbps MP3 & ID3 Tagging | High-bitrate MP3 transcoding and Mutagen ID3 tagging with cover art | M1 | Survey (R2) |
| 11 | Spotify Audio Stream Matching | Unblocked Android client matching with $\le 5\text{s}$ duration threshold | M1 | Survey (R2) |
| 12 | Telegram UI & Quality Keyboards | Interactive quality selection keyboard for YouTube and audio | M2 | Survey (R1) |
| 13 | Multi-Platform Media Caching | Cache YouTube and Spotify `file_id` in `cached_media` table | M2 | Survey (R4) |
| 14 | Scratch Directory Leak Fix & GC | Fix task_dir cleanup on errors + startup/periodic `downloads/` GC | M2 | Survey (R4) |
| 15 | Render Container Hardening | Add mutagen to requirements, memory semaphore (2), 50MB guards | M2 | Survey (R4) |
| 16 | Comprehensive E2E Verification | Automated verification suite across Tiers 1-5 passing 100% | M3 | Survey (R1-R4) |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: Media Downloader Engine (`downloader.py`) | Multi-tier YouTube (yt-dlp, mobile client, Loader.to helper) + Spotify (embed scraper, 320k MP3, mutagen ID3) + atomic scratch cleanup | none | IN_PROGRESS |
| 2 | M2: Bot UI, Caching & Container Hardening | `main.py`, `database.py`, `Dockerfile`, `requirements.txt` (Telegram UI keyboards, caching, leak GC, RAM semaphore, 50MB guard) | M1 | PLANNED |
| 3 | M3: E2E Verification & Adversarial Hardening | `tests/` E2E test suite (Tiers 1-4), Tier 5 challenger hardening, forensic audit | M2 | PLANNED |

## Interface Contracts
### YouTube Downloader (`downloader.py` ↔ `main.py`)
- `extract_youtube_info(url: str) -> Optional[Dict[str, Any]]`:
  Returns: `{"title": str, "duration": int, "thumbnail": str, "video_id": str, "resolutions": List[int]}`
- `download_youtube(video_id_or_url: str, quality: str) -> Dict[str, Any]`:
  `quality`: `"1080"`, `"720"`, `"480"`, `"360"`, or `"audio"` / `"mp3"`.
  Returns: `{"file_path": str, "title": str, "duration": int, "thumbnail": Optional[str], "task_dir": str, "is_audio": bool, "tier_used": int}`

### Spotify Downloader (`downloader.py` ↔ `main.py`)
- `extract_spotify_info(url: str) -> Optional[Dict[str, Any]]`:
  Returns: `{"type": "track"|"album", "title": str, "artist": str, "cover_url": str, "tracks": Optional[List[Dict[str, Any]]]}`
- `download_spotify(url_or_track_dict: Union[str, Dict[str, Any]]) -> Dict[str, Any]`:
  Returns: `{"file_path": str, "title": str, "artist": str, "album": str, "duration": int, "cover_path": Optional[str], "task_dir": str, "bitrate": "320k"}`

### Database Caching (`database.py` ↔ `main.py`)
- `get_cached_media(shortcode_or_id: str, media_type: str) -> Optional[str]`
- `save_cached_media(shortcode_or_id: str, media_type: str, file_id: str) -> None`

## Code Layout
- Root: `/Users/reza/Documents/antigravity normal/instajetload_bot`
- Entry Point: `main.py`
- Downloader Core: `downloader.py`
- Database Layer: `database.py`
- Localization: `locales.py`
- Configuration: `.env`, `cookies.txt`
- Container: `Dockerfile`, `requirements.txt`
- Tests: `tests/` (E2E and unit test harnesses)
