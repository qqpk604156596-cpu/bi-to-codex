# Contributing

Thanks for helping improve BI to Codex: an evidence-backed framework for governed Power BI delivery with domain-specific case studies.

## Before opening an issue

- Confirm the issue is reproducible from versioned PBIP/PBIR/TMDL or workflow files.
- State your Windows, Power BI Desktop, Python, Node.js and source-system versions when relevant.
- Separate local facts, inferences and unknowns.
- Do not attach credentials, `.env` files, PBIX binaries, private datasets or unredacted local logs.

## Pull requests

1. Keep changes focused on one quality gate or capability.
2. Preserve the public-data-practice classification and documented limitations.
3. Add or update tests for behavior-bearing changes.
4. Run the relevant non-Desktop checks and include the exact results.
5. For Desktop changes, describe the manual setup and attach only reviewed evidence.
6. Do not mark Service, Fabric, gateway, real-user RLS or real-client acceptance as validated without direct evidence.

## Adding a case study

1. Start from `templates/bi-project/` and use a distinct folder under `projects/`.
2. Follow the [case-study contract](docs/CASE_STUDY_CONTRACT.md).
3. Keep domain assumptions, source mappings, metrics and report requirements inside the case.
4. Add machine-readable tests and curated evidence for every capability claim.
5. Do not promote case-specific logic into the reusable framework until it is proven across at least two materially different cases.

## Suggested contribution areas

- workflow reliability and stage-level performance;
- source-system, Power Query and semantic-model refresh diagnostics;
- PBIR validation and report accessibility;
- evidence schemas and reproducible release gates;
- governed adapters and case studies for additional data types;
- documentation, onboarding and public portfolio clarity.

Use discussions or issues for design proposals before introducing a new data source, schema family, DirectQuery path or Service/Fabric scope.
