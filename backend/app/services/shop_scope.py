def parse_shop_scope(shop_id: str) -> set[str] | None:
    # shop-all or an empty value means all shops; otherwise accept a comma-separated scope.
    values = {value.strip() for value in shop_id.split(",") if value.strip()}
    if not values or "shop-all" in values:
        return None
    return values
