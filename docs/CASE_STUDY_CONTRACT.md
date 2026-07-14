# Case-study contract

BI to Codex is organized as a reusable delivery framework plus independently governed BI case studies. A case proves support for its own data and operating boundary; it does not prove arbitrary-schema or cross-industry support.

## Required structure

Create each case under `projects/<case-slug>/` from `templates/bi-project/`. Keep the following assets versioned where applicable:

- `project.yaml`: machine-readable status, ownership, delivery scope and external validation boundaries;
- `config/`: data contract, approved source mapping and metric definitions;
- `src/`: source-specific SQL, Power Query, DAX, extraction and transformation logic;
- `model/` and PBIP assets: semantic-model and report source files;
- `tests/`: case-local behavior and contract tests;
- `docs/`: scope, metric dictionary, model/report decisions, limitations and delivery notes;
- `evidence/`: sanitized machine and human evidence supporting each quality gate.

## Required decisions

Before implementation, document:

1. dataset ownership, license, sensitivity and redistribution boundary;
2. table grain, keys, null policy, time semantics and expected row volumes;
3. source system, connection mode and approved schema mapping;
4. metric definitions, reconciliation method and tolerances;
5. semantic-model relationships, filter direction and RLS boundary;
6. report users, decisions, accessibility requirements and performance targets;
7. which capabilities require Power BI Desktop, Service, Fabric, a gateway or human acceptance.

## Evidence requirements

Every claimed capability must have current evidence at the appropriate layer:

- data contract and data-quality results;
- independent metric reconciliation;
- model and relationship validation;
- RLS definition and, where claimed, effective-identity validation;
- PBIP/PBIR and report QA;
- refresh and representative interaction duration;
- human visual and accessibility acceptance;
- release summary with explicit unvalidated boundaries.

Public cases must exclude credentials, private data, PBIX binaries, local caches and unredacted logs.

## Reuse rule

Keep case-specific assumptions inside the case. Move behavior into `scripts/`, `templates/` or shared standards only when:

- the behavior is needed by at least two materially different cases;
- its inputs and outputs can be expressed without domain-specific field names;
- both cases retain passing tests after extraction; and
- the shared capability and its unsupported boundaries are documented.

Until those conditions are met, describe the feature as case-local rather than framework-wide.

## Current coverage

The Enterprise Sales Automation case is the only case that currently passes the complete L1 Desktop quality gates. Additional data types are a roadmap and contribution area, not a validated capability claim.
