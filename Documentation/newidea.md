### Theme recommendation: **Treasure Chests** 🧰💰

You don’t “fill” them; you **draw from them**. Each category is a chest with coins. Spend money → coins disappear. Overspend → chest cracks / goes into debt.

It’s playful, instantly intuitive, and maps cleanly to your goal: **variable spending limits**.

Below is a complete **app spec markdown** you can hand to a developer agent.

---

# ChestCheck (Working Title) — PWA Spending Limits App

## 1) Product Summary

**ChestCheck** is a super-simple PWA for two people (Ron + Ralisa) to track variable spending by category. Each category is a **Treasure Chest** with a monthly coin limit. Users open the app, log a transaction (amount + category), and exit. That’s the core loop.

**Success metric:** daily usage friction low enough that logging a transaction takes **≤ 15 seconds** and monthly reconciliation takes **≤ 10 minutes**.

## 2) Core Goals

* Track **variable spending only** (behavior-driven purchases).
* Enforce clear monthly category limits.
* Provide a monthly summary: “how did we do?” + simple insights.
* Keep UX playful but not childish; intentional, not judgmental.
* Built as a **PWA** so it installs on iPhone home screen without App Store.
* Simple shared household view for two users.

## 3) Non-Goals (Hard Boundaries)

* No bank connections.
* No net worth tracking.
* No investments, debts, amortization charts.
* No forecasting.
* No complicated budgeting methods or accounting.
* No receipts, OCR, or itemization (v1).
* No AI categorization (v1). User picks category manually.

## 4) Theme & UI Metaphor

Each category is a **Treasure Chest**:

* Chest starts the month full of coins (the limit).
* Every transaction removes coins.
* As it empties: visual states change.
* If spending exceeds the limit: chest becomes **cracked** and coins go negative.

### Chest States

* **Full / Healthy**: >60% remaining
* **Low**: 20–60% remaining
* **Almost Empty**: 0–20% remaining
* **Cracked**: <0 remaining (overspent)

Use simple visuals (icons/emoji or minimal illustrations). No heavy animation required.

## 5) Primary User Flows

### 5.1 Daily Flow (Primary)

1. Open app (home screen PWA).
2. Tap **“Log Spend”**.
3. Enter:

   * Amount (required)
   * Category (required)
   * Optional note (merchant) — optional
4. Tap **Save**.
5. App returns to dashboard.

**Target time:** ≤15 seconds.

### 5.2 Monthly Setup Flow

* User sets monthly limits for each category (coins per chest).
* Limits persist month-to-month, editable anytime.
* Option: “Copy last month limits” (default behavior).

### 5.3 Month End Summary Flow

On the 1st of the month (or when user opens app next month), app shows:

* Previous month performance summary
* Top overspent categories
* Best category (most remaining)
* Total variable spending vs total limits
* Quick “rollover” action:

  * Start new month using same categories/limits

## 6) Data Model (Minimal)

### Entities

#### User

* userId (Cognito sub)
* email
* displayName (optional)

#### Household

* householdId
* members: userIds (exactly 2 in v1)

#### Category (Chest)

* categoryId
* householdId
* name (e.g., “Dining”, “Groceries”)
* monthlyLimitCents (int)
* isActive (bool)
* sortOrder (int)

#### Transaction

* transactionId
* householdId
* userId (who logged it)
* categoryId
* amountCents (int, positive numbers only)
* note (string, optional)
* createdAt (ISO timestamp)
* monthKey (e.g., “2026-02” derived from createdAt in household timezone)

#### MonthSummary (can be computed on read; optional cache)

* householdId
* monthKey
* totalsByCategory: {categoryId: spentCents}
* totalSpentCents
* generatedAt

## 7) Calculations

### Remaining per Category

remaining = monthlyLimitCents - sum(transactions.amountCents for that category in monthKey)

### Category State

* remaining / limit >= 0.60 → Healthy
* 0.20 to 0.60 → Low
* 0.00 to 0.20 → Almost Empty
* remaining < 0 → Cracked

### Monthly Summary Metrics

* totalLimit = sum(category.monthlyLimitCents for active categories)
* totalSpent = sum(all transactions in monthKey)
* percentUsed = totalSpent / totalLimit
* overspentCategories = categories where remaining < 0
* bestCategory = max remaining (or highest % remaining)

## 8) Screens (Keep It Very Few)

### Screen A — Dashboard (Default)

Shows current month:

* A grid/list of chests (categories)

  * Name
  * Remaining dollars
  * Simple visual state
* One prominent button: **Log Spend**
* A small “This Month” total line:

  * Total spent
  * Total remaining across all chests

Tap a chest → Category detail list (optional minimal).

### Screen B — Log Spend (2 inputs + save)

* Amount (numeric keypad)
* Category picker (list)
* Note (optional)
* Save

After save:

* Toast: “Logged ✓”
* Return to Dashboard

### Screen C — Month Summary

* Month selector (default last month)
* Total spent vs total limit
* List of categories with:

  * Limit
  * Spent
  * Remaining
  * State
* “Start New Month” button (if viewing a past month at rollover time)

### Screen D — Settings (Lightweight)

* Manage categories (add/edit/archive)
* Set monthly limits
* Household members view (2 users)
* Data export (CSV) (optional but recommended)
* Delete all data (required)

## 9) PWA Requirements (iPhone)

* Serve over HTTPS
* `manifest.json` with:

  * name, short_name, icons (192, 512), display: standalone
* iOS meta tags:

  * `apple-mobile-web-app-capable`
  * `apple-touch-icon`
* Simple home screen install instructions in Settings screen

## 10) Tech Stack (AWS-first)

### Frontend

* Simple React + Vite or Next.js (either works)
* Hosted on S3 + CloudFront (recommended)
* Mobile-first UI

### Auth

* AWS Cognito User Pool
* Email/password
* Two-user household (invite by email or manual admin add for v1)

### Backend

* API Gateway + Lambda
* DynamoDB tables:

  * Categories
  * Transactions
  * Households (and membership)
* Optional: monthly summary cache table or compute on demand

## 11) Security & Encryption (Must-Have)

Even without bank connections, transaction logs are sensitive.

### At Rest

* S3: Server-side encryption enabled (SSE-S3 or SSE-KMS)
* DynamoDB: encryption at rest (AWS managed)
* Secrets: store in AWS Secrets Manager (OpenAI key, etc.)

### In Transit

* HTTPS only (CloudFront + API Gateway TLS)
* No plaintext secrets in frontend

### Least Privilege IAM

* Lambdas can only access required tables/buckets
* Cognito-authenticated access enforced on APIs

### Data Minimization

* Store cents + category + timestamp + optional note only
* No account numbers or bank identifiers (none collected)

### User Controls

* Delete all data (hard delete)
* Export transactions (CSV) for personal backup

## 12) API Endpoints (Minimal)

All require Cognito JWT.

* `GET /me` (user + household info)
* `GET /categories?monthKey=YYYY-MM`
* `POST /categories`
* `PUT /categories/{id}`
* `POST /transactions`
* `GET /transactions?monthKey=YYYY-MM` (optionally filtered by category)
* `GET /summary?monthKey=YYYY-MM`
* `POST /household/invite` (optional v1.1; can be manual)
* `POST /data/export` (optional)
* `DELETE /data` (delete all)

## 13) UX Rules to Preserve Simplicity

* Logging a transaction must not require scrolling.
* Default category picker order = most used categories on top.
* Amount field uses numeric keypad and supports quick entry ($12.34).
* No modal stacking.
* One primary action per screen.

## 14) Milestones

### MVP (v1)

* Auth + two-user household
* Categories + limits
* Log transaction
* Dashboard states
* Monthly summary
* Delete all data
* PWA installability

### v1.1 (Optional Enhancements)

* CSV export
* Category detail screen
* Lightweight streak: “Days logged” (optional)
* Reminder banner (non-push): “Haven’t logged today?”

## 15) Acceptance Criteria

* User can install PWA on iPhone and open full screen.
* User can log a transaction in ≤15 seconds.
* Dashboard updates instantly with new remaining amounts.
* Month summary is clear and requires no interpretation.
* System works with two users seamlessly.
* Data is encrypted at rest and in transit.

---

## Alternate theme options (if you want more choices)

* **Coin Pouches** (you draw coins out; pouch empties)
* **Cookie Jar** (you “take cookies out” 😄)
* **Fuel Tanks** (you burn fuel; gauge drops)
* **Ammo Magazines** (you use rounds; hits zero) *(might be too “tactical” for this use case)*
* **Piggy Banks** (you break into it; but it implies saving more than spending control)*

My vote stays: **Treasure Chests** — it’s neutral, visual, and couples-friendly.

