-- How ratings change with how early or late the order arrived.
SELECT
    delay_bucket,
    count(*)                                  AS reviews,
    round(avg(rating), 2)                     AS avg_rating,
    round(avg((rating = 1)::INT) * 100, 1)    AS one_star_pct,
    round(avg((rating <= 2)::INT) * 100, 1)   AS low_rating_pct
FROM olist_review_facts
GROUP BY delay_bucket, delay_bucket_order
ORDER BY delay_bucket_order;
