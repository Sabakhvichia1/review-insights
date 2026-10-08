"""The complaint categories shared by the LLM, the hand labels and the dashboard."""

ISSUES = {
    "late_delivery": "Order arrived late, or has not arrived yet.",
    "wrong_or_missing_item": "Received the wrong product, or part of the order was missing.",
    "damaged_on_arrival": "Product or packaging arrived broken, leaking or physically damaged.",
    "product_quality": (
        "Product is poor quality, doesn't work, doesn't give the promised result, "
        "is different from the description or photos, or seems fake."
    ),
    "seller_service": (
        "Problem with the seller or store rather than the product: no reply, refund, "
        "return, cancellation, invoice or billing."
    ),
    "price_value": "Too expensive for what it is, or charged more than expected.",
    "other": "Anything else, or no clear complaint.",
}

LABELS = {
    "late_delivery": "Late delivery",
    "wrong_or_missing_item": "Wrong or missing item",
    "damaged_on_arrival": "Damaged on arrival",
    "product_quality": "Product quality",
    "seller_service": "Seller service",
    "price_value": "Price / value",
    "other": "Other",
}
