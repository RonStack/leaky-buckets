# Leaky-Buckets — Copilot Instructions

## Deployment Rules

Deployments should always go through GitHub Actions, CloudFormation, and AWS CLI commands during the deployment process, not through a local terminal.

You have access to AWS CLI commands within this terminal, but should only use it for troubleshooting, not deploying resources.

The deploy workflow has **path filters** — empty commits won't trigger it. Use `gh workflow run deploy.yml` for manual redeploys, or `workflow_dispatch` from the Actions tab.

---

## Project Overview

**Leaky-Buckets** is a personal finance app that visualizes spending as water filling up buckets — and income as a faucet pouring in. Users upload bank/credit card statements and paystubs (CSV, PDF, or image) and the app categorizes spending into buckets, parses income from paystubs with AI, and shows where all money goes.

**Live URL:** https://leakingbuckets.goronny.com  
**Repo:** https://github.com/RonStack/leaky-buckets  
**AWS Account:** 123525499627 (us-east-1)  

---

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│  React SPA  │────▶│  API Gateway     │────▶│  Lambda (x8) │
│  (CloudFront)│    │  (Cognito auth)  │     │  Python 3.12 │
└─────────────┘     └──────────────────┘     └──────┬───────┘
                                                     │
                                    ┌────────────────┼────────────┐
                                    ▼                ▼            ▼
                              ┌──────────┐    ┌──────────┐  ┌─────────┐
                              │ DynamoDB │    │    S3    │  │ OpenAI  │
                              │ (8 tables)│   │ (uploads)│  │ GPT-4o  │
                              └──────────┘    └──────────┘  └─────────┘
```

### Tech Stack
- **Frontend:** React 18 + Vite 5, hosted on S3/CloudFront
- **Auth:** Amazon Cognito (User Pool + App Client), `amazon-cognito-identity-js`
- **API:** API Gateway REST API with Cognito authorizer
- **Backend:** Python 3.12 Lambda (arm64), SAM-managed
- **Database:** DynamoDB (6 tables), KMS encrypted
- **Storage:** S3 for raw uploads (CSVs, PDFs, images)
- **AI:** OpenAI GPT-4o-mini (merchant categorization), GPT-4o (paystub parsing, statement parsing)
- **CI/CD:** GitHub Actions → CloudFormation/SAM
- **Domain:** leakingbuckets.goronny.com (Route 53 → CloudFront, ACM cert)

---

## Repository Structure

```
leaky-buckets/
├── .github/workflows/
│   ├── deploy.yml          # 6-job deployment pipeline (validate → foundation → auth → api → frontend-infra → frontend-app)
│   └── teardown.yml        # Manual destroy workflow (requires confirmation)
├── backend/
│   ├── handlers/
│   │   ├── buckets.py      # GET /buckets, PUT /buckets/{id}, POST /buckets/seed
│   │   ├── deletedata.py   # POST /delete-all-data (hard deletes all user data)
│   │   ├── health.py       # GET /health (no auth)
│   │   ├── live.py         # POST/GET /live-expenses, PUT/DELETE /live-expenses/{id}
│   │   ├── month.py        # GET /month/{key}, POST /month/{key}/lock
│   │   ├── paystub.py      # POST/GET /paystub, PUT/DELETE /paystub/{id}
│   │   ├── transactions.py # GET /transactions, PUT /transactions/{id}
│   │   └── upload.py       # POST /upload (CSV, PDF, or image)
│   ├── lib/
│   │   ├── categorizer.py  # Merchant memory (DynamoDB) → OpenAI GPT-4o-mini batch (dedup + chunked)
│   │   ├── db.py           # DynamoDB helpers (put/get/query/update/delete/scan/batch)
│   │   ├── normalizer.py   # CSV → normalized transaction format
│   │   ├── paystub_parser.py   # PDF/image paystub → GPT-4o → structured income data
│   │   ├── response.py     # HTTP response helpers with CORS headers
│   │   ├── statement_parser.py # PDF/image statement → GPT-4o → transaction list
│   │   └── __init__.py
│   └── requirements.txt    # boto3, openai, pypdf
├── frontend/
│   ├── src/
│   │   ├── api.js          # API client (all backend calls go through here)
│   │   ├── App.jsx         # Main app shell (header, nav, month picker, page routing)
│   │   ├── auth.js         # Cognito auth helpers (login, logout, token management)
│   │   ├── main.jsx        # React entry point
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx     # Faucet waterfall + bucket grid + summary stats (supports Live mode)
│   │   │   ├── LiveExpensePage.jsx # ⚡ Add live expense form + recent expense list
│   │   │   ├── LoginPage.jsx     # Email/password login, handles newPasswordRequired
│   │   │   ├── ReviewPage.jsx    # Exception-only review (low confidence + uncategorized)
│   │   │   ├── SettingsPage.jsx  # Bucket targets editor + Delete All Data
│   │   │   └── UploadPage.jsx    # 3 source types, accepts CSV/PDF/image
│   │   └── styles.css      # All styles (playful, warm theme)
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── infra/
│   ├── foundation.yml      # KMS key, S3 bucket, 6 DynamoDB tables
│   ├── auth.yml            # Cognito User Pool + App Client
│   ├── api.yml             # API Gateway + 7 Lambda functions (SAM template)
│   └── frontend.yml        # S3 bucket + CloudFront distribution + custom domain
├── copilot_instructions.md
└── Documentation/
    ├── InitialBuildOut.md   # Original spec/requirements
    └── STATUS.md            # Current build status
```

---

## Key AWS Resources

| Resource | Name/ID | Notes |
|---|---|---|
| CloudFormation stacks | `lb-foundation-prod`, `lb-auth-prod`, `lb-api-prod`, `lb-frontend-prod` | All prefixed `lb-*-prod` |
| Cognito User Pool | `us-east-1_lFDwzMhiz` | 2 users registered |
| API Gateway URL | `https://8op9q04t4f.execute-api.us-east-1.amazonaws.com/prod` | REST API |
| CloudFront | `E2SD1TL23SF49V` / `d3inqacv19lrzq.cloudfront.net` | Custom domain alias |
| ACM Certificate | `arn:aws:acm:us-east-1:123525499627:certificate/6b03975e-2c39-4656-8358-94dbbe6003b4` | For `leakingbuckets.goronny.com` |
| Route 53 Zone | `Z30C2B5RZJPYD9` (goronny.com) | CNAME to CloudFront |
| S3 uploads bucket | `lb-uploads-prod-123525499627` | Raw CSVs, PDFs, images |
| SAM artifacts bucket | Set in GitHub Variables as `SAM_ARTIFACTS_BUCKET` | Used during `sam deploy` |

### DynamoDB Tables (all prefixed `lb-*-prod`)
| Table | Partition Key | Sort Key | GSI |
|---|---|---|---|
| `lb-users-prod` | `userId` | — | — |
| `lb-transactions-prod` | `pk` (USER#id) | `sk` (TXN#date#id) | `monthKey` GSI |
| `lb-merchants-prod` | `merchantKey` | — | — |
| `lb-buckets-prod` | `pk` (USER#id) | `sk` (BUCKET#id) | — |
| `lb-monthly-summaries-prod` | `pk` (USER#id) | `sk` (MONTH#key) | — |
| `lb-paystubs-prod` | `paystubId` | — | `byMonth` GSI (monthKey + paystubId) |
| `lb-live-expenses-prod` | `pk` (USER#id) | `sk` (EXP#date#id) | `byMonth` GSI (monthKey + sk) |

---

## GitHub Secrets & Variables

| Name | Type | Purpose |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | Secret | IAM user "Igloo" access key |
| `AWS_SECRET_ACCESS_KEY` | Secret | IAM user "Igloo" secret key |
| `OPENAI_API_KEY` | Secret | OpenAI API key (sk-proj-...) — passed to Lambda via CloudFormation parameter |
| `AWS_REGION` | Variable | `us-east-1` |
| `SAM_ARTIFACTS_BUCKET` | Variable | S3 bucket for SAM deployment artifacts |

---

## Data Flow

### Statement Upload (CSV)
1. Frontend reads CSV as text → `POST /upload { csvContent, source, fileName }`
2. Lambda stores raw CSV in S3
3. `normalizer.py` parses CSV → normalized transactions
4. `categorizer.py` categorizes transactions: merchant memory first (DynamoDB lookup), then remaining unique descriptions sent to OpenAI GPT-4o-mini in batches of 20
5. Transactions stored in DynamoDB with bucket assignment + confidence score

### Statement Upload (PDF/Image)
1. Frontend reads file as base64 → `POST /upload { fileContent, source, fileName }`
2. Lambda stores raw file in S3
3. `statement_parser.py` extracts text from PDF (pypdf) or sends image to GPT-4o vision
4. GPT-4o returns a JSON array of transactions
5. `categorizer.py` categorizes each, same as CSV flow

### Paystub Upload (PDF/Image)
1. Frontend reads file as base64 → `POST /paystub { fileContent, source, fileName }`
2. Lambda stores raw file in S3
3. `paystub_parser.py` extracts text from PDF (pypdf) or sends image to GPT-4o vision
4. **Important:** Text after "Company Contributions" is stripped before AI parsing (those are employer-paid, not employee deductions)
5. GPT-4o returns structured JSON: grossPay, netPay, taxes, retirement, HSA, debt, etc.
6. Stored in paystubs DynamoDB table

### Dashboard View
1. Fetches monthly summary (bucket totals, transaction counts, needs-review count)
2. Fetches paystub data for the month (income totals)
3. Shows **The Faucet** waterfall: Gross → Taxes → Investing → Debt → Take-Home
4. Shows **Bucket Grid** below: spending categories with fill bars and status icons

### Live Expense Recording
1. User switches to **Live** mode via toggle in header (vs **Statements** mode)
2. In Live mode, user sees "Add Expense" nav item instead of Upload/Review
3. User enters amount, picks a bucket, optionally adds a note and date
4. Expense stored in `lb-live-expenses-prod` table with `pk=USER#id`, `sk=EXP#date#uuid`
5. Dashboard in Live mode shows bucket grid filled from live expense totals
6. Live data is stored separately from statement data — eventually can be compared

### Recurring Bills
1. In **Live** mode, user navigates to "Recurring" page to manage monthly bill definitions
2. Each bill has a name, amount, and bucket — no date needed (per-month concept)
3. Bills are stored in `lb-recurring-bills-prod` table with `pk=USER#id`, `sk=BILL#uuid`
4. When viewing any month in Live mode, Dashboard shows a banner if recurring bills haven't been applied
5. User clicks "Apply Now" → backend creates live expenses for each bill with `source: "recurring"` and `recurringBillId`
6. Duplicate detection: already-applied bills (matched by `recurringBillId`) are skipped
7. Month picker includes 3 future months to enable forward-looking planning

---

## Key Design Decisions

- **CORS:** Locked to `https://leakingbuckets.goronny.com` in both `api.yml` (API Gateway) and `response.py` (Lambda headers). Also, `AddDefaultAuthorizerToCorsPreflight: false` is set so OPTIONS requests bypass the Cognito authorizer.
- **Bucket seeding:** Default buckets are auto-seeded on dashboard load (idempotent). Buckets: Housing, Groceries, Dining, Transport, Shopping, Entertainment, Healthcare, Subscriptions, Travel, Misc.
- **Merchant memory:** When a user confirms a categorization on the Review page with "remember," the merchant → bucket mapping is stored in DynamoDB. Next time that merchant appears, it's categorized instantly without AI.
- **Mode toggle:** The app has two modes: **Statements** (analytics from uploaded bank/credit card statements and paystubs) and **Live** (manual real-time expense recording). Mode toggle is in the header. Each mode has its own dashboard view and nav items.
- **Month-scoping:** Transactions, paystubs, and live expenses are all scoped by `monthKey` (e.g., "2026-01"). The frontend has a month picker that drives all data queries.
- **OpenAI models:** GPT-4o-mini for merchant categorization (cheap, fast), GPT-4o for paystub/statement parsing (more capable, handles complex layouts).
- **No PyMuPDF:** We tried PyMuPDF for PDF→image conversion but it requires native C libraries incompatible with Lambda arm64. Switched to `pypdf` (pure Python text extraction). Image-based/scanned PDFs won't work with text extraction — users should upload those as screenshots instead.
- **API Gateway 29s timeout:** REST API has a hard 29-second integration timeout. Lambda timeouts are set higher (60-90s) but the client may get a 504 if AI parsing takes too long. The frontend handles this gracefully — shows "Upload received!" and directs users to check Dashboard/Review in a minute. The Lambda finishes in the background and data lands in DynamoDB.
- **IAM wildcard:** Lambda role uses `arn:aws:dynamodb:*:*:table/lb-*-prod` so new tables don't need explicit IAM policy updates.

---

## Frontend Environment Variables

Set in `.env.production` (committed) or injected during build:

| Variable | Value |
|---|---|
| `VITE_API_URL` | `https://8op9q04t4f.execute-api.us-east-1.amazonaws.com/prod` |
| `VITE_COGNITO_USER_POOL_ID` | `us-east-1_lFDwzMhiz` |
| `VITE_COGNITO_CLIENT_ID` | (check `.env.production` or auth stack outputs) |

---

## Common Tasks

### Add a new Lambda handler
1. Create `backend/handlers/yourhandler.py` with a `handler(event, context)` function
2. Add a `YourFunction` resource in `infra/api.yml` with API Gateway events
3. Use helpers from `lib/response.py` for responses and `lib/db.py` for DynamoDB
4. Push to main — pipeline auto-deploys

### Add a new DynamoDB table
1. Add the table resource in `infra/foundation.yml`
2. Add a CloudFormation export for the table name
3. Import it in `infra/api.yml` Globals → Environment → Variables
4. Lambda IAM role wildcard (`lb-*-prod`) covers it automatically

### Add a new frontend page
1. Create `frontend/src/pages/YourPage.jsx`
2. Import it in `App.jsx` and add to the `PAGES` object
3. Add a nav link in the header section of `App.jsx`

### Redeploy without code changes
```sh
gh workflow run deploy.yml
```

### Check pipeline status
```sh
gh run list --limit 1 --json status,conclusion,displayTitle
```

### Check Lambda environment
```sh
aws lambda get-function-configuration --function-name lb-<handler>-prod --query "Environment.Variables" --region us-east-1
```