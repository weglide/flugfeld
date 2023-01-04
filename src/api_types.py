import enum


class OpenAipKind(int, enum.Enum):
    AIRPORT = 0
    GLIDER_SITE = 1
    AIRFIELD_CIVIL = 2
    INTERNATIONAL = 3
    HELIPORT_MILITARY = 4
    MILITARY_AERODROME = 5
    UL_FLYING_SITE = 6
    HELIPORT_CIVIL = 7
    AERODROME_CLOSED = 8
    AIRPORT_IFR = 9
    AIRFIELD_WATER = 10
    LANDING_STRIP = 11
    AGRICULTURAL_STRIP = 12
    ALTIPORT = 13


class FrequencyKind(int, enum.Enum):
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


class RunwayComposition(int, enum.Enum):
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
