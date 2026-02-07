# Leaky-Buckets — Build Status

> Last updated: 2026-02-07

## Infrastructure (CI/CD Pipeline)

| Component | Status | Notes |
|---|---|---|
| GitHub Actions — deploy workflow | ✅ Done | 6 jobs on push to `main` (paths: infra/, backend/, frontend/) + `workflow_dispatch` |
| GitHub Actions — teardown workflow | ✅ Done | Manual, requires typing "destroy" |
| CloudFormation — Foundation stack | ✅ Deployed | KMS, S3, DynamoDB (6 tables — includes paystubs) |
| CloudFormation — Auth stack | ✅ Deployed | Cognito User Pool + app client |
| CloudFormation — API stack | ✅ Deployed | API Gateway + 7 Lambda functions (SAM) |
| CloudFormation — Frontend stack | ✅ Deployed | S3 + CloudFront CDN + custom domain |
| GitHub Secrets & Variables | ✅ Done | AWS creds, OpenAI key (sk-proj-...), region, SAM bucket |
| Custom domain + SSL | ✅ Done | leakingbuckets.goronny.com, ACM cert, Route 53 CNAME |

## Backend (Lambda Handlers)

| Handler | Status | Endpoints | Notes |
|---|---|---|---|
| `health` | ✅ Done | `GET /health` | No auth |
| `upload` | ✅ Done | `POST /upload` | CSV, PDF, and image — auto-detects format |
| `transactions` | ✅ Done | `GET /transactions`, `PUT /transactions/{id}` | Uses monthKey GSI |
| `buckets` | ✅ Done | `GET /buckets`, `PUT /buckets/{id}`, `POST /buckets/seed` | Seed is idempotent |
| `month` | ✅ Done | `GET /month/{key}`, `POST /month/{key}/lock` | Summary + lock |
| `paystub` | ✅ Done | `POST/GET /paystub`, `PUT/DELETE /paystub/{id}` | PDF + image support |
| `deletedata` | ✅ Done | `POST /delete-all-data` | Cleans all 6 tables + S3 |

## Backend (Core Logic)

| Module | Status | Notes |
|---|---|---|
| `db.py` — DynamoDB helpers | ✅ Done | Generic get/put/query/update/delete/batch/scan |
| `response.py` — API response helpers | ✅ Done | CORS locked to `https://leakingbuckets.goronny.com` |
| `normalizer.py` — CSV normalization | ✅ Done | Bank + credit card formats, strips account numbers |
| `categorizer.py` — Merchant memory + AI | ✅ Done | DynamoDB merchant lookup → OpenAI GPT-4o-mini fallback |
| `paystub_parser.py` — Paystub parsing | ✅ Done | PDF text extraction (pypdf) or image vision (GPT-4o). Strips "Company Contributions" section. |
| `statement_parser.py` — Statement parsing | ✅ Done | PDF text extraction or image vision → GPT-4o → transaction list |

## Frontend (React SPA)

| Component | Status | Notes |
|---|---|---|
| Project scaffolding (Vite + React) | ✅ Done | Lightweight, fast builds |
| Auth (Cognito login) | ✅ Done | `amazon-cognito-identity-js`, handles newPasswordRequired |
| Dashboard — Faucet waterfall | ✅ Done | Shows gross pay → taxes → investing → debt → take-home |
| Dashboard — Bucket grid | ✅ Done | Playful bucket states (🟢🟡🔴), auto-seeds buckets |
| Upload page | ✅ Done | 3 source types (Bank, Credit Card, Paystub), accepts CSV/PDF/image |
| Review page — Exceptions only | ✅ Done | Low confidence + uncategorized, remember merchant |
| Settings — Bucket targets | ✅ Done | Edit monthly spending targets per bucket |
| Settings — Delete all data | ✅ Done | Hard delete with typed "DELETE" confirmation |
| Month picker | ✅ Done | Scopes all data to selected month |
| S3 + CloudFront hosting | ✅ Done | Static site + CDN + custom domain |

## Security

| Requirement | Status | Notes |
|---|---|---|
| Encryption at rest (S3 + DynamoDB) | ✅ Done | KMS managed key with rotation |
| HTTPS only | ✅ Done | CloudFront + API Gateway TLS |
| CORS restricted to domain | ✅ Done | `https://leakingbuckets.goronny.com` |
| CORS preflight fix | ✅ Done | `AddDefaultAuthorizerToCorsPreflight: false` |
| Account number stripping | ✅ Done | Normalizer strips during CSV processing |
| Delete all data (hard delete) | ✅ Done | Settings page, typed confirmation |

## Users

| User | Status |
|---|---|
| ronald.stack@gmail.com | ✅ Created in Cognito |
| ralisa.stack@gmail.com | ✅ Created in Cognito |

## Resolved Issues

| Issue | Resolution |
|---|---|
| CORS 401 on OPTIONS preflight | Added `AddDefaultAuthorizerToCorsPreflight: false` to SAM API config |
| CORS origin wildcard | Locked to `https://leakingbuckets.goronny.com` in api.yml + response.py |
| Transaction update broken query | Fixed to use monthKey GSI query (was using invalid `begins_with("")`) |
| OpenAI API key not reaching Lambda | GitHub Secret had wrong value — verified via `aws lambda get-function-configuration` |
| PyMuPDF fails on Lambda arm64 | Switched to pypdf (pure Python text extraction) — no native C deps |
| OpenAI rejects PDF as image | Removed vision-based PDF approach; extract text with pypdf, send text to GPT-4o |
| Company Contributions in paystub | Strip text after "Company Contributions" before AI parsing (employer-paid, not deductions) |

## Remaining Work

- [ ] End-to-end testing with more statement formats (various banks, credit cards)
- [ ] Consider async processing for large PDF/image statement uploads (API Gateway 29s timeout)
- [ ] Add ability to manually add/edit transactions
- [ ] Add month-over-month comparison view
