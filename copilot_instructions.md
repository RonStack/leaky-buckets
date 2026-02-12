# ChestCheck — Copilot Instructions

## Deployment Rules

Deployments should always go through GitHub Actions, CloudFormation, and AWS CLI commands during the deployment process, not through a local terminal.

You have access to AWS CLI commands within this terminal, but should only use it for troubleshooting, not deploying resources.

The deploy workflow has **path filters** — empty commits won't trigger it. Use `gh workflow run deploy.yml` for manual redeploys, or `workflow_dispatch` from the Actions tab.

---

## Project Overview

**ChestCheck** is a treasure-chest-themed PWA for tracking variable spending. Each spending category is a "Treasure Chest" with a monthly coin limit. Users open the app, log a transaction (amount + category), and exit. The core loop targets ≤15 seconds.

**Live URL:** https://leakingbuckets.goronny.com
**Repo:** https://github.com/RonStack/leaky-buckets
**AWS Account:** 123525499627 (us-east-1)

---

## Architecture

### Frontend
- **React 18 + Vite 5** — mobile-first PWA
- **Hosted on S3 + CloudFront** (infra/frontend.yml)
- **Auth:** Cognito User Pool (infra/auth.yml), session-based tokens
- **PWA:** manifest.json, service worker, iOS meta tags
- **No router library** — simple state-based page switching in App.jsx
- Source: `frontend/src/`

### Backend
- **API Gateway REST + Lambda** (Python 3.12, arm64)
- **DynamoDB** for persistence (4 tables)
- **SAM template:** `infra/api.yml`
- **Only dependency:** boto3
- Source: `backend/handlers/`, `backend/lib/`

### CI/CD Pipeline
- **GitHub Actions:** `.github/workflows/deploy.yml`
- 6 sequential jobs: validate → foundation → auth → api → frontend-infra → frontend-app
- CloudFormation stacks: `lb-foundation-prod`, `lb-auth-prod`, `lb-api-prod`, `lb-frontend-prod`
- SAM for Lambda deployment

---

## Data Model

### Tables (DynamoDB)

| Table | Hash Key | Range Key | Purpose |
|-------|----------|-----------|---------|
| Users | userId (Cognito sub) | — | User → household mapping |
| Households | householdId (8-char UUID) | — | Shared household, 2-user max |
| Categories | householdId | categoryId | Treasure chests with monthly limits |
| Transactions | householdId | sk (`{monthKey}#TXN#{createdAt}#{txnId}`) | Logged spends |

### Key Design Decisions
- All amounts stored in **cents** (integers)
- Household auto-created on first `GET /me` call
- 8 default categories seeded: Groceries ($600), Dining ($300), Entertainment ($150), Shopping ($200), Transport ($150), Health ($100), Subscriptions ($100), Miscellaneous ($100)
- Transaction SK format enables efficient `begins_with(monthKey)` queries
- Summary computed on-read (no cache table)

---

## API Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | /health | No | Health check |
| GET | /me | Yes | Get/create user + household |
| POST | /household/join | Yes | Join existing household |
| GET | /categories | Yes | List categories |
| POST | /categories | Yes | Create category |
| PUT | /categories/{id} | Yes | Update category |
| GET | /transactions?monthKey= | Yes | List month transactions |
| POST | /transactions | Yes | Log a spend |
| DELETE | /transactions/{id} | Yes | Delete transaction |
| GET | /summary?monthKey= | Yes | Month summary with chest states |
| DELETE | /data | Yes | Delete all household data |

---

## Frontend Pages

| Page | Component | Purpose |
|------|-----------|---------|
| Dashboard | `Dashboard.jsx` | Chest grid + "Log Spend" FAB |
| Log Spend | `LogSpend.jsx` | Amount + category + note → save |
| Month Summary | `MonthSummary.jsx` | Category breakdown + transaction list |
| Settings | `Settings.jsx` | Manage chests, household, delete data |
| Login | `LoginPage.jsx` | Cognito email/password |

### Chest States
- **Healthy** (>60% remaining) — green
- **Low** (20–60%) — yellow
- **Almost Empty** (0–20%) — orange
- **Cracked** (<0%) — red, cracked border

---

## File Structure

```
.github/workflows/deploy.yml    # CI/CD pipeline (DO NOT MODIFY without care)
infra/
  foundation.yml                # KMS, S3, DynamoDB tables
  auth.yml                      # Cognito User Pool
  api.yml                       # API Gateway + Lambda (SAM)
  frontend.yml                  # S3 + CloudFront
backend/
  requirements.txt              # boto3 only
  handlers/
    health.py                   # GET /health
    user.py                     # GET /me, POST /household/join
    categories.py               # CRUD categories
    transactions.py             # Log/list/delete transactions
    summary.py                  # GET /summary
    data.py                     # DELETE /data
  lib/
    db.py                       # DynamoDB helpers
    response.py                 # HTTP response builders
frontend/
  index.html                    # PWA meta tags
  package.json                  # React + Vite + Cognito SDK
  vite.config.js
  public/
    manifest.json               # PWA manifest
    sw.js                       # Service worker
    icon-192.svg, icon-512.svg  # App icons
  src/
    main.jsx                    # React entry
    App.jsx                     # Page router + header
    api.js                      # API client
    auth.js                     # Cognito auth helpers
    styles.css                  # All styles (dark treasure theme)
    pages/
      LoginPage.jsx
      Dashboard.jsx
      LogSpend.jsx
      MonthSummary.jsx
      Settings.jsx
```

---

## Code Conventions

- **Python:** snake_case, type hints optional, f-strings, no classes for handlers
- **JavaScript:** camelCase, functional React components, no TypeScript
- **CSS:** BEM-ish class names, CSS custom properties, no CSS-in-JS
- **Amounts:** Always cents (int). Convert to dollars only in UI display
- **Errors:** Return `{error: "message"}` from backend, display via `.error-msg` class
- **CORS:** Locked to `https://leakingbuckets.goronny.com` in response.py