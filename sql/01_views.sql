-- One row per order: what was bought, where it went, and how the delivery went.
CREATE OR REPLACE VIEW olist_order_facts AS
WITH items AS (
    SELECT
        i.order_id,
        count(*)              AS n_items,
        sum(i.price)          AS items_value,
        sum(i.freight_value)  AS freight_value,
        -- The most expensive item stands for the order's category and seller.
        arg_max(coalesce(t.product_category_name_english, p.product_category_name, 'unknown'), i.price) AS category,
        arg_max(i.seller_id, i.price) AS seller_id
    FROM olist_items i
    LEFT JOIN olist_products p USING (product_id)
    LEFT JOIN olist_category_names t USING (product_category_name)
    GROUP BY i.order_id
)
SELECT
    o.order_id,
    o.order_status,
    o.order_purchase_timestamp       AS purchased_at,
    o.order_delivered_customer_date  AS delivered_at,
    o.order_estimated_delivery_date  AS promised_at,
    c.customer_state,
    s.seller_state,
    it.category,
    it.n_items,
    it.items_value,
    it.freight_value,
    it.seller_id,
    date_diff('day', o.order_purchase_timestamp, o.order_delivered_customer_date) AS delivery_days,
    -- Positive = days late, negative = days early, compared with the date promised at checkout.
    date_diff('day', CAST(o.order_estimated_delivery_date AS DATE),
                     CAST(o.order_delivered_customer_date AS DATE))               AS days_late,
    CASE
        WHEN o.order_status IN ('canceled', 'unavailable')        THEN 'canceled'
        WHEN o.order_delivered_customer_date IS NULL              THEN 'not delivered'
        WHEN CAST(o.order_delivered_customer_date AS DATE)
           > CAST(o.order_estimated_delivery_date AS DATE)        THEN 'late'
        ELSE 'on time'
    END AS delivery_status
FROM olist_orders o
LEFT JOIN olist_customers c USING (customer_id)
LEFT JOIN items it USING (order_id)
LEFT JOIN olist_sellers s ON s.seller_id = it.seller_id;


-- One row per review, with the facts of the order it belongs to.
-- A few review ids repeat across orders and a few orders have two reviews; keep one of each.
CREATE OR REPLACE VIEW olist_review_facts AS
WITH one_per_review AS (
    SELECT * FROM olist_reviews
    QUALIFY row_number() OVER (PARTITION BY review_id ORDER BY order_id) = 1
),
one_per_order AS (
    SELECT * FROM one_per_review
    QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY review_answer_timestamp DESC) = 1
)
SELECT
    r.review_id,
    r.review_score                                   AS rating,
    nullif(trim(r.review_comment_title), '')         AS title,
    nullif(trim(r.review_comment_message), '')       AS review_text,
    r.review_creation_date                           AS reviewed_at,
    f.*,
    CASE
        WHEN f.delivery_status IN ('canceled', 'not delivered') THEN 8
        WHEN f.days_late <= -10 THEN 1
        WHEN f.days_late <= -1  THEN 2
        WHEN f.days_late = 0    THEN 3
        WHEN f.days_late <= 3   THEN 4
        WHEN f.days_late <= 7   THEN 5
        WHEN f.days_late <= 14  THEN 6
        ELSE 7
    END AS delay_bucket_order,
    CASE
        WHEN f.delivery_status IN ('canceled', 'not delivered') THEN f.delivery_status
        WHEN f.days_late <= -10 THEN '10+ days early'
        WHEN f.days_late <= -1  THEN '1-9 days early'
        WHEN f.days_late = 0    THEN 'on the promised day'
        WHEN f.days_late <= 3   THEN '1-3 days late'
        WHEN f.days_late <= 7   THEN '4-7 days late'
        WHEN f.days_late <= 14  THEN '8-14 days late'
        ELSE '15+ days late'
    END AS delay_bucket
FROM one_per_order r
JOIN olist_order_facts f USING (order_id);


-- Every 1-2 star review with real text, from both marketplaces, in one shape.
CREATE OR REPLACE VIEW low_rating_reviews AS
SELECT 'olist' AS source, review_id, rating, title, review_text, reviewed_at
FROM olist_review_facts
WHERE rating <= 2 AND length(review_text) >= 15
UNION ALL
SELECT 'amazon' AS source, review_id, rating, title, review_text, reviewed_at
FROM amazon_reviews
WHERE rating <= 2 AND length(review_text) >= 15;


-- A fixed random sample of 400 low ratings per marketplace for the LLM to label.
-- md5 ordering makes the sample the same on every machine and every run.
CREATE OR REPLACE VIEW label_sample AS
SELECT * FROM low_rating_reviews
QUALIFY row_number() OVER (PARTITION BY source ORDER BY md5(review_id || 'sample-v1')) <= 400;


-- 50 of those per marketplace, labeled by hand to check the LLM.
CREATE OR REPLACE VIEW hand_label_sample AS
SELECT * FROM label_sample
QUALIFY row_number() OVER (PARTITION BY source ORDER BY md5(review_id || 'hand-v1')) <= 50;
