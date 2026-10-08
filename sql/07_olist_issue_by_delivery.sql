-- Olist only: what do unhappy customers complain about when the order came on time,
-- compared with when it was late or never arrived?
WITH labeled AS (
    SELECT
        CASE WHEN f.delivery_status = 'on time' THEN 'on time' ELSE 'late or not delivered' END AS delivery,
        l.primary_issue
    FROM llm_labels l
    JOIN olist_review_facts f USING (review_id)
    WHERE l.source = 'olist'
)
SELECT
    delivery,
    primary_issue,
    count(*)                                                                AS reviews,
    round(count(*) * 100.0 / sum(count(*)) OVER (PARTITION BY delivery), 1) AS share_pct
FROM labeled
GROUP BY delivery, primary_issue
ORDER BY delivery, reviews DESC;
