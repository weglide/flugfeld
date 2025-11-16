import csv
import signal
from typing import List

from src.logger import logger
from src.types import Airport

AIRPORT_CSV = "airport.csv"


def read_airports() -> List[Airport]:
    """
    Read airports from a csv file.
    """
    airports: List[Airport] = []

    logger.info(f"Reading airports from {AIRPORT_CSV}...")
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

    logger.info(f"Read {len(airports)} airports from csv.")
    return airports


def write_airports(airports: List[Airport]) -> None:
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
    # logger.info(f"Writing {len(airports)} airports to {AIRPORT_CSV}...")

    with open(AIRPORT_CSV, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(airports)

    signal.signal(signal.SIGINT, original_sigint_handler)
    # logger.info("Wrote airports to csv.")
