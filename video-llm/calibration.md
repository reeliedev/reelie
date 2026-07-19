# Confidence calibration — judge matcher

Matcher: **LLM judge (claude-sonnet-4-6)**  |  149 predictions across 12 videos

## Buckets — fuzzy vs judge (side by side)

| confidence   |   #preds |   fuzzy #correct |   fuzzy prec |   judge #correct |   judge prec |
|--------------|----------|------------------|--------------|------------------|--------------|
| >= 0.85      |      118 |              104 |         0.88 |              104 |         0.88 |
| 0.70 - 0.85  |       27 |                9 |         0.33 |               12 |         0.44 |
| < 0.70       |        4 |                2 |         0.5  |                1 |         0.25 |

## Threshold sweep (auto-approve at confidence >= T; judge-verified)

|   threshold |   #approved | coverage   |   precision |
|-------------|-------------|------------|-------------|
|       0.7   |         145 | 97%        |       0.8   |
|       0.725 |         135 | 91%        |       0.822 |
|       0.75  |         135 | 91%        |       0.822 |
|       0.775 |         130 | 87%        |       0.838 |
|       0.8   |         129 | 87%        |       0.845 |
|       0.825 |         118 | 79%        |       0.881 |
|       0.85  |         118 | 79%        |       0.881 |
|       0.875 |         103 | 69%        |       0.903 |
|       0.9   |          93 | 62%        |       0.935 |
|       0.925 |          32 | 21%        |       0.906 |
|       0.95  |          32 | 21%        |       0.906 |

## Recommendation

**Recommended auto-approve threshold: confidence >= 0.875** — lowest threshold with judge precision >= 0.90 (precision 0.903, coverage 69%).


> The old >= 0.85 rule was derived under the fuzzy matcher. Under the judge, use the recommendation above.