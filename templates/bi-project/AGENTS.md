# Project execution rules

Read `project.yaml` and every document in `docs/` before changing data, models, reports, or delivery files.

1. Separate facts, inferences, unknowns, and recommendations.
2. Do not place credentials, client raw data, PBIX binaries, or sensitive personal data in Git.
3. Keep transformations, SQL, Power Query, DAX, tests, and validation evidence reproducible.
4. Stop at a failed quality gate; do not hide or silently bypass failures.
5. Treat client data as non-public unless written authorization says otherwise.
6. Require explicit authorization before publishing, sending, deploying, committing, or pushing.
