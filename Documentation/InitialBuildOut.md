Below is a **developer-ready README** you can drop straight into the `leaky-buckets` repo. It is intentionally opinionated and scope-restrictive. This is a feature, not a bug.

---

# 🪣 Leaky-Buckets

**Leaky-Buckets** is a *shared, playful personal finance app* designed for **two people** who want **clarity without overwhelm**.

The goal is not perfect accounting.
The goal is a **10-minute monthly money check-in** that produces *real insight* and *calm conversations*.

If this starts to feel like QuickBooks, **we have failed**.

---

## 🎯 Core Design Principles (Non-Negotiable)

1. **10 minutes per month**

   * Upload statements
   * Review only exceptions
   * See bucket status
   * Done

2. **Playful, not punitive**

   * Buckets spill, leak, fill, or stay steady
   * No shaming, no red spreadsheets
   * Visual feedback > tables

3. **Manual inputs by design**

   * No live bank connections
   * Monthly CSV uploads only
   * Control > automation

4. **Shared visibility**

   * Built for exactly **two users**
   * Same dashboard, same truth
   * No “power user” mode

5. **Insights, not accounting**

   * We care about trends and behavior
   * Not GAAP, not reconciliation
   * No balance sheets, no journals

---

## 👥 Users & Auth

* Exactly **two household users**
* Auth via **AWS Cognito**

  * Email + password
  * No social logins
  * Cheap, simple, reliable
* No roles, no permissions hierarchy
* Either user can upload, review, and lock a month

---

## 🧠 Core Workflow (This Is the Product)

### Monthly Flow (Target: ≤10 minutes)

1. **Upload**

   * User uploads:

     * Bank CSV
     * Credit card CSV
   * Files stored raw (encrypted) in S3

2. **Normalize**

   * Backend normalizes all CSVs into a common transaction format
   * Raw files are preserved for audit/debug

3. **Categorize**

   * Rules first (merchant memory)
   * AI second (OpenAI API)
   * Confidence score attached to each transaction

4. **Review (Exceptions Only)**

   * User sees:

     * Uncategorized items
     * Low-confidence items
     * New merchants
   * One-click fixes
   * “Remember this merchant” option

5. **Lock Month**

   * Once locked:

     * Transactions are immutable
     * Buckets are finalized
     * Dashboard updates

6. **Bucket Dashboard**

   * Simple, visual bucket states:

     * 🟢 Stable
     * 🟡 Dripping
     * 🔴 Overflowing
   * No charts that require interpretation

---

## 🪣 Buckets (Keep It Human)

* Max **8–10 buckets**
* Examples:

  * Home & Utilities
  * Groceries
  * Dining / Coffee
  * Subscriptions
  * Health
  * Transport
  * Fun / Travel
  * One-Off / Big Hits

Buckets:

* Have monthly targets (optional)
* Are intentionally approximate
* Are discussion starters, not scorecards

---

## 🤖 AI Usage (OpenAI API)

AI is **assistive**, not authoritative.

### Used for:

* Categorizing unknown merchants
* Suggesting bucket placement
* Confidence scoring

### Not used for:

* Budget setting
* Forecasting
* Moral judgment
* Financial advice

### Requirements:

* AI calls must be **idempotent**
* Categorization must be explainable (store model output + reasoning snippet)
* Merchant memory overrides AI permanently

---

## ☁️ AWS Architecture (All Infrastructure Lives Here)

### Core Services

* **AWS Cognito** — Authentication
* **API Gateway** — Public API
* **AWS Lambda** — Business logic
* **DynamoDB** — Core data store
* **S3** — CSV uploads (raw + normalized)
* **CloudWatch** — Logs & metrics

### Data Stores (DynamoDB)

* `users`
* `transactions`
* `merchants`
* `buckets`
* `monthly_summaries`

### Storage (S3)

* `/uploads/raw/`
* `/uploads/normalized/`

---

## 🔐 Security & Encryption (Must Be Implemented)

This app stores sensitive financial behavior. Security is not optional.

### At Rest

* **S3**

  * Server-side encryption (SSE-S3 or SSE-KMS)
  * Private buckets only
* **DynamoDB**

  * Encryption at rest (default AWS-managed keys)

### In Transit

* HTTPS only
* TLS enforced via API Gateway

### Data Minimization

* Never store:

  * Full account numbers
  * Bank login credentials
* Strip account identifiers during normalization

### User Controls

* “Delete all data” button (hard delete)
* No soft-delete ambiguity

---

## 🚫 Explicit Non-Goals (Read This Twice)

The app must NOT:

* Connect directly to banks
* Track net worth
* Track investments
* Forecast future spending
* Optimize taxes
* Provide financial advice
* Support more than 2 users
* Grow into a “platform”

If a feature sounds impressive but adds friction, **do not build it**.

---

## 📐 Success Criteria

The app is successful if:

* A full monthly review takes **≤10 minutes**
* Both users understand spending patterns instantly
* Conversations feel calmer, not tense
* No one avoids opening the app

---

## 🧭 Development Guidance for AI / Agents

* Favor clarity over cleverness
* Prefer deletion over abstraction
* Every screen must answer: *“What do I do next?”*
* If a feature needs documentation, it’s probably too complex
* When in doubt: simplify

---

## 🪣 Philosophy (Why This Exists)

Money stress usually comes from **opacity**, not overspending.

Leaky-Buckets exists to:

* Make money visible
* Make tradeoffs obvious
* Make conversations easier

Not to make anyone feel bad.

---

**If you’re unsure whether to build something: don’t.
If you’re unsure whether it’s simple enough: simplify again.**