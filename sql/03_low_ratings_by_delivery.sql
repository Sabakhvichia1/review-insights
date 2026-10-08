-- Where do 1-2 star reviews come from? Share of all orders vs share of low ratings,
-- by delivery outcome.
SELECT
    delivery_status,
    count(*)                                                   AS reviews,
    round(count(*) * 100.0 / sum(count(*)) OVER (), 1)         AS share_of_reviews_pct,
    count(*) FILTER (WHERE rating <= 2)                        AS low_ratings,
    round(count(*) FILTER (WHERE rating <= 2) * 100.0
          / sum(count(*) FILTER (WHERE rating <= 2)) OVER (), 1) AS share_of_low_ratings_pct,
    round(avg(rating), 2)                                      AS avg_rating
FROM olist_review_facts
GROUP BY delivery_status
ORDER BY share_of_low_ratings_pct DESC;
