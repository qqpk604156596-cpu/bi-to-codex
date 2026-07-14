# Enterprise Sales Automation

An evidence-backed Power BI Desktop portfolio project built from the public [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online%2Bretail%2Bii) dataset.

The repository demonstrates a governed, template-based workflow for MySQL Import, independent metric reconciliation, a star schema, simulated country RLS, file-based PBIP/PBIR generation, automated quality gates, and human Desktop acceptance.

> This is a public-data practice project, not a paid client engagement. Power BI Service, Fabric, gateway configuration, real-user sharing, and real-client acceptance are not validated.

![Executive Overview](projects/enterprise-sales-automation/evidence/runs/20260714T064441297Z/saved-desktop-screenshots/Executive%20Overview.png)

## What is included

- Three Power BI pages: Executive Overview, Product & Trend Analysis, and Customer & Country Analysis.
- 1,067,371 public retail transaction lines loaded through MySQL 8.0 Import.
- Ten reconciled business measures with DuckDB/MySQL baselines.
- Star-schema semantic model and simulated country-level RLS.
- Versioned PBIP/PBIR/TMDL source assets.
- A local Next.js interaction prototype with Playwright and accessibility coverage.
- Resumable quality gates with stage fingerprints, time budgets, heartbeat logs, and evidence reuse.
- Refresh evidence at 68.59 seconds against a 300-second target.
- Representative Performance Analyzer results up to 455 ms against a 3-second target.

The 30-minute post-mapping automation target was not measured end to end and is not claimed as achieved.

## Repository layout

```text
docs/                                  Shared Power BI delivery standards
projects/enterprise-sales-automation/  PBIP project, SQL, configuration, docs and evidence
scripts/                               Workflow runner and quality gates
templates/bi-project/                  Reusable project scaffold
tests/                                 Workflow and validation tests
```

## Start here

- [Project overview](projects/enterprise-sales-automation/README.md)
- [Portfolio case study](projects/enterprise-sales-automation/docs/portfolio-case-study.md)
- [L1 Desktop delivery checklist](projects/enterprise-sales-automation/docs/delivery-checklist.md)
- [Evidence index](projects/enterprise-sales-automation/evidence/README.md)
- [Automation operations guide](projects/enterprise-sales-automation/docs/agent-runtime-operations.md)

## Local setup

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

Desktop stages require a local Power BI Desktop installation and the project's documented Desktop Bridge integration.

## Data and binary policy

- The source dataset is CC BY 4.0 and must be downloaded from UCI by each user.
- Raw/intermediate data, local databases, credentials, PBIX binaries, caches and unredacted local logs are intentionally excluded.
- PBIP/PBIR/TMDL source files and curated, reviewed evidence are versioned.

## Contributing

Feedback, reproducible bug reports, documentation improvements and focused pull requests are welcome. Good starting areas include:

- testing the workflow on another Windows/Power BI Desktop version;
- improving MySQL and Power Query refresh diagnostics;
- strengthening accessible report patterns;
- adding a separately governed schema adapter without weakening current quality gates;
- reviewing the evidence model and public portfolio narrative.

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## License

Code and original project documentation are licensed under the [MIT License](LICENSE). The UCI Online Retail II dataset remains subject to its own CC BY 4.0 license and is not redistributed here.
