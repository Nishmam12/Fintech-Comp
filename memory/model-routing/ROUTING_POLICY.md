# Model Routing Policy

**Status:** proposed policy; exact routes and thresholds must be measured.

## Objectives
Optimize financial interpretation correctness per dollar while keeping authorization deterministic. The 80% no-paid-inference / 18% primary / 2% escalation mix is a workload hypothesis, not a quota.

## Decision flow
1. Validate request size, known fields and schema.
2. Use deterministic handling only if the input is structured or fully resolvable by tested rules.
3. Otherwise call the primary interpretation model with a compact schema-driven prompt and minimal necessary context.
4. Validate output structurally and semantically.
5. Escalate only for benchmark-supported classes: unresolved contradiction, material schema/semantic error, complex constraint reasoning, out-of-distribution signal or a known failure class. Bound repair/escalation attempts.
6. If uncertainty remains material, send to human review or return unresolved. Never approve by default.
7. Pass every proposal to the deterministic kernel.

## Initial provider candidates
- Alibaba direct Qwen Flash family as primary.
- DeepSeek direct Flash/reasoning route for escalation.
- Optional GLM/OpenRouter alternative in controlled evaluation.
- Jev/TypeSafe only if it improves quality/cost versus rules-only routing after fair testing.

All exact model IDs, regions, context tiers, structured-output support, pricing and billing of hidden reasoning tokens must be re-verified from official source pages at implementation time. Do not silently change aliases; pin model/provider and log actual route.

## Required logged fields
Request ID, schema/prompt version, provider, model ID, route reason, input/output/reasoning tokens where available, estimated cost, actual billed cost, retries, latency, parse/validation outcomes, escalation, and non-authorizing proposal outcome. Data fields must comply with data minimization; do not log raw secrets or full transaction documents by default.

## Failure behavior
- Provider timeout: bounded retry only if safe; otherwise valid deterministic processing or review.
- Invalid output: reject output, optionally one bounded repair attempt; never authorize invalid schema.
- Unavailable model: return unresolved/review where interpretation is required.
- Exhausted budget: stop paid calls; do not silently switch to unreviewed routes or authorize unresolved intent.
- Model claim `authorized=true`: ignore/reject as untrusted; authorization is computed from canonical state.
