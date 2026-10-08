-- Olist only: do the LLM's "late delivery" labels agree with the actual delivery dates?
SELECT
    l.primary_issue = 'late_delivery'   AS llm_says_late_delivery,
    f.delivery_status,
    count(*)                            AS reviews
FROM llm_labels l
JOIN olist_review_facts f USING (review_id)
WHERE l.source = 'olist'
GROUP BY ALL
ORDER BY llm_says_late_delivery DESC, reviews DESC;
