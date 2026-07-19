# Extraction accuracy report

Matcher: **fuzzy (threshold 85)**  |  videos scored: **12**

## Per-video

| video       |   #gt |   #pred |   prod_P |   prod_R |   prod_F1 |   pv_P |   pv_R |   pv_F1 |
|-------------|-------|---------|----------|----------|-----------|--------|--------|---------|
| 9EgrHHzbYnE |    16 |      18 |     0.67 |     0.75 |      0.71 |   0.61 |   0.69 |    0.65 |
| DUHRAVYLHxs |     1 |       1 |     1    |     1    |      1    |   0    |   0    |    0    |
| FaL8JhFuBBo |    23 |      18 |     0.78 |     0.61 |      0.68 |   0.61 |   0.48 |    0.54 |
| U5lQJEHM7g4 |    23 |      21 |     0.9  |     0.83 |      0.86 |   0.9  |   0.83 |    0.86 |
| V50oT7H8Cl8 |     2 |       2 |     1    |     1    |      1    |   1    |   1    |    1    |
| WOqiHidVb-g |     2 |       1 |     0    |     0    |      0    |   0    |   0    |    0    |
| YmA9l0eHFrk |     5 |       8 |     0.62 |     1    |      0.77 |   0.62 |   1    |    0.77 |
| cqKd_BEHheI |    18 |      11 |     0.91 |     0.56 |      0.69 |   0.91 |   0.56 |    0.69 |
| g6geutlCWjM |    29 |      27 |     0.7  |     0.66 |      0.68 |   0.48 |   0.45 |    0.46 |
| jrfYKdSFso0 |    22 |      17 |     0.94 |     0.73 |      0.82 |   0.71 |   0.55 |    0.62 |
| ls9gPqFxw4o |    14 |      20 |     0.7  |     1    |      0.82 |   0.6  |   0.86 |    0.71 |
| rtBUVRKn0Ck |     7 |       5 |     0.6  |     0.43 |      0.5  |   0.6  |   0.43 |    0.5  |

## Aggregate

| level           |   precision |   recall |   F1 |   TP |   FP |   FN |
|-----------------|-------------|----------|------|------|------|------|
| Product-level   |       0.772 |    0.71  | 0.74 |  115 |   34 |   47 |
| Product+Variant |       0.658 |    0.605 | 0.63 |   98 |   51 |   64 |

## Confidence calibration (product-level)

Precision within each confidence bucket — use it to pick an auto-approve threshold.

| confidence   |   #preds |   #correct | precision   |
|--------------|----------|------------|-------------|
| 0.00-0.50    |        0 |          0 | -           |
| 0.50-0.70    |        4 |          2 | 0.50        |
| 0.70-0.85    |       27 |          9 | 0.33        |
| 0.85-1.00    |      118 |        104 | 0.88        |
