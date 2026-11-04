<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

## Architecture rules
- Detection pipeline (feature engineering, Isolation Forest, rule-based reasons) lives in pure modules `src/lib/isolation-forest.ts` and `src/lib/scoring.ts` so it is unit-testable; `src/lib/scoring.functions.ts` is the only server entry that runs it and upserts `risk_scores`.
- Analyst pages live under `src/routes/_authenticated/` and read data client-side through the browser client with RLS (any signed-in analyst can read everything) — single-tenant SOC console.
- `risk_scores` upserts never send `status`, so analyst triage decisions survive re-scoring.
