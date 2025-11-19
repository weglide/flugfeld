from typing import List, Optional

import requests

from .logger import logger
from .types import Airport, AirportKind, OpenaipAirport, RadioType, RunwaySurface

OPENAIP_ENDPOINT_URL = "https://api.core.openaip.net/api/airports"


def _parse_openaip_airport(openaip_airport: OpenaipAirport) -> Airport:
    """
    Convert a raw OpenAIP airport JSON API response to our internal airport representation.
    Ignores Heliports and airports for which no timezone can be found.

    https://docs.openaip.net/#/Airports/get_airports
    """
    openaip_id = openaip_airport["_id"]
    kind = AirportKind(int(openaip_airport["type"])).name
    openaip_name = openaip_airport["name"]
    icao = openaip_airport.get("icaoCode")
    country = openaip_airport["country"]

    # Get info for main radio (fallback to first).
    radio_frequency: Optional[str] = None
    radio_type: Optional[str] = None
    radio_description: Optional[str] = None
    if len(openaip_airport.get("frequencies", [])) > 0:
        frequency = next(
            (f for f in openaip_airport["frequencies"] if f["primary"]),
            openaip_airport["frequencies"][0],
        )
        description = frequency.get("name")
        if description is not None:
            radio_description = description.title()
        radio_frequency = frequency["value"]
        radio_type = RadioType(int(frequency["type"])).name

    # Get info for main runway (fallback to first).
    rwy_name: Optional[str] = None
    rwy_sfc: Optional[str] = None
    rwy_direction: Optional[int] = None
    rwy_length: Optional[int] = None
    rwy_width: Optional[int] = None
    if len(openaip_airport.get("runways", [])) > 0:
        runway = next(
            (f for f in openaip_airport["runways"] if f["mainRunway"]),
            openaip_airport["runways"][0],
        )
        assert runway["dimension"]["length"]["unit"] == 0
        assert runway["dimension"]["width"]["unit"] == 0
        assert int(runway["trueHeading"]) <= 360
        rwy_name = runway["designator"]
        rwy_sfc = RunwaySurface(int(runway["surface"]["mainComposite"])).name
        rwy_direction = int(runway["trueHeading"])
        rwy_length = runway["dimension"]["length"]["value"]
        rwy_width = runway["dimension"]["width"]["value"]

    elevation = openaip_airport["elevation"]["value"]
    lon, lat = openaip_airport["geometry"]["coordinates"]
    assert openaip_airport["elevation"]["unit"] == 0

    return {
        "longitude": lon,
        "latitude": lat,
        "openaip_id": openaip_id,
        "weglide_id": None,
        "openaip_name": openaip_name,
        "weglide_name": None,
        "kind": kind,
        "region": country,
        "continent": None,
        "launches": None,
        "icao": icao,
        "reign": None,
        "elevation": elevation,
        "timezone": None,
        "radio_frequency": radio_frequency,
        "radio_type": radio_type,
        "radio_description": radio_description,
        "rwy_name": rwy_name,
        "rwy_sfc": rwy_sfc,
        "rwy_direction": rwy_direction,
        "rwy_length": rwy_length,
        "rwy_width": rwy_width,
    }


def download_airports(api_key: str | None) -> List[Airport]:
    """
    Request all airports from OpenAIP pagewise
    and convert them to our internal format.

    https://docs.openaip.net/#/Airports/get_airports
    """
    assert api_key is not None

    openaip_airports: list[OpenaipAirport] = []
    headers = {"x-openaip-api-key": api_key}
    response = requests.get(OPENAIP_ENDPOINT_URL, headers=headers)
    data = response.json()
    total_count = data["totalCount"]

    # Read page by page (1k entries each).
    logger.info(f"Downloading {total_count} airports from OpenAIP...")
    for i in range(1, 2 + (total_count // 1000)):
        response = requests.get(
            OPENAIP_ENDPOINT_URL, params={"page": i}, headers=headers
        )
        data = response.json()
        openaip_airports.extend(data["items"])
        logger.info(f"Downloaded {i * 1000}/{total_count} airports.")

    # Parse OpenAIP airports into internal representation.
    airports = [_parse_openaip_airport(a) for a in openaip_airports]

    return airports
