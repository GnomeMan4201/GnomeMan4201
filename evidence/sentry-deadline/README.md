# Sentry deadline characterization

This is a narrow, network-free evidence harness for the distinction raised in Juan Torchia's DEV discussion around diagnostic collectors that hang instead of reject.

It is not a proposed Element production patch. It characterizes two different guarantees:

1. **Report stopped waiting** — a `Promise.race()` deadline allows the report to serialize without the late diagnostic family, while the collector remains alive and can complete after the report has already left.
2. **Collector actually stopped** — cooperative cancellation propagates an `AbortSignal`; the collector observes the abort and rejects instead of completing.

The harness uses the same `@sentry/browser` version named in Juan's evidence package (`10.67.0`), a synthetic DSN, and an in-memory transport built with `Sentry.createTransport()`. No network request is made by Sentry. Assertions are made against the serialized Sentry envelope rather than a mocked `captureMessage()` call.

## Invariants

For the deadline case the test requires all of the following in one run:

- the synthetic crypto collector started;
- the report deadline expired first;
- exactly one Sentry event serialized;
- unrelated `user`, `device`, and `storage` contexts survived;
- `crypto` context was absent from the serialized event;
- the collector had **not** completed when the envelope serialized;
- after the report was already serialized, releasing the collector caused it to complete;
- that late completion did not retroactively mutate the serialized event.

For the cancellation case the final lifetime assertion inverts:

- the collector receives the abort;
- it rejects rather than completing;
- the report still serializes without the missing family.

A happy-path control verifies that a collector which completes inside the budget is included in the event.

## Run

```bash
cd evidence/sentry-deadline
npm ci
npm test
```

CI intentionally runs the test suite twice in separate Node processes to reduce the chance of a result depending on residual Sentry SDK state.

## Scope

This demonstrates the semantics of a deadline boundary around an optional diagnostic family using the real Sentry Browser SDK serialization path. It does **not** establish that Element's underlying crypto APIs support cancellation; that is a separate implementation constraint. The purpose is to make the difference between control-flow timeout and resource-lifetime cancellation observable and falsifiable.

## Provenance

Discussion source: Juan Torchia, *The bug report that never left the browser*, DEV Community, Aug. 2026.

Juan's published evidence harness uses a local `Sentry.createTransport()` transport and the real Browser SDK; this characterization follows that evidentiary shape while isolating only the hang/deadline question.
