# FinEx Data Ownership Map

**Task:** S1-DAT-01
**Owner:** Shivraj
**Reviewers:** Mitali, Palak

## Catalog: finex_dev

| Schema | Table | Description | Owner |
|--------|-------|-------------|-------|
| core | users | User accounts and auth | Shivraj |
| core | user_profiles | Extended user profile data | Shivraj |
| core | portfolios | User investment portfolios | Shivraj |
| core | portfolio_holdings | Holdings within a portfolio | Shivraj |
| core | transactions | Buy/sell transaction log | Shivraj |
| core | paper_trades | Paper trading simulation records | Shivraj |
| core | goals | User financial goals | Shivraj |
| core | risk_profiles | User risk assessment | Shivraj |
| core | alerts | User notifications/alerts | Shivraj |
| market | instruments | Tradable instruments (stocks, etc.) | Shivraj |
| market | prices | Historical price data | Shivraj |
| market | market_news | News articles for sentiment | Shivraj |
| analytics | portfolio_performance | Computed portfolio returns | Shivraj |
| analytics | risk_metrics | Computed risk metrics | Shivraj |
| analytics | recommendations | AI/rule-based recommendations | Shivraj |
| ai | documents | Uploaded source documents | Shivraj |
| ai | document_chunks | Chunked document text for RAG | Shivraj |
| ai | embeddings | Vector embeddings for chunks | Shivraj |
| ai | conversations | AI chat conversation threads | Shivraj |
| ai | messages | Individual chat messages | Shivraj |

## Access Rules

- **core / market / analytics / ai** — all under `finex_dev` for now (dev environment).
- Row-level isolation enforced at application layer via `user_id` filtering.
- Only backend service account should have write access; read access can be broadened for analytics/BI later.

## Environments (Future)

| Environment | Status | Notes |
|-------------|--------|-------|
| finex_dev | Active | Created and populated with test data |
| finex_staging | Planned | To be created before QA sign-off |
| finex_prod | Planned | To be created before go-live |
