-- Why customers give 1-2 stars, by marketplace (from the LLM labels on the 400-review samples).
SELECT
    source,
    primary_issue,
    count(*)                                                              AS reviews,
    round(count(*) * 100.0 / sum(count(*)) OVER (PARTITION BY source), 1) AS share_pct
FROM llm_labels
GROUP BY source, primary_issue
ORDER BY source, reviews DESC;
