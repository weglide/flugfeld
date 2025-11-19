from typing import Any, List

from geojson import Feature, FeatureCollection, Point, dump

from .logger import logger
from .types import Airport

AIRPORT_GEOJSON = "airport.geojson"


def _airport_to_feature(airport: Airport) -> Feature:
    """
    Convert an airport to a GeoJSON Feature.
    """
    geometry = Point((airport["longitude"], airport["latitude"]))
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


def write_airports(airports: List[Airport]) -> None:
    """
    Write airports as GeoJSON Feature Collection to a file.
    """
    features = [_airport_to_feature(airport) for airport in airports]
    feature_collection = FeatureCollection(list(features))
    logger.info(f"Writing airports to {AIRPORT_GEOJSON}...")
    with open(AIRPORT_GEOJSON, "w") as f:
        dump(feature_collection, f, indent=4)
    logger.info("Wrote airports to geojson.")
