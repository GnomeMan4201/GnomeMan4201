# Evidence record

## Question

Can a report deadline make the report stop waiting while leaving the diagnostic collector alive, and can that distinction be observed at the real Sentry Browser SDK serialization boundary?

## Tested revision

- Repository: `GnomeMan4201/GnomeMan4201`
- Branch: `evidence/sentry-deadline-harness`
- Commit: `423481ba668c03c97ddf2cc6106ab2b178b9928e`
- Workflow run: `31536833473`
- Job: `93929820984`
- Date: 2026-08-11 UTC

## Environment

- GitHub-hosted Ubuntu 24.04 runner
- Node.js `v22.23.1`
- npm `10.9.8`
- `@sentry/browser` `10.67.0` (explicitly version-checked before tests)
- synthetic DSN
- `Sentry.createTransport()` in-memory transport
- no Sentry network request

## Result

PASS.

The suite ran twice in separate Node processes. Each run reported:

```text
3 tests
3 passed
0 failed
```

The three characterization cases were:

```text
PASS  control: a collector that completes inside the budget is serialized
PASS  Promise.race deadline stops report waiting but does not stop the collector
PASS  cooperative cancellation inverts the lifetime assertion: collector aborts instead of completing
```

Observed semantics:

```text
Promise.race deadline
  collector starts
  deadline wins
  report serializes exactly one event without crypto context
  unrelated user/device/storage context survives
  collector is still incomplete at serialization time
  collector is released after serialization
  collector then completes
  serialized event remains unchanged

Cooperative cancellation
  collector starts
  deadline aborts its AbortSignal
  collector observes abort and rejects
  collector never reaches completion
  report serializes exactly one event without crypto context
```

## Verdict

The distinction is reproducible and observable:

> `Promise.race()` can prove **the report stopped waiting**. It does not prove **the collector stopped**.

A collector can outlive the serialized report. Cooperative cancellation changes that lifetime guarantee, but only when the underlying collector participates in cancellation.

This supports the narrower claim discussed with Juan Torchia. It does not claim that Element's crypto implementation currently accepts an `AbortSignal`, nor does it prescribe a production timeout value or scheduling policy.

## Execution note

Workflow run `31536790056` failed before dependency installation because the first CI draft asked `actions/setup-node` to cache against a `package-lock.json` that had not yet been committed. No characterization test ran in that attempt. The cache declaration was removed in commit `423481ba668c03c97ddf2cc6106ab2b178b9928e`; the subsequent run above passed completely. The failed infrastructure attempt is retained rather than hidden from the record.
