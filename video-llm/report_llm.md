# Extraction accuracy report

Matcher: **LLM judge (claude-sonnet-4-6)**  |  videos scored: **12**

## Per-video

| video       |   #gt |   #pred |   prod_P |   prod_R |   prod_F1 |   pv_P |   pv_R |   pv_F1 |
|-------------|-------|---------|----------|----------|-----------|--------|--------|---------|
| 9EgrHHzbYnE |    16 |      18 |     0.89 |     1    |      0.94 |   0.83 |   0.94 |    0.88 |
| DUHRAVYLHxs |     1 |       1 |     1    |     1    |      1    |   0    |   0    |    0    |
| FaL8JhFuBBo |    23 |      18 |     0.89 |     0.7  |      0.78 |   0.89 |   0.7  |    0.78 |
| U5lQJEHM7g4 |    23 |      21 |     0.9  |     0.83 |      0.86 |   0.81 |   0.74 |    0.77 |
| V50oT7H8Cl8 |     2 |       2 |     1    |     1    |      1    |   1    |   1    |    1    |
| WOqiHidVb-g |     2 |       1 |     1    |     0.5  |      0.67 |   0    |   0    |    0    |
| YmA9l0eHFrk |     5 |       8 |     0.62 |     1    |      0.77 |   0.62 |   1    |    0.77 |
| cqKd_BEHheI |    18 |      11 |     0.91 |     0.56 |      0.69 |   0.91 |   0.56 |    0.69 |
| g6geutlCWjM |    29 |      27 |     0.81 |     0.76 |      0.79 |   0.59 |   0.55 |    0.57 |
| jrfYKdSFso0 |    22 |      17 |     1    |     0.77 |      0.87 |   0.94 |   0.73 |    0.82 |
| ls9gPqFxw4o |    14 |      20 |     0.7  |     1    |      0.82 |   0.7  |   1    |    0.82 |
| rtBUVRKn0Ck |     7 |       5 |     0.8  |     0.57 |      0.67 |   0.8  |   0.57 |    0.67 |

## Aggregate

| level           |   precision |   recall |    F1 |   TP |   FP |   FN |
|-----------------|-------------|----------|-------|------|------|------|
| Product-level   |       0.852 |    0.784 | 0.817 |  127 |   22 |   35 |
| Product+Variant |       0.772 |    0.71  | 0.74  |  115 |   34 |   47 |

## Confidence calibration (product-level)

Precision within each confidence bucket — use it to pick an auto-approve threshold.

| confidence   |   #preds |   #correct | precision   |
|--------------|----------|------------|-------------|
| 0.00-0.50    |        0 |          0 | -           |
| 0.50-0.70    |        4 |          4 | 1.00        |
| 0.70-0.85    |       27 |         14 | 0.52        |
| 0.85-1.00    |      118 |        109 | 0.92        |
