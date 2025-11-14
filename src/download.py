import csv
import json
import logging
import os
from typing import Any, List, Optional

import numpy as np
import requests
from dotenv import load_dotenv
from geojson import Feature, FeatureCollection, dump
from geojson import Point as GeoJsonPoint
from scipy.spatial.distance import cdist
from timezonefinder import TimezoneFinder

from src.api_types import (
    Airport,
    AirportKind,
    RadioType,
    RunwaySurface,
)

WGS_84_SRID: int = 4326
EARTH_RADIUS_KM: float = 6371.0
METER_PER_FEET: float = 0.3048

AIRPORT_CSV = "airport.csv"
AIRPORT_GEOJSON = "airport.geojson"
OPENAIP_ENDPOINT_URL = "https://api.core.openaip.net/api/airports"
CONTINENTS = "geo/continents.json"


def _parse_openaip_airport(openaip_airport: Any) -> Airport:
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
        "continent": _find_continent(country),
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

    openaip_airports: list[Any] = []
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


def _find_continent(country: str) -> str:
    with open(CONTINENTS) as json_file:
        for k, v in json.load(json_file).items():
            if country in v:
                return k

        raise AssertionError(f"No continent found for country {country}")


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

    def is_of_interest(airport: Airport) -> bool:
        return airport["kind"] not in kind_ignore_list

    return list(filter(is_of_interest, airports))


def merge_airports(existing: List[Airport], remote: List[Airport]) -> List[Airport]:
    """
    Add all airports from the remote which do not yet exist (check by openaip_id).
    Returns the merged airport list.
    """
    merged_list = list(existing)
    existing_ids = {airport["openaip_id"] for airport in existing}

    for remote_airport in remote:
        if remote_airport["openaip_id"] not in existing_ids:
            merged_list.append(remote_airport)

    return merged_list


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


def assign_weglide_name(airports: List[Airport]) -> List[Airport]:
    """
    Convert the OpenAIP name to title case for the WeGlide name.
    Does not overwrite existing names.
    """
    # Clone list before modifying.
    airports = list(airports)
    for airport in airports:
        if airport["weglide_name"] is None:
            airport["weglide_name"] = airport["openaip_name"].title()

    return airports


def assign_region(airports: List[Airport]) -> List[Airport]:
    """
    TODO
    Add region to country string (append separated by dash) for selected countries.
    Region is reverse geocoded by coordinates because it is not present in OpenAIP.
    Overwrites existing region string.
    """
    # Clone list before modifying.
    airports = list(airports)

    return airports


def assign_continent(airports: List[Airport]) -> List[Airport]:
    """
    Add continent based on country part of the region (first two letters) to airports.
    Overwrites existing continent.
    """
    # Clone list before modifying.
    airports = list(airports)
    with open(CONTINENTS) as json_file:
        items = json.load(json_file).items()
        for airport in airports:
            country = airport["region"][:2]
            for continent, countries in items:
                if country in countries:
                    airport["continent"] = continent
                    break
            else:
                raise AssertionError(f"No continent found for country {country}.")

    return airports


def assign_timezone(airports: List[Airport]) -> List[Airport]:
    """
    Add timezone to airports by coordinates.
    Does override existing timezones.
    """
    # Clone list before modifying.
    airports = list(airports)
    tz = TimezoneFinder()
    for airport in airports:
        lng = airport["longitude"]
        lat = airport["latitude"]
        airport["timezone"] = tz.timezone_at(lng=lng, lat=lat)

    return airports


def assign_launches(airports: List[Airport]) -> List[Airport]:
    """
    TODO
    Assign the number of glider launches to each aiport.
    Fetched from WeGlide API and used for reign calculation.
    Overwrites existing launch number.
    """
    # Clone list before modifying.
    airports = list(airports)

    return airports


def assign_reign(airports: List[Airport]) -> List[Airport]:
    """
    Assign a reign for each airport in the given list.
    Reign is based on number of launches and distance to nearby airports.
    """
    # Clone list before modifying.
    airports = list(airports)

    lon = [a["longitude"] for a in airports]
    lat = [a["latitude"] for a in airports]
    lonlat = np.column_stack((np.array(lon), np.array(lat)))

    # Distance matrix between airports.
    lonlatrad = np.radians(lonlat)
    theta = np.cos(np.mean(lonlat[:, 1]))
    lonlatrad[:, 0] *= theta
    dist_matrix = cdist(lonlatrad, lonlatrad, "euclidean") * EARTH_RADIUS_KM

    # Start with a large reign for every airport.
    reign = [1000] * len(lonlat)

    # Build reign for each airport from distance matrix and number of launches.
    for i in range(len(lonlat)):
        for j in range(len(lonlat)):
            # Only traverse upper triangle.
            if j >= i:
                continue

            dist = dist_matrix[i, j]
            if dist >= max(reign[i], reign[j]):
                continue

            launches1 = airports[i]["launches"]
            assert launches1 is not None

            launches2 = airports[j]["launches"]
            assert launches2 is not None

            if launches1 >= launches2:
                if reign[j] > dist:
                    reign[j] = round(dist)
                continue

            if reign[i] > dist:
                reign[i] = round(dist)

    # Update the airport list with the reign.
    for i, r in enumerate(reign):
        airports[i]["reign"] = r

    return airports


def read_airports_from_csv() -> List[Airport]:
    """
    Read airports from a csv file.
    """
    airports: List[Airport] = []

    print(f"Reading airports from {AIRPORT_CSV}...")
    with open(AIRPORT_CSV, "r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            airport = Airport(
                weglide_id=int(row["weglide_id"]) if row["weglide_id"] else None,
                openaip_id=row["openaip_id"],
                weglide_name=row["weglide_name"] if row["weglide_name"] else None,
                openaip_name=row["openaip_name"],
                kind=row["kind"],
                longitude=float(row["longitude"]),
                latitude=float(row["latitude"]),
                elevation=int(row["elevation"]),
                region=row["region"],
                continent=row["continent"],
                timezone=row["timezone"],
                launches=int(row["launches"]) if row["launches"] else None,
                reign=int(row["reign"]) if row["reign"] else None,
                icao=row["icao"] if row["icao"] else None,
                radio_frequency=row["radio_frequency"]
                if row["radio_frequency"]
                else None,
                radio_type=row["radio_type"] if row["radio_type"] else None,
                radio_description=row["radio_description"]
                if row["radio_description"]
                else None,
                rwy_name=row["rwy_name"] if row["rwy_name"] else None,
                rwy_sfc=row["rwy_sfc"] if row["rwy_sfc"] else None,
                rwy_direction=int(row["rwy_direction"])
                if row["rwy_direction"]
                else None,
                rwy_length=int(row["rwy_length"]) if row["rwy_length"] else None,
                rwy_width=int(row["rwy_width"]) if row["rwy_width"] else None,
            )
            airports.append(airport)

    print(f"Read {len(airports)} airports from csv.")
    return airports


def write_airports_to_csv(airports: List[Airport]) -> None:
    """
    Write airports to csv file.
    """
    fieldnames = [
        "weglide_id",
        "openaip_id",
        "weglide_name",
        "openaip_name",
        "kind",
        "longitude",
        "latitude",
        "elevation",
        "region",
        "continent",
        "timezone",
        "launches",
        "reign",
        "icao",
        "radio_frequency",
        "radio_type",
        "radio_description",
        "rwy_name",
        "rwy_sfc",
        "rwy_direction",
        "rwy_length",
        "rwy_width",
    ]

    print(f"Writing {len(airports)} airports to {AIRPORT_CSV}...")
    with open(AIRPORT_CSV, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(airports)
    print("Wrote airports to csv.")


def _airport_to_feature(airport: Airport) -> Feature:
    """
    Convert an airport to a GeoJSON Feature.
    """
    geometry = GeoJsonPoint((airport["longitude"], airport["latitude"]))
    properties: dict[str, Any] = {
        "lng": airport["longitude"],
        "lat": airport["latitude"],
        "id": airport["weglide_id"],
        "openaip_id": airport["openaip_id"],
        "name": airport["weglide_name"],
        "openaip_name": airport["openaip_name"],
        "kind": airport["kind"],
        "region": airport["region"],
        "continent": airport["continent"],
        "launches": airport["launches"],
        "icao": airport["icao"],
        "reign": airport["reign"],
        "openaip_elevation": airport["elevation"],
        "elevation": airport["elevation"],
        "timezone": airport["timezone"],
        "radio_frequency": airport["radio_frequency"],
        "radio_type": airport["radio_type"],
        "radio_description": airport["radio_description"],
        "rwy_name": airport["rwy_name"],
        "rwy_sfc": airport["rwy_sfc"],
        "rwy_direction": airport["rwy_direction"],
        "rwy_length": airport["rwy_length"],
        "rwy_width": airport["rwy_width"],
    }
    return Feature(geometry=geometry, properties=properties)


def write_airports_to_geojson(airports: List[Airport]) -> None:
    """
    Write airports as GeoJSON Feature Collection to a file.
    """
    features = [_airport_to_feature(airport) for airport in airports]
    feature_collection = FeatureCollection(list(features))
    logger.info(f"Writing airports to {AIRPORT_GEOJSON}...")
    with open(AIRPORT_GEOJSON, "w") as f:
        dump(feature_collection, f, indent=4)
    logger.info("Wrote airports to geojson.")


if __name__ == "__main__":
    # Setup.
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)
    load_dotenv()
    api_key = os.environ["OPENAIP_API_KEY"]

    # Read data.
    remote_airports = download_airports(api_key)
    remote_airports = filter_airports(remote_airports)
    existing_airports = read_airports_from_csv()
    airports = merge_airports(existing_airports, remote_airports)
    airports = sort_airports(airports)

    # Augment data.
    airports = assign_weglide_id(airports)
    airports = assign_weglide_name(airports)
    airports = assign_region(airports)
    airports = assign_continent(airports)
    airports = assign_timezone(airports)
    airports = assign_launches(airports)
    # airports = assign_reign(airports)

    # Write data.
    write_airports_to_csv(airports)
    write_airports_to_geojson(airports)
