# badBANANA Research Method

Version 1.0

This document defines the default evidentiary workflow used for badBANANA Research investigations. Individual projects may add stricter controls, but they should not silently weaken these defaults.

## 1. Research question before collection

Write the question in a form that can produce both supporting and disconfirming evidence.

For investigations where competing explanations are practical, preregister at least:

- **H0** — the observed pattern is compatible with ordinary, independent, or coincidental behavior;
- **H1** — the pattern reflects a shared mechanism, process, or coordination not adequately explained by H0;
- **H2** — a materially different alternative explanation that could produce similar observables.

Hypotheses are analytical structures, not conclusions.

## 2. Evidence classes

Keep evidence and inference separate.

### Observation

A directly recorded property of a source or artifact: timestamp, response body, repository state, file hash, relationship exposed by an API, captured page state, or other reproducible observable.

### Correlation

Two or more observations share a measurable property, timing relationship, structural feature, identifier, or behavior. Correlation does not establish common control, identity, cause, or intent.

### Linkage

Independent evidence supports a relationship stronger than correlation. The exact linkage claim must be stated narrowly and tied to its supporting records.

### Operational inference

A model of process or mechanism that explains multiple linked observations. Operational inference remains distinct from actor identity.

### Attribution

A claim assigning control, authorship, responsibility, or identity to a specific actor. Attribution requires stronger evidence than shared infrastructure, timing, naming, code similarity, or behavioral resemblance alone.

## 3. Source provenance

For every material observation, preserve enough information to identify how it was obtained.

Where practical, record:

- source URL, API, repository, file, or artifact identifier;
- collection timestamp and timezone;
- source-provided timestamp separately from collector time;
- relevant request/query parameters;
- raw or minimally transformed source material;
- SHA-256 or another stable content digest for retained artifacts;
- transformation steps used before analysis;
- collector/tool version or commit when the collection method is material.

Do not silently replace source timestamps with collector timestamps.

## 4. Discovery lineage and independence

Evidence discovered through one lead can create the appearance of independent confirmation when later sources merely repeat that lead.

Maintain a discovery-lineage record for material claims. Two sources should not be treated as independent merely because they have different URLs or publishers.

Before counting evidence as independent, ask:

- Did one source cite, embed, mirror, scrape, syndicate, or derive from the other?
- Did both sources originate from the same upstream dataset or account?
- Did the analyst discover the second source only by following the first source's identifiers?
- Are multiple observations actually multiple views of the same underlying event?

When independence cannot be established, label it unresolved rather than counting it as a separate confirmation.

## 5. Collection discipline

Prefer deterministic collection and bounded queries where practical.

For longitudinal or cluster work:

- preserve collection windows;
- record pagination and truncation boundaries;
- distinguish unavailable records from confirmed absence;
- avoid treating API result order as meaningful unless documented;
- avoid converting missing fields into negative evidence without justification;
- retain negative or null observations when they bear on a hypothesis.

If collection changes during an investigation, record the change and its effect on comparability.

## 6. Disconfirmation

Every promoted analytical claim requires an explicit attempt to find evidence against it.

Useful disconfirmation tests include:

- searching for ordinary examples with the same supposedly distinctive feature;
- testing whether timing synchrony disappears under a wider window;
- checking whether a shared artifact is a template, framework default, or common dependency;
- testing alternate clustering thresholds;
- searching for expected evidence that should exist if the preferred hypothesis were true;
- identifying cases that break the proposed pattern;
- reproducing calculations from raw records rather than screenshots or summaries.

A failed disconfirmation attempt does not prove the hypothesis. It narrows the known alternatives.

## 7. Promotion gate

Do not promote a material claim from hypothesis to supported inference unless:

1. at least two materially independent evidence lines support the claim, unless the claim is itself a direct single-source observation;
2. at least one plausible disconfirming explanation has been tested;
3. known source or collection limitations are recorded;
4. unresolved conflicts are disclosed;
5. the wording of the claim does not exceed the evidence class supporting it.

Unresolved conflicts block promotion when they affect the core claim.

## 8. Confidence

Confidence expresses the strength of the current evidence for the exact stated claim. It is not a probability that the overall narrative is true.

Confidence should decrease when:

- provenance is weak or indirect;
- source independence is unresolved;
- evidence depends on a narrow collection window;
- important expected observations are missing;
- alternate explanations remain viable;
- the conclusion requires multiple inferential jumps.

Prefer bounded language over false precision when the evidence does not support a numeric estimate.

## 9. Corrections and historical integrity

Do not rewrite prior evidentiary states as though the corrected value had always been present.

For material corrections, preserve:

- the original record or digest;
- the corrected value;
- the reason for correction;
- correction timestamp;
- the relationship between the correction and the original record.

Where a system supports append-only correction events or versioned ledgers, use them.

## 10. Reproducibility

A published technical claim should include the smallest practical path for another person to reproduce or falsify it.

Where appropriate, publish:

- pinned source commit or release;
- dependency lockfiles;
- environment requirements;
- exact commands;
- input fixtures or sanitized datasets;
- golden outputs or hashes;
- tests for important failure cases;
- known non-deterministic dependencies;
- a clear statement of what a successful reproduction does and does not prove.

Screenshots can document state but should not substitute for reproducible artifacts when machine-readable evidence is available.

## 11. Public-data and privacy boundary

Use public or explicitly authorized data sources.

Publication should minimize unnecessary personal data. A public identifier may be relevant evidence, but public availability alone does not make every associated personal detail necessary to publish.

Synthetic demonstration records should be visibly labeled as synthetic and never presented as investigative findings.

## 12. AI-assisted analysis

AI may assist with code, normalization, hypothesis generation, summarization, comparison, or drafting. It is not an independent evidence source merely because it produces a second opinion.

Material factual claims should remain traceable to underlying artifacts, measurements, or reproducible computations. When an AI-generated interpretation cannot be independently grounded, treat it as a hypothesis or analytical lead.

## 13. Minimum publication package

For substantial investigations, aim to publish or retain:

```text
research question
hypotheses
collection scope
source/provenance record
observations
analysis/transforms
claim ledger
disconfirmation attempts
limitations
reproduction procedure
corrections/revision history
```

The objective is not to make every investigation large. It is to make the evidentiary boundary inspectable.

## 14. Core rule

Measure first. Attribute last.

A robust pattern is not automatically a specific attribution, and a repeatable result is not automatically a causal explanation.
