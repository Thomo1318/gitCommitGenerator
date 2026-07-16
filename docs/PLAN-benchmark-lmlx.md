## Project: Benchmark `lmlx` for Phase 0.5 Semantic Grouping

**Goal**: Execute the v1 and v2 benchmark gauntlets against the `lmlx` server and update `02_detailed_analysis.md` to compare `lmlx`'s latency and semantic adherence against `oMLX` and `MTPLX`.
**Timeline**: 1 Day
**Team**: Test Engineer, Performance Optimizer, Documentation Writer
**Constraints**: Must test both speed (v1) and schema/semantic adherence (v2).

---

## Milestones

| #   | Milestone               | Target Date | Owner     | Success Criteria                                 |
| --- | ----------------------- | ----------- | --------- | ------------------------------------------------ |
| 1   | Benchmark Script Config | Day 1       | Tester    | Scripts hit `lmlx` at `localhost:8010` correctly |
| 2   | v1 Speed Execution      | Day 1       | Optimizer | Cold/Warm cache latencies recorded for `lmlx`    |
| 3   | v2 Gauntlet Execution   | Day 1       | Tester    | JSON, Schema, and Semantic Pair scores recorded  |
| 4   | Documentation Updates   | Day 1       | Docs      | ADR-0005 analysis updated with `lmlx` tables     |

---

## Phase 1: Environment & Script Setup

| Task                                | Effort | Owner  | Depends On | Done Criteria                                   |
| ----------------------------------- | ------ | ------ | ---------- | ----------------------------------------------- |
| Review `benchmarkSmallModels_v2.py` | 1h     | Tester | -          | Verify if `lmlx` requires special client kwargs |
| Start `lmlx` target servers         | 1h     | Tester | -          | Ensure the 4B and 27B models are served         |

## Phase 2: Execution & Analysis

| Task                 | Effort | Owner     | Depends On | Done Criteria                                                |
| -------------------- | ------ | --------- | ---------- | ------------------------------------------------------------ |
| Run v1 Speed Test    | 2h     | Optimizer | Setup      | Record Run 1, 2, and 3 speeds for the models                 |
| Run v2 Semantic Test | 2h     | Tester    | Setup      | Record 10-file gauntlet scoring rubric                       |
| Analyze Results      | 1h     | Optimizer | Tests      | Determine if `lmlx`'s streaming detokenizer/cache beats oMLX |

## Phase 3: Documentation

| Task              | Effort | Owner | Depends On | Done Criteria                                               |
| ----------------- | ------ | ----- | ---------- | ----------------------------------------------------------- |
| Update v1 Table   | 1h     | Docs  | Exec       | `02_detailed_analysis.md` v1 table includes `lmlx`          |
| Update v2 Table   | 1h     | Docs  | Exec       | `02_detailed_analysis.md` v2 table includes `lmlx`          |
| Rewrite Takeaways | 2h     | Docs  | Exec       | "The Takeaway" sections reflect `lmlx` superiority/failures |

---

## Dependencies Map

```text
Script Setup ──> Run v1 ──> Run v2 ──> Analyze Results ──> Update ADR-0005
```

---

## Risks & Mitigation

| Risk                | Impact | Probability | Mitigation                                                                    |
| ------------------- | ------ | ----------- | ----------------------------------------------------------------------------- |
| Incompatible API    | High   | Low         | Modify the script to use standard OpenAI base URL `http://localhost:8010/v1`. |
| Out of Memory (OOM) | High   | Med         | Load and test one model at a time with `lmlx serve`.                          |
