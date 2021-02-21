from typing import List

from astropy import time, coordinates as coord, units as u

from .utils.hjd_to_jd import hjd_to_jd


def isclose(a, b, rel_tol=1e-06, abs_tol=1e-06):
    return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)


def test_hjd_to_jd_hourangle_ra():
    target_coords: List[coord.SkyCoord] = [
        coord.SkyCoord("23:23:08.55", "+18:24:59.3", unit=(u.hourangle, u.deg), frame='icrs'),
        coord.SkyCoord("12:23:08.55", "+18:24:59.3", unit=(u.hourangle, u.deg), frame='icrs'),
        coord.SkyCoord("0:23:08.55", "+18:24:59.3", unit=(u.hourangle, u.deg), frame='icrs'),
        coord.SkyCoord("23:23:08.55", "+0:24:59.3", unit=(u.hourangle, u.deg), frame='icrs'),
        coord.SkyCoord("12:23:08.55", "+0:24:59.3", unit=(u.hourangle, u.deg), frame='icrs'),
        coord.SkyCoord("0:23:08.55", "+0:24:59.3", unit=(u.hourangle, u.deg), frame='icrs'),
        coord.SkyCoord("23:23:08.55", "-18:24:59.3", unit=(u.hourangle, u.deg), frame='icrs'),
        coord.SkyCoord("12:23:08.55", "-18:24:59.3", unit=(u.hourangle, u.deg), frame='icrs'),
        coord.SkyCoord("0:23:08.55", "-18:24:59.3", unit=(u.hourangle, u.deg), frame='icrs'),
    ]

    jds: List[float] = [2458849.50000000,
                        2458853.50000000,
                        2458858.50000000,
                        2458863.50000000,
                        2458850.00000000,
                        2458850.04166667]

    greenwich = coord.EarthLocation.of_site('greenwich')

    def hjd_for_jd(date: float, target: coord.SkyCoord) -> float:
        times = time.Time([date], format='jd', scale='utc', location=greenwich)
        ltt_helio = times.light_travel_time(target, 'heliocentric')
        return date + ltt_helio.value

    for target in target_coords:
        for jd in jds:
            hjd = hjd_for_jd(jd, target)
            assert isclose(hjd_to_jd(hjd[0], ra=target.ra, dec=target.dec, ra_unit=u.hourangle), jd)


def test_hjd_to_mjd_degree_coords():
    target_coords: List[coord.SkyCoord] = [
        coord.SkyCoord(288.0, 88.0, unit=(u.deg, u.deg), frame='icrs'),
        coord.SkyCoord(130.0, 88.0, unit=(u.deg, u.deg), frame='icrs'),
        coord.SkyCoord(0.0, 88.0, unit=(u.deg, u.deg), frame='icrs'),
        coord.SkyCoord(288.0, 0.0, unit=(u.deg, u.deg), frame='icrs'),
        coord.SkyCoord(130.0, 0.0, unit=(u.deg, u.deg), frame='icrs'),
        coord.SkyCoord(0.0, 0.0, unit=(u.deg, u.deg), frame='icrs'),
        coord.SkyCoord(288.0, -76.0, unit=(u.deg, u.deg), frame='icrs'),
        coord.SkyCoord(124.0, -76.0, unit=(u.deg, u.deg), frame='icrs'),
        coord.SkyCoord(0.0, -76.0, unit=(u.deg, u.deg), frame='icrs'),
    ]

    jds: List[float] = [2458849.50000000,
                        2458853.50000000,
                        2458858.50000000,
                        2458863.50000000,
                        2458850.00000000,
                        2458850.04166667]

    greenwich = coord.EarthLocation.of_site('greenwich')

    def hjd_for_jd(date: float, target: coord.SkyCoord) -> float:
        times = time.Time([date], format='jd', scale='utc', location=greenwich)
        ltt_helio = times.light_travel_time(target, 'heliocentric')
        return date + ltt_helio.value

    for target in target_coords:
        for jd in jds:
            hjd = hjd_for_jd(jd, target)
            assert isclose(hjd_to_jd(hjd[0], ra=target.ra, dec=target.dec, ra_unit=u.hourangle), jd)
