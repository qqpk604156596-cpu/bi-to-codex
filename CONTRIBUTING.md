# Contributing

Thanks for helping improve this Power BI Desktop delivery workflow.

## Before opening an issue

- Confirm the issue is reproducible from versioned PBIP/PBIR/TMDL or workflow files.
- State your Windows, Power BI Desktop, Python, Node.js and MySQL versions when relevant.
- Separate local facts, inferences and unknowns.
- Do not attach credentials, `.env` files, PBIX binaries, private datasets or unredacted local logs.

## Pull requests

1. Keep changes focused on one quality gate or capability.
2. Preserve the public-data-practice classification and documented limitations.
3. Add or update tests for behavior-bearing changes.
4. Run the relevant non-Desktop checks and include the exact results.
5. For Desktop changes, describe the manual setup and attach only reviewed evidence.
6. Do not mark Service, Fabric, gateway, real-user RLS or real-client acceptance as validated without direct evidence.

## Suggested contribution areas

- workflow reliability and stage-level performance;
- MySQL, Power Query and semantic-model refresh diagnostics;
- PBIR validation and report accessibility;
- evidence schemas and reproducible release gates;
- documentation, onboarding and public portfolio clarity.

Use discussions or issues for design proposals before introducing a new data source, schema family, DirectQuery path or Service/Fabric scope.
