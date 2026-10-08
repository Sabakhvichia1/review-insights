-- Olist, on-time orders only: are orders with several items or several sellers rated worse?
-- Items from different sellers ship separately, so the first parcel can look like an incomplete order.
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
    END                                        AS order_type,
    count(*)                                   AS orders,
    round(avg(f.rating), 2)                    AS avg_rating,
    round(avg((f.rating <= 2)::INT) * 100, 1)  AS low_rating_pct
FROM olist_review_facts f
JOIN order_shape o USING (order_id)
WHERE f.delivery_status = 'on time'
GROUP BY order_type
ORDER BY low_rating_pct;
