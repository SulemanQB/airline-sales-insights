"""Static reference data and simulation parameters.

Everything here is fictional. Southern Cross Air (SCA) is an invented carrier;
cost rates are illustrative round numbers, not any real contract.
"""
from datetime import date

AIRLINE = "Southern Cross Air"
START = date(2024, 7, 1)
END = date(2026, 6, 30)  # two full financial years (FY25, FY26)
SEED = 20261016

# route_code, origin, dest, haul, distance_km, daily_seats, base_fare_aud, bookings_per_day
ROUTES = [
    ("SYD-MEL", "SYD", "MEL", "Domestic", 706, 2400, 165, 70),
    ("SYD-BNE", "SYD", "BNE", "Domestic", 750, 1900, 170, 52),
    ("MEL-BNE", "MEL", "BNE", "Domestic", 1380, 1200, 205, 30),
    ("SYD-PER", "SYD", "PER", "Domestic", 3290, 900, 390, 20),
    ("MEL-ADL", "MEL", "ADL", "Domestic", 650, 800, 150, 22),
    ("BNE-CNS", "BNE", "CNS", "Domestic", 1390, 700, 210, 17),
    ("SYD-OOL", "SYD", "OOL", "Domestic", 680, 600, 140, 16),
    ("SYD-AKL", "SYD", "AKL", "International", 2160, 700, 380, 15),
    ("MEL-SIN", "MEL", "SIN", "International", 6030, 560, 720, 13),
    ("SYD-NRT", "SYD", "NRT", "International", 7820, 480, 980, 10),
    ("SYD-LAX", "SYD", "LAX", "International", 12050, 450, 1450, 8),
    ("BNE-DPS", "BNE", "DPS", "International", 4600, 380, 560, 9),
]

# channel_code, channel, channel_group, connection, commission_pct, fee_per_segment_aud
CHANNELS = [
    ("WEB", "Direct Web", "Direct", "Direct", 0.012, 0.0),
    ("APP", "Direct App", "Direct", "Direct", 0.012, 0.0),
    ("TMC_GDS", "Travel Agent / TMC", "Indirect", "GDS", 0.010, 13.0),
    ("TMC_NDC", "Travel Agent / TMC", "Indirect", "NDC", 0.010, 3.5),
    ("OTA_GDS", "Online Travel Agency", "Indirect", "GDS", 0.060, 13.0),
    ("OTA_NDC", "Online Travel Agency", "Indirect", "NDC", 0.060, 3.5),
]

# fare_family, cabin, fare multiplier, ancillary attach base, refundable
FARES = [
    ("Starter", "Economy", 0.70, 0.55, False),
    ("Saver", "Economy", 1.00, 0.40, False),
    ("Flex", "Economy", 1.55, 0.25, True),
    ("Business", "Business", 3.40, 0.10, True),
    ("Business Flex", "Business", 4.20, 0.05, True),
]

POS = [("AU", "Australia", "Oceania"), ("NZ", "New Zealand", "Oceania"),
       ("US", "United States", "Americas"), ("JP", "Japan", "Asia"),
       ("SG", "Singapore", "Asia"), ("GB", "United Kingdom", "Europe"),
       ("ID", "Indonesia", "Asia")]

SEGMENTS = [("CORP", "Corporate"), ("LEIS", "Leisure")]

# Planted business stories (dates are inclusive)
STORY_NDC_START = date(2025, 3, 1)          # NDC migration programme begins
STORY_ROUTE = "MEL-SIN"                      # competitor capacity hits this route
STORY_ROUTE_SHOCK = date(2025, 10, 1)
STORY_APP_OUTAGE = (date(2026, 2, 9), date(2026, 2, 12))  # app release defect
