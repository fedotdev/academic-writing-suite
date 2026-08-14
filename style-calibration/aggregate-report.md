# Aggregate Edit-Log Report

Source: `calibration/edit-log.jsonl` (last line, current run only).
Pairs analyzed: `2_1_1`, `2_1_2`, `2_1_4`, `2_2_1`, `3_1_0`. Stale pairs ignored.

## Per-pair summary

| pair_id | n_ops | replaces | deletes | inserts | words_before | words_after | ratio |
|---|---|---|---|---|---|---|---|
| 2_1_1 | 2 | 2 | 0 | 0 | 479 | 177 | 0.370 |
| 2_1_2 | 3 | 3 | 0 | 0 | 542 | 528 | 0.974 |
| 2_1_4 | 1 | 1 | 0 | 0 | 714 | 1162 | 1.627 |
| 2_2_1 | 6 | 6 | 0 | 0 | 634 | 576 | 0.909 |
| 3_1_0 | 3 | 3 | 0 | 0 | 955 | 1982 | 2.075 |
| **Total** | **15** | **15** | **0** | **0** | **3324** | **4425** | **1.331** |

## Big rewrites vs local edits (before length > 40 words)

| pair_id | big_rewrites (>40w) | local_edits (<=40w) | big share |
|---|---|---|---|
| 2_1_1 | 2 | 0 | 100.0% |
| 2_1_2 | 2 | 1 | 66.7% |
| 2_1_4 | 1 | 0 | 100.0% |
| 2_2_1 | 4 | 2 | 66.7% |
| 3_1_0 | 3 | 0 | 100.0% |
| **Total** | **12** | **3** | **80.0%** |

## Notes

- **Words** counted as whitespace-split tokens across all `before`/`after` arrays.
- **Ratio** = words_after / words_before; <1 means net compression.
- Big rewrite = op whose `before` exceeds 40 words; local edit = 40 words or fewer.
