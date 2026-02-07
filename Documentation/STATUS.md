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
| GitHub Secrets & Variables | ✅ Done | AWS creds, OpenAI key, region, SAM bucket |

## Backend (Lambda Handlers)

| Handler | Status | Endpoints |
|---|---|---|
| `health` | ✅ Done | `GET /health` |
| `upload` | ✅ Done | `POST /upload` — presigned URL + CSV processing |
| `transactions` | ✅ Done | `GET /transactions`, `PUT /transactions/{id}` |
| `buckets` | ✅ Done | `GET /buckets`, `PUT /buckets/{id}`, `POST /buckets/seed` |
| `month` | ✅ Done | `GET /month/{key}`, `POST /month/{key}/lock` |

## Backend (Core Logic)

| Module | Status | Notes |
|---|---|---|
| `db.py` — DynamoDB helpers | ✅ Done | Generic get/put/query/delete/batch |
| `response.py` — API response helpers | ✅ Done | CORS headers, error formatting |
| `normalizer.py` — CSV normalization | ✅ Done | Bank + credit card formats, strips account numbers |
| `categorizer.py` — Merchant memory + AI | ✅ Done | Rules first, OpenAI fallback, confidence scoring |

## Frontend (React SPA)

| Component | Status | Notes |
|---|---|---|
| Project scaffolding (Vite + React) | ✅ Done | Lightweight, fast builds |
| Auth (Cognito login) | ✅ Done | `amazon-cognito-identity-js` |
| Dashboard — Bucket visualization | ✅ Done | Playful bucket states (🟢🟡🔴) |
| Upload page | ✅ Done | Drag & drop CSV upload |
| Review page — Exceptions only | ✅ Done | Low confidence + uncategorized |
| Month lock | ✅ Done | Lock button on review page |
| S3 + CloudFront hosting | ⬜ Not started | Static site hosting |

## Remaining Work

- [ ] CloudFront distribution for frontend hosting
- [ ] Custom domain + SSL (optional)
- [ ] "Delete all data" button (user control)
- [ ] Create the two Cognito users
- [ ] End-to-end testing with real CSVs
