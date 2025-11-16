from typing import List

from src.types import Airport, AirportKind


def filter_airports(airports: List[Airport]) -> List[Airport]:
    """
    Remove irrelevant airports such as heliports.
    """
    kind_ignore_list = (
        AirportKind.HELIPORT_MILITARY.name,
        AirportKind.HELIPORT_CIVIL.name,
        AirportKind.AERODROME_CLOSED.name,
        AirportKind.AIRFIELD_WATER.name,
    )

    def _is_of_interest(airport: Airport) -> bool:
        return airport["kind"] not in kind_ignore_list

    return list(filter(_is_of_interest, airports))


def _airport_changed(new: Airport, old: Airport) -> bool:
    """
    Returns True if there is changed OpenAIP information
    in the new airport compared to the old one.
    """
    assert new["openaip_id"] == old["openaip_id"]
    return (
        new["openaip_name"] == old["openaip_name"]
        and new["kind"] == old["kind"]
        and new["longitude"] == old["longitude"]
        and new["latitude"] == old["latitude"]
        and new["elevation"] == old["elevation"]
        and new["icao"] == old["icao"]
        and new["radio_frequency"] == old["radio_frequency"]
        and new["radio_type"] == old["radio_type"]
        and new["radio_description"] == old["radio_description"]
        and new["rwy_name"] == old["rwy_name"]
        and new["rwy_sfc"] == old["rwy_sfc"]
        and new["rwy_direction"] == old["rwy_direction"]
        and new["rwy_length"] == old["rwy_length"]
        and new["rwy_width"] == old["rwy_width"]
    )


def merge_airports(existing: List[Airport], remote: List[Airport]) -> List[Airport]:
    """
    Add all airports from the remote which do not yet exist (check by openaip_id).
    Replace airports where the OpenAIP data has chagend, resetting the WeGlide derived data except for `weglide_name`.
    Returns the merged airport list.
    """
    merged = list(existing)

    for remote_airport in remote:
        existing_airport = next(
            (
                airport
                for airport in merged
                if airport["openaip_id"] == remote_airport["openaip_id"]
            ),
            None,
        )
        if existing_airport is None:
            merged.append(remote_airport)
        elif _airport_changed(remote_airport, existing_airport):
            # Losing WeGlide specific data except for `weglide_name` on replace.
            remote_airport["weglide_name"] = existing_airport["weglide_name"]
            existing_airport = remote_airport

    return merged


def sort_airports(airports: List[Airport]) -> List[Airport]:
    """
    Sort a list of airports by weglide_id ascending
    with None values moved to the end.
    """
    return sorted(
        airports,
        key=lambda airport: (
            airport["weglide_id"] is None,
            airport["weglide_id"] or float("inf"),
        ),
    )
