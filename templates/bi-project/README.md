# {{PROJECT_NAME}}

This BI project follows the shared BI delivery lifecycle.

## Start here

1. Complete `project.yaml`.
2. Define scope and acceptance criteria in `docs/`.
3. Record the data grain and permissions in `docs/data-contract.md`.
4. Configure `config/data-contract.json`.
5. Run the repository `ValidateAll` workflow after configuring data, metrics, model, and Power BI project files.
6. Do not build report pages until metrics and model checks pass.

## Automated checks

From the parent BI delivery repository:

```powershell
.\scripts\Invoke-BIWorkflow.ps1 -Stage ValidateAll -ProjectPath "<project-path>"
```

To isolate a failed gate, run individual stages:

```powershell
.\scripts\Invoke-BIWorkflow.ps1 -Stage ValidateDataContract -ProjectPath "<project-path>"
.\scripts\Invoke-BIWorkflow.ps1 -Stage TestDataQuality -ProjectPath "<project-path>"
.\scripts\Invoke-BIWorkflow.ps1 -Stage ValidateMetrics -ProjectPath "<project-path>"
.\scripts\Invoke-BIWorkflow.ps1 -Stage ValidateModelSpec -ProjectPath "<project-path>"
.\scripts\Invoke-BIWorkflow.ps1 -Stage ValidatePowerBIProject -ProjectPath "<project-path>"
.\scripts\Invoke-BIWorkflow.ps1 -Stage ValidateReportQA -ProjectPath "<project-path>"
```

CSV checks support required columns, nullability, types, allowed values, numeric ranges, row-count bounds, unique fields, composite primary keys, and restricted arithmetic row formulas. Metric checks support distinct count, sum, average, and ratios. Model-spec checks validate design files only; they do not validate an actual Power BI model. `ValidateAll` summarizes local deterministic checks. `ValidateReportQA` is a separate release-readiness gate for PBIR pages, visual files, and manual QA records; Power BI Desktop refresh, publishing, and client sign-off remain separate gates.

## Main folders

- `data/`: ignored raw/interim data and publishable samples.
- `config/`: machine-readable data contracts.
- `config/metrics.json`: metric definitions, baselines, tolerances, and formats.
- `src/`: extraction, transformation, SQL, Power Query, and DAX sources.
- `model/`: model design specifications and future PBIP/TMDL assets.
- `report/`: PBIR report assets.
- `themes/`: versioned visual themes.
- `tests/`: repeatable data, metric, model, and report checks.
- `evidence/`: profiles, validation results, report QA evidence, and approved screenshots.
