# ADR-0001: LLM Proposals and Deterministic Financial Authority

- **Status:** ACCEPTED
- **Date:** 2026-10-15
- **Owner:** Project owner

## Context
Budget Kernel uses LLMs for interpreting financial instructions and making non-binding suggestions. Financial authorization must remain correct when a model is mistaken, compromised, unavailable, or manipulated.

## Decision
An LLM, routing model, confidence score, prompt, retrieved example or provider response may only produce an untrusted typed proposal. Deterministic application code checks the proposal against current canonical mandate/grant/ledger state and is the only component allowed to authorize, reserve, settle, release or reject a transaction.

## Consequences
- Model output requires schema and semantic validation.
- All ledger mutations go through one domain service and transactional persistence.
- The application fails closed where unresolved intent is needed for authorization.
- The model cannot override a rejection or change protected reserve/policy state.

## Evidence and validation
Required tests: prompt injection attempting to force approval, model output containing `authorized=true`, provider failure and budget exhaustion. No implementation result has been verified yet.

## Revisit when
Never weaken the fundamental boundary. Implementation choices may change, but authorization must remain deterministic and independent of LLM judgment.
