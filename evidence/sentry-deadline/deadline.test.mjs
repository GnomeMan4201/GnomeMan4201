import assert from "node:assert/strict";
import { test } from "node:test";
import * as Sentry from "@sentry/browser";

const DSN = "https://public@example.invalid/1";
const DEADLINE_MS = 25;
const FLUSH_TIMEOUT_MS = 1_000;

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function decodeRequestBody(body) {
  if (typeof body === "string") return body;
  if (body instanceof Uint8Array) return new TextDecoder().decode(body);
  if (body instanceof ArrayBuffer) return new TextDecoder().decode(new Uint8Array(body));
  throw new TypeError(`Unsupported Sentry request body: ${Object.prototype.toString.call(body)}`);
}

function parseEnvelope(body) {
  const lines = decodeRequestBody(body).trimEnd().split("\n");
  const envelopeHeader = JSON.parse(lines[0]);
  const items = [];

  for (let i = 1; i < lines.length; i += 2) {
    const itemHeader = JSON.parse(lines[i]);
    const payloadLine = lines[i + 1];
    assert.notEqual(payloadLine, undefined, "envelope item is missing its payload");
    items.push({ header: itemHeader, payload: JSON.parse(payloadLine) });
  }

  return { header: envelopeHeader, items };
}

function eventFromSingleRequest(requests) {
  assert.equal(requests.length, 1, "expected exactly one serialized Sentry request");
  const envelope = parseEnvelope(requests[0].body);
  const events = envelope.items.filter(({ header }) => header.type === "event");
  assert.equal(events.length, 1, "expected exactly one event envelope item");
  return events[0].payload;
}

function baseContexts() {
  return {
    user: { username: "@synthetic:example.invalid" },
    device: { device_id: "SYNTHETIC" },
    storage: { storageManager_persisted: "false" },
  };
}

function initLocalSentry(requests, state) {
  Sentry.init({
    dsn: DSN,
    defaultIntegrations: false,
    transport: (options) =>
      Sentry.createTransport(options, async (request) => {
        state.serializedAt = performance.now();
        requests.push(request);
        return { statusCode: 200 };
      }),
  });
}

async function sendWithRaceDeadline({ collector, family = "crypto", deadlineMs = DEADLINE_MS }) {
  const contexts = baseContexts();
  const collectorPromise = Promise.resolve().then(collector);
  const outcome = await Promise.race([
    collectorPromise.then((value) => ({ kind: "completed", value })),
    new Promise((resolve) => setTimeout(() => resolve({ kind: "deadline" }), deadlineMs)),
  ]);

  if (outcome.kind === "completed") contexts[family] = outcome.value;

  Sentry.captureMessage("synthetic deadline characterization", {
    level: "info",
    contexts,
    extra: { policy: "race-deadline", deadline_ms: deadlineMs },
  });

  const flushed = await Sentry.flush(FLUSH_TIMEOUT_MS);
  assert.equal(flushed, true, "Sentry did not flush the local transport");

  return { outcome, collectorPromise };
}

async function sendWithCooperativeCancellation({ collector, family = "crypto", deadlineMs = DEADLINE_MS }) {
  const contexts = baseContexts();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(new Error("synthetic report deadline")), deadlineMs);

  let outcome;
  try {
    const value = await collector(controller.signal);
    outcome = { kind: "completed", value };
    contexts[family] = value;
  } catch (error) {
    if (!controller.signal.aborted) throw error;
    outcome = { kind: "aborted", error };
  } finally {
    clearTimeout(timer);
  }

  Sentry.captureMessage("synthetic cancellation characterization", {
    level: "info",
    contexts,
    extra: { policy: "cooperative-cancellation", deadline_ms: deadlineMs },
  });

  const flushed = await Sentry.flush(FLUSH_TIMEOUT_MS);
  assert.equal(flushed, true, "Sentry did not flush the local transport");

  return { outcome };
}

test("control: a collector that completes inside the budget is serialized", async () => {
  const requests = [];
  const state = {};
  initLocalSentry(requests, state);

  const { outcome } = await sendWithRaceDeadline({
    collector: async () => ({ device_keys: "synthetic" }),
  });

  assert.equal(outcome.kind, "completed");
  const event = eventFromSingleRequest(requests);
  assert.deepEqual(event.contexts.crypto, { device_keys: "synthetic" });
  assert.deepEqual(event.contexts.user, baseContexts().user);
  assert.deepEqual(event.contexts.device, baseContexts().device);
  assert.deepEqual(event.contexts.storage, baseContexts().storage);
});

test("Promise.race deadline stops report waiting but does not stop the collector", async () => {
  const requests = [];
  const transportState = {};
  initLocalSentry(requests, transportState);

  const gate = deferred();
  const collectorState = {
    started: false,
    completed: false,
    completedAt: undefined,
  };

  const { outcome, collectorPromise } = await sendWithRaceDeadline({
    collector: async () => {
      collectorState.started = true;
      const value = await gate.promise;
      collectorState.completed = true;
      collectorState.completedAt = performance.now();
      return value;
    },
  });

  assert.equal(outcome.kind, "deadline");
  assert.equal(collectorState.started, true, "collector never started");
  assert.equal(collectorState.completed, false, "collector completed before the report left");
  assert.equal(requests.length, 1, "report did not serialize after the deadline");
  assert.equal(typeof transportState.serializedAt, "number", "transport never observed the envelope");

  const event = eventFromSingleRequest(requests);
  assert.equal(event.contexts.crypto, undefined, "timed-out crypto context leaked into the report");
  assert.deepEqual(event.contexts.user, baseContexts().user);
  assert.deepEqual(event.contexts.device, baseContexts().device);
  assert.deepEqual(event.contexts.storage, baseContexts().storage);

  gate.resolve({ device_keys: "late-synthetic" });
  await collectorPromise;

  assert.equal(collectorState.completed, true, "collector did not eventually complete");
  assert.ok(
    collectorState.completedAt > transportState.serializedAt,
    `collector completion (${collectorState.completedAt}) must occur after report serialization (${transportState.serializedAt})`,
  );

  // The report is already serialized. A late collector completion must not mutate it retroactively.
  const serializedEvent = eventFromSingleRequest(requests);
  assert.equal(serializedEvent.contexts.crypto, undefined);
});

test("cooperative cancellation inverts the lifetime assertion: collector aborts instead of completing", async () => {
  const requests = [];
  const transportState = {};
  initLocalSentry(requests, transportState);

  const collectorState = {
    started: false,
    completed: false,
    aborted: false,
  };

  const { outcome } = await sendWithCooperativeCancellation({
    collector: (signal) =>
      new Promise((resolve, reject) => {
        collectorState.started = true;
        const timer = setTimeout(() => {
          collectorState.completed = true;
          resolve({ device_keys: "too-late" });
        }, 250);

        signal.addEventListener(
          "abort",
          () => {
            clearTimeout(timer);
            collectorState.aborted = true;
            reject(signal.reason ?? new Error("aborted"));
          },
          { once: true },
        );
      }),
  });

  assert.equal(outcome.kind, "aborted");
  assert.equal(collectorState.started, true);
  assert.equal(collectorState.aborted, true, "collector did not observe cancellation");
  assert.equal(collectorState.completed, false, "collector completed despite cancellation");

  const event = eventFromSingleRequest(requests);
  assert.equal(event.contexts.crypto, undefined);
  assert.deepEqual(event.contexts.user, baseContexts().user);
  assert.deepEqual(event.contexts.device, baseContexts().device);
  assert.deepEqual(event.contexts.storage, baseContexts().storage);
});
