from typing import List

from src.types import Airport


def format_name(original: str) -> str:
    """
    Format the title case OpenAIP name into something less verbose.
    Does not fix language specific special characters.
    """
    formatted = (
        original
        # Remove "Airport" variants from name.
        .replace("Airport", "")
        .replace("Airpor", "")
        .replace("Airpo", "")
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
        # Remove "Ultralight" variants from name.
        .replace("Ultralightport", "")
        .replace("Ultralight", "")
        .replace("Ultraligh", "")
        # Remove other airport synonyms from name.
        .replace("Stolport", "")
        .replace("Aviation", "")
        .replace("Aerodrome", "")
        .replace("Gliderport", "")
        # Remove escape slashes from /Private/.
        .replace("/Private/", "Private")
        # "The" is not necessary.
        .replace(" The ", "")
        # No title case for " And ".
        .replace(" And ", " and ")
        # French stuff.
        .replace(" L ", " l'")
        .replace(" D ", " d'")
        .replace(" Et ", " et ")
        .replace(" En ", " en ")
        .replace(" Des ", " des ")
        .replace(" De ", " de ")
        .replace(" Du ", " du ")
        .replace(" La ", " la ")
        .replace(" Le ", " le ")
        .replace(" Les ", " les ")
        .replace(" Sur ", " sur ")
        # Dashes are preferred over slashes.
        .replace(" / ", " - ")
        # Fix double spaces.
        .replace("  ", " ")
        # Trim whitespace.
        .strip()
    )
    if len(formatted) > 2:
        return formatted
    else:
        return original


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
        airport["weglide_name"] = format_name(airport["weglide_name"])

    return airports
