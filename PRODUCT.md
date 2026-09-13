# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Primary:** Indian retail investors and High Net-worth Individuals (HNIs / sNII & bNII) actively tracking and applying for Mainboard and SME Initial Public Offerings (IPOs).
- **Secondary:** Bot administrators and investment community coordinators managing subscriber access, alert schedules, and Telegram distribution channels.

## Product Purpose

IPO-Wise automates the tracking, evaluation, and application workflow for Indian IPOs. It eliminates manual checking of Grey Market Premium (GMP) and subscription demand by scraping real-time data, filtering for attractive investment opportunities (> 15% GMP by default), delivering structured alert cards directly to Telegram chats/channels with 1-tap broker bidding bridges, and providing a clean web management console.

Success means investors never miss a lucrative IPO opportunity, can assess risk/demand instantly without visiting multiple ad-heavy portals, and can trigger broker bidding or mute notifications in seconds.

## Positioning

Unlike cluttered, ad-heavy financial portals (e.g. Chittorgarh, InvestorGain web) or generic market alert bots, IPO-Wise is a distraction-free, privacy-preserving, high-density pipeline. It uniquely pairs official report scraping with automated lot/capital requirements (Retail 1 lot vs HNI ₹2L+ threshold), 1-tap direct broker deep-links (Zerodha, Groww, AngelOne, etc.), and interactive Telegram state tracking (Applied / Mute / Ignore per IPO).

## Operating Context

- **Environment:** Real-time Indian stock market hours (active bidding 10:00 AM – 5:00 PM IST; scheduled alert triggers at 10:00, 12:30, 15:30 IST).
- **Delivery Channels:** Telegram mobile & desktop app (instant rich-text message alerts with inline action buttons) and a local/cloud web management dashboard (`http://localhost:5050/` or reverse-proxied under `/ipo/`).
- **Data Upstream:** Live scraping of official InvestorGain v2 reporting endpoints (Report 331 for GMP, Report 333 for Live Subscription Demand).

## Capabilities and Constraints

- **Core Capabilities:**
  - Automated scraping of Mainboard and SME IPO status, price band, lot size, GMP value/percentage, and subscription multipliers (Overall, Retail, sNII, bNII, QIB).
  - Telegram alert dispatching with inline interactive actions (`Applied`, `Ignore`, `Unmute`).
  - 1-tap broker bidding bridges for rapid order placement.
  - Web console for master toggle, GMP threshold adjustment (0–60%), schedule configuration, manual "Check Now" triggers, subscriber approval management, and live IPO table explorer.
- **Constraints & Rules:**
  - Production deployment on Google Cloud VM (systemd / PM2 / Nginx reverse proxy at `/ipo/`).
  - Production database (`ipo_bot.db`) stores live subscriber registrations, approvals, and mute lists; it must never be overwritten during updates.
  - Zero clutter, high-density financial data formatting (exact ₹ amounts, lot counts, and dates; no fabricated claims or marketing fluff).

## Brand Commitments

- **Name:** IPO-Wise (IPO Wise).
- **Voice & Tone:** Fast, concise, objective, financial-utility tone. High signal-to-noise ratio, zero clickbait, precise figures.
- **Visual Identity:** Sleek dark-mode aesthetic with functional data density, high-contrast badges for GMP / categories (Mainboard vs SME), and clear interactive affordances.

## Evidence on Hand

- Live code repository in `ipo-alert-bot/` with complete scraping pipeline (`scraper/`), Telegram bot engine (`bot/`), SQLite data layer (`database.py`), and web interface (`web/templates/`, `web/static/`).
- Actual scraper targets: InvestorGain v2 cloud report read endpoints.
- Pre-configured deployment files (`deploy/`, `ecosystem.config.js`, `AGENTS.md`).

## Product Principles

1. **Signal Over Noise:** Only alert when actionable criteria (e.g., GMP > threshold and open window) are satisfied. Respect investor attention.
2. **Actionable Precision:** Always supply exact numbers—share count, lot price, total minimum investment, and HNI lot cutoff—so decisions can be made without mental math.
3. **One-Tap Execution:** Minimize friction between receiving an alert and executing the bid across preferred brokerage platforms.
4. **Resilient & Low-Overhead:** Self-contained, lightweight Python/SQLite service with persistent state and graceful fallbacks.
