from typing import List

from src.types import Airport


def assign_weglide_id(airports: List[Airport]) -> List[Airport]:
    """
    Add auto incrementing WeGlide IDs to all airports missing one.
    Does not overwrite existing IDs.
    """
    # Clone list before modifying.
    airports = list(airports)
    max_existing_id = max(
        (
            weglide_id
            for airport in airports
            if (weglide_id := airport.get("weglide_id")) is not None
        ),
        default=0,
    )
    for airport in airports:
        if airport["weglide_id"] is None:
            max_existing_id = max_existing_id + 1
            airport["weglide_id"] = max_existing_id

    return airports
