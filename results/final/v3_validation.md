# v3 pre-run validation (no model was called)

- file: benchmark/tasks_v3.json, SHA-256 `4a5af81ef68c2003bd4f85978f09af00cb03297c08489d8cad2733282026606c`
- tasks: 60; sample_id overlap with v2: 0
- reference answers/solutions passing their own grader: 60/60
- near-duplicate check (SequenceMatcher >= 0.80 after boilerplate stripping) vs classifier training data (seed set + v2 DEV) and vs all v2 tasks: passed