from jobs.sync_anime_metadata import sync_anime_metadata


NOT_YET_AIRED_STATUS = "Not yet aired"


def sync_upcoming_anime_metadata(batch_size: int = 20, request_delay: float = 1.0) -> dict:
    """
    Refreshes MAL-managed metadata only for anime that have not started airing.
    """
    return sync_anime_metadata(batch_size=batch_size, request_delay=request_delay, status=NOT_YET_AIRED_STATUS)


if __name__ == "__main__":
    sync_upcoming_anime_metadata()
