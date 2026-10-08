-- Olist: how often a 1-2 star review is about a wrong or missing item, by order type
-- (from the LLM labels on the 400-review sample).
WITH order_shape AS (
    SELECT order_id, count(*) AS n_items, count(DISTINCT seller_id) AS n_sellers
    FROM olist_items
    GROUP BY order_id
)
SELECT
    CASE
        WHEN o.n_sellers > 1 THEN 'several sellers'
        WHEN o.n_items > 1   THEN 'one seller, several items'
        ELSE 'one item'
    END                                                                AS order_type,
    count(*)                                                           AS low_ratings,
    round(avg((l.primary_issue = 'wrong_or_missing_item')::INT) * 100, 1) AS wrong_or_missing_pct
FROM llm_labels l
JOIN olist_review_facts f USING (review_id)
JOIN order_shape o USING (order_id)
WHERE l.source = 'olist'
GROUP BY order_type
ORDER BY wrong_or_missing_pct;
