# S2-QLT-01 — Rollback Plan

## Purpose

Safe revert procedures for the Sprint 2 deterministic risk evaluation feature if a critical defect is discovered after merge into `release/2026-W40`.

---

## Rollback Trigger Criteria

A rollback is triggered if **any** of these conditions occur after merge:

| # | Condition |
|---|-----------|
| 1 | Deterministic scoring produces different results for the same input across runs |
| 2 | Category boundary mapping returns incorrect category at 34.0 or 67.0 |
| 3 | Contract boundary returns an undocumented error code |
| 4 | Explanation engine produces language that constitutes financial advice |
| 5 | Golden examples file fails validation |
| 6 | Anand issues a no-go decision on the UAT checklist |

---

## Rollback Procedure

### Step 1: Identify the Merge Commit

```powershell
git log --oneline --merges -5 release/2026-W40
# Find the merge commit for PR associated with feature/144-s2-risk-evidence
```

### Step 2: Revert the Merge

```powershell
git checkout release/2026-W40
git pull origin release/2026-W40
git revert -m 1 <merge-commit-sha> --no-edit
git push origin release/2026-W40
```

### Step 3: Verify Revert

```powershell
# Confirm S2-QLT-01 directory no longer exists on the branch
git ls-tree -r --name-only release/2026-W40 | Select-String "S2-QLT-01"
# Expected: no output
```

### Step 4: Notify Stakeholders

| Who | Method | Message |
|-----|--------|---------|
| Anand | GitHub comment on PR | "Rollback executed — [reason]. Evidence reverted from W40." |
| P5 (Nayan + Pranjal) | GitHub mention | "Review invalidated by rollback — awaiting re-submission." |
| P6 (Mrugank + Payal) | GitHub mention | "Please investigate root cause and re-submit when fixed." |

---

## Post-Rollback

1. Create a new branch from `release/2026-W40` (post-revert)
2. Fix the identified issue
3. Re-run the full 42-test regression suite
4. Re-submit evidence PR for review
5. Obtain fresh UAT acceptance from Anand

---

## Impact Assessment

| Component | Impact of Rollback |
|-----------|--------------------|
| `ai/risk/scoring.py` | No change — engine code is not modified by this PR |
| `ai/risk/explanation.py` | No change — engine code is not modified by this PR |
| `ai/risk/contract.py` | No change — contract boundary is not modified by this PR |
| `S2-QLT-01/` | Removed entirely — evidence package only |
| CI/CD | No pipeline changes — evidence-only PR |
| Frontend (React/Flutter) | No impact — backend evidence only |

> **Note**: This PR adds **evidence documentation and test harness only**. Rollback removes the evidence package without affecting any production code.

---

*Rollback plan authored by: P6 — Mrugank Kakade + Payal Mude*  
*Date: 2026-10-12*
