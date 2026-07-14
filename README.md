# BI to Codex

An evidence-backed framework for building, validating and evolving Power BI projects with Codex.

The repository separates reusable delivery infrastructure from domain-specific case studies. The current validated case uses public retail sales data; additional data types must bring their own governed contracts, metrics, model and evidence before they can be described as supported.

> Current scope: the reusable workflow and project scaffold exist, but only the Enterprise Sales case has passed the complete Desktop quality gates. This repository is not an arbitrary-schema, any-industry one-click generator.

![Enterprise Sales case — Executive Overview](projects/enterprise-sales-automation/evidence/runs/20260714T064441297Z/saved-desktop-screenshots/Executive%20Overview.png)

## Framework and case studies

| Layer | Purpose | Current status |
| --- | --- | --- |
| Reusable framework | Workflow orchestration, quality gates, evidence model, standards and project scaffold | Implemented and tested |
| Enterprise Sales case | MySQL Import, retail metrics, star schema, simulated country RLS and a three-page report | L1 Desktop deliverable |
| Additional data types | New case-local contracts and adapters for other domains and source shapes | Contributions welcome; not yet validated |

## What the framework provides

- Resumable, stage-based workflow execution with fingerprints, time budgets and heartbeat logs.
- Machine-readable quality gates for documentation, data contracts, metrics, semantic models, PBIP/PBIR and reports.
- A reusable `templates/bi-project/` scaffold that keeps state, source logic, tests and evidence together.
- Explicit separation between reusable core behavior and case-specific schema, measures, visuals and acceptance criteria.
- Evidence-backed capability claims: untested Service, Fabric, gateway and real-user sharing remain explicitly unvalidated.

## Current validated case

[`projects/enterprise-sales-automation/`](projects/enterprise-sales-automation/README.md) is the first reference implementation, built from the public [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online%2Bretail%2Bii) dataset.

It includes:

- 1,067,371 public retail transaction lines loaded through MySQL 8.0 Import.
- Ten reconciled business measures with DuckDB/MySQL baselines.
- A star-schema semantic model and simulated country-level RLS.
- Versioned PBIP/PBIR/TMDL source assets and a local interaction prototype.
- A verified 68.59-second Desktop refresh against a 300-second target.
- Representative Performance Analyzer results up to 455 ms against a 3-second target.

The 30-minute post-mapping automation target was not measured end to end and is not claimed as achieved. This is a public-data practice case, not a paid client engagement.

## Repository layout

```text
docs/                                  Shared standards and case-study contract
projects/                              Independently governed BI case studies
projects/enterprise-sales-automation/  First validated sales case
scripts/                               Reusable workflow runner and quality gates
templates/bi-project/                  Scaffold for a new governed case
tests/                                 Framework and validation tests
```

## Start here

- [Case-study contract](docs/CASE_STUDY_CONTRACT.md)
- [Enterprise Sales overview](projects/enterprise-sales-automation/README.md)
- [Portfolio case study](projects/enterprise-sales-automation/docs/portfolio-case-study.md)
- [L1 Desktop delivery checklist](projects/enterprise-sales-automation/docs/delivery-checklist.md)
- [Evidence index](projects/enterprise-sales-automation/evidence/README.md)
- [Automation operations guide](projects/enterprise-sales-automation/docs/agent-runtime-operations.md)

## Run the current case

Requirements include Windows, Power BI Desktop, MySQL 8.0, MySQL Connector/NET, Python, PowerShell, Node.js and Playwright.

```powershell
python -m venv projects/enterprise-sales-automation/.venv
projects/enterprise-sales-automation/.venv/Scripts/pip install -r projects/enterprise-sales-automation/requirements.txt
Copy-Item projects/enterprise-sales-automation/.env.example projects/enterprise-sales-automation/.env
```

Fill the local `.env` with your own MySQL connection values. Never commit credentials.

Run non-Desktop checks:

```powershell
python scripts/Test-BIReportQA.py --project-path projects/enterprise-sales-automation
python scripts/bi_workflow_runtime.py validate-docs --project-path projects/enterprise-sales-automation
python -m unittest tests.test_bi_workflow_runtime tests.test_report_qa
```

Run the resumable workflow:

```powershell
./scripts/Invoke-BIWorkflow.ps1 -Stage Resume -ProjectPath ./projects/enterprise-sales-automation
```

Desktop stages require a local Power BI Desktop installation and the case's documented Desktop Bridge integration.

## Add another data type

Start from `templates/bi-project/`, create a new folder under `projects/`, and satisfy the [case-study contract](docs/CASE_STUDY_CONTRACT.md). A new case must define its own data grain, rights and sensitivity, source mapping, metric semantics, model, report contract, tests and evidence.

Common logic should move into the framework only after it is proven across at least two materially different cases. Case-specific assumptions must remain inside their case folder.

## Data and binary policy

- Each case must document its dataset source, license and redistribution boundary.
- Raw/intermediate data, local databases, credentials, PBIX binaries, caches and unredacted local logs are excluded.
- PBIP/PBIR/TMDL source files and curated, reviewed evidence may be versioned when authorized.

## Contributing

Feedback, reproducible bug reports, new governed cases, documentation improvements and focused pull requests are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request, or use GitHub Discussions for a proposed data type or architectural change.

## License

Code and original project documentation are licensed under the [MIT License](LICENSE). Case-study datasets remain subject to their own licenses and are not redistributed here.
