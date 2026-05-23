def calculate_backoff_seconds(retry_count: int, base_delay: int, max_delay: int) -> int:
    retry_count = max(0, int(retry_count or 0))
    return min(max_delay, base_delay * (2 ** retry_count))

