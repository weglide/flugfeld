import csv
import json
import logging
import os
import signal
from time import sleep
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
NOMINATIM_ENDPOINT_URL = "https://nominatim.openstreetmap.org/reverse"
WEGLIDE_ENDPOINT_URL = "https://api.weglide.org/v1/airport"
CONTINENTS = "geo/continents.json"
COUNTRIES = "geo/countries.json"


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


def _format_name(name: str) -> str:
    return (
        name
        # Remove "Airport" variants from name.
        .replace("Airport", "")
        # Remove "Airpark" variants from name.
        .replace("Airpark", "")
        .replace("Air Park", "")
        # Remove "Airfield" variants from name.
        .replace("Airfield", "")
        .replace("Air Field", "")
        .replace("Field", "")
        # Remove "Airstrip" variants from name.
        .replace("Airstrip", "")
        .replace("Air Strip", "")
        .replace("Landing Strip", "")
        .replace("Strip", "")
        # Remove other airport synonyms from name.
        .replace("Ultralightport", "")
        .replace("Stolport", "")
        # Remove escape slashes from /Private/.
        .replace("/Private/", "Private")
        # No title case for " And ".
        .replace(" And ", " and ")
        # Fix double spaces.
        .replace("  ", " ")
        # Trim whitespace.
        .strip()
    )


def assign_weglide_name(airports: List[Airport]) -> List[Airport]:
    """
    Convert the OpenAIP name to title case for the WeGlide name.
    Does not overwrite existing names but does clean them.
    """
    # Clone list before modifying.
    airports = list(airports)
    for airport in airports:
        if airport["weglide_name"] is None:
            # Derive from OpenAIP Name.
            airport["weglide_name"] = airport["openaip_name"].title()
        # Adjust name.
        airport["weglide_name"] = _format_name(airport["weglide_name"])

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


def _new_zealand_region(airport: Airport) -> str:
    """
    Get North- or South Island region of New Zealand airport based on coordinates.
    """
    assert airport["region"] == "NZ"
    if (
        airport["longitude"] > 165.410156
        and airport["longitude"] < 174.495850
        and airport["latitude"] > -48.389419
        and airport["latitude"] < -40.171149
    ):
        return "NZ-S"  # South Island
    else:
        return "NZ-N"  # North Island


def _get_airport_region(airport: Airport) -> str:
    """
    Makes a reverse geocoding request to OpenStreetMaps Nominatim service.
    Requests per second should be limited to 1.
    Send informative User-Agent header.
    """
    assert len(airport["region"]) == 2

    # Special case for New Zealand
    # for which North/South Island is used instead of regions.
    if airport["region"] == "NZ":
        return _new_zealand_region(airport)

    params = {
        "lon": airport["longitude"],
        "lat": airport["latitude"],
        "format": "json",
        "zoom": 15,
    }
    headers = {"User-Agent": "WeGlide/1.0 Match airport to country and region"}
    response = requests.get(NOMINATIM_ENDPOINT_URL, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()
    address = data.get("address", {})
    nominatim_region = address.get("ISO3166-2-lvl4") or address.get("ISO3166-2-lvl6")
    assert response.status_code == 200, (
        f"Failed request for region (status code {response.status_code}) for {airport['weglide_name']}. Please try again. \n {response.url}"
    )
    assert nominatim_region is not None, (
        f"Could not find region for {airport['weglide_name']}. Please add manually. \n {response.url}"
    )
    assert nominatim_region[:2] == airport["region"], (
        f"Found region country ({nominatim_region}) differs from existing one ({airport['region']}) for {airport['weglide_name']}. Please verify manually. \n {response.url}"
    )
    return nominatim_region


def _missing_region_airport_indices(airports: List[Airport]) -> List[int]:
    """
    Search in countries.json file for all countries we need regions for.
    Only regions that are searchable on WeGlide need to be added.
    Returns a list of airport indices which do not yet have a region but need one.
    """
    missing_regions: List[int] = []  # List of indices of airports missing a region.
    with open(COUNTRIES) as json_file:
        continents = json.load(json_file).get("data")
        for i in range(len(airports)):
            country = airports[i]["region"]
            continent = airports[i]["continent"]
            if len(country) != 2:
                continue  # Already has a region specified.

            found_continent = continents.get(continent)
            if found_continent is None:
                continue  # Continent not in the countries.json list.

            found_country = found_continent["regions"].get(country)
            if found_country is None:
                continue  # Country not in the countries.json list.

            if "regions" in found_country:
                missing_regions.append(i)

    return missing_regions


def assign_region(airports: List[Airport]) -> List[Airport]:
    """
    Add region to country string (append separated by dash)
    for countries with regions specified in countries.json.
    Region is reverse geocoded by coordinates because it is not present in OpenAIP.
    Overwrites existing region string if there should be a more detailed one.
    """
    # Clone list before modifying.
    airports = list(airports)
    missing_regions = _missing_region_airport_indices(airports)
    for i in range(len(missing_regions)):
        missing_airport = airports[missing_regions[i]]
        nominatim_region = _get_airport_region(missing_airport)
        missing_airport["region"] = nominatim_region
        logger.info(
            f"Update region {i + 1}/{len(missing_regions)} to {nominatim_region} for {missing_airport['weglide_name']}."
        )
        # Intermediate save in case script or api have problems.
        write_airports_to_csv(airports)
        # Sleep for responsible API usage.
        # sleep(1)

    return airports


def _get_airport_launches(airport: Airport) -> int | None:
    """
    Request airport information from WeGlide and extract number of launches.
    Returns None when airport does not (yet) exist on WeGlide or on error.
    """
    assert airport["weglide_id"] is not None

    headers = {"User-Agent": "WeGlide/1.0 Airport launches"}
    url = f"{WEGLIDE_ENDPOINT_URL}/{airport['weglide_id']}"
    response = requests.get(url, headers=headers)
    data = response.json()
    launches = data.get("stats", {}).get("count")
    assert response.status_code == 200 or response.status_code == 404, (
        f"Failed request for launches (status code {response.status_code}) for {airport['weglide_name']}. Please try again. \n {response.url}"
    )
    return launches


def assign_launches(airports: List[Airport], force=False) -> List[Airport]:
    """
    Assign the number of glider launches to each aiport.
    Fetched from WeGlide API and used for reign calculation.
    Overwrites existing launch number and None if airport could not be found on WeGlide.
    """
    # Clone list before modifying.
    airports = list(airports)

    for airport in airports:
        if not force and airport["launches"] is not None:
            continue  # Do not update existing values.

        name = airport["weglide_name"]
        launches = _get_airport_launches(airport)
        if launches is not None:
            airport["launches"] = launches
            logger.info(f"Added {launches} launches to {name}.")
            # Intermediate save in case script or api have problems.
            write_airports_to_csv(airports)
        else:
            logger.info(f"Skipped launches for {name} (not found on WeGlide).")

        # Sleep for responsible API usage.
        sleep(0.2)

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

    # Prevent keyboard interruption of script during file write.
    original_sigint_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    # print(f"Writing {len(airports)} airports to {AIRPORT_CSV}...")

    with open(AIRPORT_CSV, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(airports)

    signal.signal(signal.SIGINT, original_sigint_handler)
    # print("Wrote airports to csv.")


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
    api_key = os.environ.get("OPENAIP_API_KEY")

    # Read data.
    # remote_airports = download_airports(api_key)
    # remote_airports = filter_airports(remote_airports)
    remote_airports = []
    existing_airports = read_airports_from_csv()
    airports = merge_airports(existing_airports, remote_airports)
    airports = sort_airports(airports)

    # Augment data.
    airports = assign_weglide_id(airports)
    airports = assign_weglide_name(airports)
    airports = assign_continent(airports)
    airports = assign_timezone(airports)
    airports = assign_region(airports)
    airports = assign_launches(airports, force=False)
    # airports = assign_reign(airports)

    # Write data.
    write_airports_to_csv(airports)
    write_airports_to_geojson(airports)
