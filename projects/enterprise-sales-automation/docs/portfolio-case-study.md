# Enterprise Sales Automation MVP — Portfolio Case Study

## Classification

**Public-data practice project. Not a paid client engagement.**

Data source: [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online%2Bretail%2Bii), licensed under CC BY 4.0. Dataset citation: Chen, D. (2012), DOI [10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D).

## Client-style problem

A retail operations manager needs a repeatable Power BI Desktop report that explains overall sales performance, product and time drivers, and customer and country contribution. The delivery must remain trustworthy when the source contains cancellations, negative quantities, and missing customer identifiers.

## Implemented solution

This public-data practice project implements a governed, template-based workflow:

1. inspect an approved MySQL schema;
2. propose and manually approve field mappings;
3. build an Import star schema and dynamic country RLS;
4. calculate and independently reconcile sales metrics with DuckDB/SQL;
5. instantiate a three-page PBIR report;
6. block delivery when data, metrics, security, report, or performance gates fail.

## Report and UI contract

- **Executive Overview**
- **Product & Trend Analysis**
- **Customer & Country Analysis**

The report uses a versioned Light Executive design system and a shared UI contract that drives a local interaction prototype and the PBIR generator. Playwright verifies the three-page navigation, dropdown filters, chart selection, comparison states, accessibility scan, and screenshot baseline. Power BI remains the final delivery runtime.

## Evidence required before publication

- 1,067,371 source rows reconciled or deviations explained;
- ten DAX measures matched to DuckDB/SQL baselines;
- dynamic RLS verified for allowed, inactive, and unmapped users;
- PBIR validation with zero errors and zero warnings;
- Import refresh within five minutes on the recorded test machine;
- common interactions typically within three seconds;
- the 30-minute post-mapping generation target is reported only when an end-to-end timing record exists;
- PBIP/PBIX and complete handoff documentation reviewed.

## Current status

The data pipeline, ten-metric reconciliation, star model, simulated country RLS, three-page PBIP/PBIR, shared UI contract, Web prototype, atomic report generation, and resumable evidence workflow are implemented. Native keyboard and screen-reader checks, representative Performance Analyzer scenarios, final visual review, and the manually approved PBIX have passed. The L1 Desktop delivery checklist, evidence index, and final lightweight Release run are complete. The local package meets this repository's L1 Desktop-deliverable standard.

The 30-minute post-mapping automation target was not measured end to end in this run. It remains an unvalidated efficiency target and is not presented as an achieved result.

## Role and contribution

The portfolio project owner approved the scope, field mapping, metric rules, visual acceptance, accessibility checks, final PBIX save, and delivery decision. Codex assisted with the file-based SQL, validation, model/report automation, evidence organization, and resumable quality-gate workflow. The project does not claim paid-client delivery, production deployment, or real-tenant Service validation.

## Internal limitations / 内部限制

- 本案例使用公开数据，不是付费客户经历。
- MySQL使用Import，不包含DirectQuery。
- 数据没有成本，不展示利润、毛利或毛利率。
- 动态RLS使用模拟用户—国家映射，不代表真实客户权限。
- Service、Fabric、网关、真实共享和客户签收均未验证。
- 对外只能声明经过证据支持的Desktop交付与AI辅助自动化能力。
