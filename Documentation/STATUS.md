# Leaky-Buckets — Build Status

> Last updated: 2026-02-07

## Infrastructure (CI/CD Pipeline)

| Component | Status | Notes |
|---|---|---|
| GitHub Actions — deploy workflow | ✅ Done | Validates + deploys on push to `main` |
| GitHub Actions — teardown workflow | ✅ Done | Manual, requires typing "destroy" |
| CloudFormation — Foundation stack | ✅ Deployed | KMS, S3, DynamoDB (5 tables) |
| CloudFormation — Auth stack | ✅ Deployed | Cognito User Pool + app client |
| CloudFormation — API stack | ✅ Deployed | API Gateway + Lambda (SAM) |
| CloudFormation — Frontend stack | ✅ Deployed | S3 + CloudFront CDN |
| GitHub Secrets & Variables | ✅ Done | AWS creds, OpenAI key, region, SAM bucket |
| Custom domain + SSL | ✅ Done | leakingbuckets.goronny.com, ACM cert, Route 53 |

## Backend (Lambda Handlers)

| Handler | Status | Endpoints |
|---|---|---|
| `health` | ✅ Done | `GET /health` |
| `upload` | ✅ Done | `POST /upload` — CSV processing + S3 raw storage |
| `transactions` | ✅ Done | `GET /transactions`, `PUT /transactions/{id}` |
| `buckets` | ✅ Done | `GET /buckets`, `PUT /buckets/{id}`, `POST /buckets/seed` |
| `month` | ✅ Done | `GET /month/{key}`, `POST /month/{key}/lock` |
| `deletedata` | ✅ Done | `POST /delete-all-data` — hard delete everything |

## Backend (Core Logic)

| Module | Status | Notes |
|---|---|---|
| `db.py` — DynamoDB helpers | ✅ Done | Generic get/put/query/delete/batch/scan |
| `response.py` — API response helpers | ✅ Done | CORS headers locked to custom domain |
| `normalizer.py` — CSV normalization | ✅ Done | Bank + credit card formats, strips account numbers |
| `categorizer.py` — Merchant memory + AI | ✅ Done | Rules first, OpenAI fallback, confidence scoring |

## Frontend (React SPA)

| Component | Status | Notes |
|---|---|---|
| Project scaffolding (Vite + React) | ✅ Done | Lightweight, fast builds |
| Auth (Cognito login) | ✅ Done | `amazon-cognito-identity-js`, handles password change |
| Dashboard — Bucket visualization | ✅ Done | Playful bucket states (🟢🟡🔴), auto-seeds buckets |
| Upload page | ✅ Done | Drag & drop CSV upload (bank/credit card toggle) |
| Review page — Exceptions only | ✅ Done | Low confidence + uncategorized, remember merchant |
| Month lock | ✅ Done | Lock button on review page |
| Settings page — Delete all data | ✅ Done | Hard delete with typed confirmation |
| S3 + CloudFront hosting | ✅ Done | Static site + CDN + custom domain |

## Security

| Requirement | Status | Notes |
|---|---|---|
| Encryption at rest (S3 + DynamoDB) | ✅ Done | KMS managed key |
| HTTPS only | ✅ Done | CloudFront + API Gateway TLS |
| CORS restricted to domain | ✅ Done | `https://leakingbuckets.goronny.com` |
| Account number stripping | ✅ Done | Normalizer strips during CSV processing |
| Delete all data (hard delete) | ✅ Done | Settings page, typed confirmation required |

## Users

| User | Status |
|---|---|
| ronald.stack@gmail.com | ✅ Created in Cognito |
| ralisa.stack@gmail.com | ✅ Created in Cognito |

## Remaining Work

- [ ] End-to-end testing with real CSVs
- [ ] Update OPENAI_API_KEY in GitHub Secrets (if not done)
