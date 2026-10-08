-- Late deliveries by customer state (states with at least 500 delivered orders).
SELECT
    customer_state,
    count(*)                                              AS delivered_orders,
    round(avg((delivery_status = 'late')::INT) * 100, 1)  AS late_pct,
    round(median(delivery_days), 0)                       AS median_delivery_days,
    round(avg(rating), 2)                                 AS avg_rating
FROM olist_review_facts
WHERE delivery_status IN ('on time', 'late')
GROUP BY customer_state
HAVING count(*) >= 500
ORDER BY late_pct DESC;
