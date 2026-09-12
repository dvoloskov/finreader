# ADR-0001: Neutral financial core with a read-only GnuCash boundary

- Status: Accepted
- Date: 2026-09-09
- Supersedes: None
- Superseded by: None

## Context

This record captures decisions agreed and implemented on 2026-09-06–07. The dev branch already had source-faithful frozen dataclasses and Decimal. The user wants one end-to-end Sberbank/GnuCash workflow first and may later move to Beancount.

## Decision

Keep source parsing separate from financial events, accounting policy and destination serialization. Preserve acquisition facts, quantities, values and provenance in the neutral core. Use existing dataclasses/Decimal, not pandas. Keep account paths, native GUIDs and commodity namespaces at the GnuCash boundary. Export native multi-split CSV plus a verification manifest; read only closed book snapshots. Do not write native books directly. Require an actual disposable-book import/readback, not just serialization tests.

## Consequences

- Future Beancount work can consume financial events instead of reverse-engineering GnuCash CSV; lot-adjustment serialization still requires destination-specific design.
- Exact source reconciliation, explicit mappings and saved-book verification are mandatory safeguards.
- Beancount export/migration and additional providers remain deferred; no plugin framework or extra dependency is needed for this milestone.
