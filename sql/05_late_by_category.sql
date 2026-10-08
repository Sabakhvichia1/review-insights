-- The 15 biggest product categories: how often they arrive late, and how they're rated.
SELECT
    category,
    count(*)                                              AS delivered_orders,
    round(avg((delivery_status = 'late')::INT) * 100, 1)  AS late_pct,
    round(avg(rating) FILTER (WHERE delivery_status = 'on time'), 2) AS avg_rating_on_time,
    round(avg(rating) FILTER (WHERE delivery_status = 'late'), 2)    AS avg_rating_late
FROM olist_review_facts
WHERE delivery_status IN ('on time', 'late')
GROUP BY category
ORDER BY delivered_orders DESC
LIMIT 15;
