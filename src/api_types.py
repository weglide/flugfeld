import enum
from typing import Optional, TypedDict


class AirportKind(int, enum.Enum):
    """
    Kind of the airport / what it is used for.
    Some of the kinds are not interesting for us such as heliports.
    https://docs.openaip.net/#/Airports/get_airports
    """

    AIRPORT = 0  # Airport (civil/military)
    GLIDER_SITE = 1  # Glider Site
    AIRFIELD_CIVIL = 2  # Airfield Civil
    INTERNATIONAL = 3  # International Airport
    HELIPORT_MILITARY = 4  # Heliport Military
    MILITARY_AERODROME = 5  # Military Aerodrome
    UL_FLYING_SITE = 6  # Ultra Light Flying Site
    HELIPORT_CIVIL = 7  # Heliport Civil
    AERODROME_CLOSED = 8  # Aerodrome Closed
    AIRPORT_IFR = 9  # Airport resp. Airfield IFR
    AIRFIELD_WATER = 10  # Airfield Water
    LANDING_STRIP = 11  # Landing Strip
    AGRICULTURAL_STRIP = 12  # Agricultural Landing Strip
    ALTIPORT = 13  # Altiport


class RadioType(int, enum.Enum):
    """
    Usage type for a radio frequency.
    """

    Approach = 0
    APRON = 1
    Arrival = 2
    Center = 3
    CTAF = 4
    Delivery = 5
    Departure = 6
    FIS = 7
    Gliding = 8
    Ground = 9
    Info = 10
    Multicom = 11
    Unicom = 12
    Radar = 13
    Tower = 14
    ATIS = 15
    Radio = 16
    Other = 17
    AIRMET = 18
    AWOS = 19
    Lights = 20
    VOLMET = 21
    Unknown = 22


class RunwaySurface(int, enum.Enum):
    """
    Type of the runway surface material.
    """

    Asphalt = 0
    Concrete = 1
    Grass = 2
    Sand = 3
    Water = 4
    EarthCement = 5
    Brick = 6
    MacadamOrTarmac = 7
    Stone = 8
    Coral = 9
    Clay = 10
    Laterite = 11
    Gravel = 12
    Earth = 13
    Ice = 14
    Snow = 15
    ProtectiveLaminate = 16
    Metal = 17
    LandingMatPortableSystem = 18
    PiercedSteelPlanking = 19
    Wood = 20
    NonBituminousMix = 21
    Unknown = 22


class Airport(TypedDict):
    """
    All possible airport information for CSV.
    """

    weglide_id: Optional[
        int
    ]  # OpenAIP changed their IDs from int to hashes, map it for backwards compatibility.
    openaip_id: str
    weglide_name: Optional[
        str
    ]  # WeGlide name contains non-ANSI characters and better casing.
    openaip_name: str
    kind: str  # Name from AirportKind enum.
    longitude: float
    latitude: float
    elevation: int  # MSL in meter.
    region: str  # Two letter country code with optional region code separated by a dash. E.g. DE-BY for Bavaria, US-OR for Oregon or CH for Switzerland.
    continent: (
        str  # Two letter continent code. E.g. NA for North America or EU for Europe.
    )
    timezone: Optional[str]
    launches: Optional[int]  # Number of total glider launches done from this Airport.
    reign: Optional[
        int
    ]  # Importance score relative to nearby airports based on number of glider launches.
    icao: Optional[str]  # ICAO code for larger airports.
    radio_frequency: Optional[str]  # E.g. "126.880"
    radio_type: Optional[str]  # Name from RadioType enum.
    radio_description: Optional[str]
    rwy_name: Optional[str]
    rwy_sfc: Optional[str]  # Name from RunwaySurface enum.
    rwy_direction: Optional[int]  # in degree.
    rwy_length: Optional[int]  # in meter.
    rwy_width: Optional[int]  # in meter.
