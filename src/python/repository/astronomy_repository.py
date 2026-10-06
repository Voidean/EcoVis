import math
from datetime import datetime

from pyglm import glm

from util.coordinate_constants import WORLD_UP

# Constants
RAD_PER_DEG = math.pi / 180.0
DEG_PER_RAD = 180.0 / math.pi
J2000_JD = 2451545.0  # Julian Date of epoch J2000.0 (Jan 1, 2000, 12:00 UTC)


def calculate_solar_declination_and_ascension(dt_utc: datetime):
    jd = date_to_julian_century(dt_utc)

    # Time in Julian Centuries from J2000.0
    t = (jd - J2000_JD) / 36525.0

    # --- Simplified Solar Coordinates (Right Ascension (α) and Declination (δ)) ---

    # 1. Geometric Mean Longitude of the Sun (l0, in degrees)
    l0 = (280.46646 + 36000.76983 * t + 0.0003032 * t ** 2) % 360.0
    if l0 < 0: l0 += 360.0

    # 2. Mean Anomaly of the Sun (m, in degrees)
    m = (357.52911 + 35999.05029 * t - 0.0001537 * t ** 2) % 360.0
    if m < 0: m += 360.0
    m_rad = m * RAD_PER_DEG

    # 3. Equation of Center (c, in degrees)
    c = (1.914602 - 0.004817 * t - 0.000014 * t ** 2) * math.sin(m_rad) + \
        (0.019993 - 0.000101 * t) * math.sin(2 * m_rad) + \
        0.000289 * math.sin(3 * m_rad)

    # 4. Sun's True Longitude (λ, in degrees)
    # Apparent Longitude is True Longitude (sol) with a small correction for nutation (ignored here)
    lambda_true = l0 + c

    # 5. Mean Obliquity of the Ecliptic (ε, in degrees) - Earth's axial tilt
    # A simplified formula is used for graphics accuracy
    epsilon = 23.43929 - 0.0130042 * t
    epsilon_rad = epsilon * RAD_PER_DEG

    # 6. Right Ascension (α) and Declination (δ)
    lambda_rad = lambda_true * RAD_PER_DEG

    sin_lambda = math.sin(lambda_rad)
    cos_lambda = math.cos(lambda_rad)

    # Declination (δ) - Angle above/below the equator
    declination_rad = math.asin(math.sin(epsilon_rad) * sin_lambda)

    # Right Ascension (α) - Angle along the equator (0-360)
    # The atan2 function correctly handles the quadrant
    right_ascension_rad = math.atan2(math.cos(epsilon_rad) * sin_lambda, cos_lambda)

    return declination_rad, right_ascension_rad


def calculate_greenwich_sidereal_time(dt_utc: datetime):
    # GMST (Greenwich Mean Sidereal Time in degrees at 0h UT on the given date)
    jd_midnight = math.floor(date_to_julian_century(dt_utc) - 0.5) + 0.5  # Julian Date at the previous midnight UT
    d_midnight = jd_midnight - J2000_JD  # Days since J2000.0 midnight

    # Simplified formula for GMST at 0h UT, avoiding TT/UT1 differences for graphics
    gmst_at_midnight_hr = (6.697374558 + 0.06570982441908 * d_midnight + 1.00273790935 * dt_utc.hour +
                           dt_utc.minute / 60.0 + dt_utc.second / 3600.0)

    # Convert to degrees (mod 360)
    gmst_at_midnight_deg = (gmst_at_midnight_hr * 15.0) % 360.0
    if gmst_at_midnight_deg < 0: gmst_at_midnight_deg += 360.0

    return gmst_at_midnight_deg


def calculate_sun_direction(dt_utc: datetime) -> glm.dvec3:
    """
    Calculates the unit vector pointing from the Earth's center to the Sun
    based on the time/date (UTC).
    """
    declination_rad, right_ascension_rad = calculate_solar_declination_and_ascension(dt_utc)
    gmst_deg = calculate_greenwich_sidereal_time(dt_utc)

    return convert_to_vector(right_ascension_rad, gmst_deg, declination_rad)


def calculate_lunar_declination_and_ascension(dt_utc: datetime):
    jd = date_to_julian_century(dt_utc)

    # Time in Julian Centuries from J2000.0
    t = (jd - J2000_JD) / 36525.0

    # --- 1. Calculate Moon's Mean Elements (in degrees) ---

    # Mean Longitude of the Moon (L')
    l_prime = (218.3164477 + 481267.88123421 * t - 0.0015786 * t ** 2 + t ** 3 / 538845.0 - t ** 4 / 65194000.0) % 360.0

    # Mean Anomaly of the Moon (m)
    m = (134.9634025 + 477198.8675803 * t + 0.0087784 * t ** 2 + t ** 3 / 69699.0 - t ** 4 / 14712000.0) % 360.0

    # Mean Anomaly of the Sun (m_sun) - needed for solar perturbation
    m_sun = (357.5291092 + 35999.0502909 * t - 0.0001536 * t ** 2 + t ** 3 / 24490000.0) % 360.0

    # Mean Longitude of the Moon's Ascending Node (n)
    n = (125.1228000 - 1934.1362891 * t + 0.0020754 * t ** 2 + t ** 3 / 467441.0 - t ** 4 / 60600000.0) % 360.0

    # Convert Mean Elements to Radians
    l_prime_rad = l_prime * RAD_PER_DEG
    m_rad = m * RAD_PER_DEG
    m_sun_rad = m_sun * RAD_PER_DEG
    n_rad = n * RAD_PER_DEG

    # --- 2. Perturbations and True Position (Moon's Ecliptic Longitude (λ) and Latitude (β)) ---

    # Ecliptic Longitude (λ, in radians)
    # This involves the main equation of center and major perturbation terms (Evection, Variation, etc.)
    lambda_rad = l_prime_rad + (6.2888 * math.sin(m_rad) + 1.258 * math.sin(2 * l_prime_rad - 2 * m_sun_rad) +
                                0.583 * math.sin(2 * (l_prime_rad - m_sun_rad)) + 0.213 * math.sin(
                m_sun_rad)) * RAD_PER_DEG

    # Ecliptic Latitude (β, in radians)
    # The tilt of the Moon's orbit relative to the ecliptic plane
    beta_rad = (5.128 * math.sin(lambda_rad - n_rad) + 0.280 * math.sin(m_rad + lambda_rad - n_rad)) * RAD_PER_DEG

    # --- 3. Conversion from Ecliptic to Equatorial Coordinates (RA and Dec) ---

    # Mean Obliquity of the Ecliptic (ε, in degrees) - Earth's axial tilt
    epsilon = 23.43929 - 0.0130042 * t
    epsilon_rad = epsilon * RAD_PER_DEG

    # Equatorial Coordinates (Right Ascension (α) and Declination (δ))
    # This is a standard coordinate transformation

    # Declination (δ, in radians)
    declination = math.asin(math.sin(beta_rad) * math.cos(epsilon_rad) +
                            math.cos(beta_rad) * math.sin(epsilon_rad) * math.sin(lambda_rad))

    # Right Ascension (α, in radians)
    # Using atan2 to get the correct quadrant
    numerator = math.cos(beta_rad) * math.sin(lambda_rad) * math.cos(epsilon_rad) - math.sin(beta_rad) * math.sin(
        epsilon_rad)
    denominator = math.cos(beta_rad) * math.cos(lambda_rad)
    ascension = math.atan2(numerator, denominator)
    if ascension < 0: ascension += 2 * math.pi  # Ensure positive RA (0 to 2pi)

    return declination, ascension


def calculate_moon_direction(dt_utc: datetime) -> glm.dvec3:
    """
    Calculates a rough unit vector pointing from the Earth's center to the Moon
    based on the time/date (UTC), using simplified, low-accuracy algorithms.
    """
    declination, ascension = calculate_lunar_declination_and_ascension(dt_utc)
    gmst_deg = calculate_greenwich_sidereal_time(dt_utc)

    return convert_to_vector(ascension, gmst_deg, declination)


def calculate_sky_rotation(dt_utc: datetime) -> glm.quat:
    """
    Calculates sky rotation based on the time/date (UTC).
    """
    gmst_deg = calculate_greenwich_sidereal_time(dt_utc)

    return glm.quat_cast(glm.rotate(glm.dmat4(1.0), -math.radians(gmst_deg), WORLD_UP))


def date_to_julian_century(dt_utc: datetime):
    # Time Conversion (UTC to Julian Date to Julian Centuries)
    # Python datetime.toordinal() gives days since 0001-01-01
    return dt_utc.toordinal() + 1721424.5 + (dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0) / 24.0


def convert_to_vector(ascension, gmst_deg, declination) -> glm.dvec3:
    # Calculate Hour Angle (H) for the Prime Meridian (H = GST - RA)
    ra_deg = ascension * DEG_PER_RAD
    h_deg = (gmst_deg - ra_deg)
    h_rad = h_deg * RAD_PER_DEG

    x = -math.cos(declination) * math.sin(h_rad)
    y = -math.cos(declination) * math.cos(h_rad)
    z = math.sin(declination)

    # The resulting vector is a unit vector pointing from Earth's center TO the celestial object.
    return glm.dvec3(x, y, z)
