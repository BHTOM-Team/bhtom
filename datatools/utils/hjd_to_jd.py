import numpy as np
from astropy import time, coordinates as coord, units as u
from astropy.coordinates.errors import UnknownSiteException
from scipy.optimize import least_squares
import logging


logger = logging.getLogger(__name__)


def hjd_to_jd(hjd: float,
              ra, dec,
              ra_unit=u.deg,
              location_name: str = 'greenwich') -> float:
    '''
        Returns MJD corresponding to the given HJD
        with the heliocentric correction's precision up to 1e-06 (when no Earth Location is provided)
    '''
    try:
        target_location: coord.SkyCoord = coord.SkyCoord(ra=ra,
                                                         dec=dec,
                                                         unit=(ra_unit, ra_unit))
        try:
            location: coord.EarthLocation = coord.EarthLocation.of_site(location_name)
        except UnknownSiteException:
            location: coord.EarthLocation = coord.EarthLocation.of_site('greenwich')

        def helio_corr(mjd: float) -> float:
            times: time.Time = time.Time(mjd, format='jd', scale='utc', location=location)
            return times.light_travel_time(target_location, 'heliocentric').value

        def hjd_guess_diff(jd: np.array):
            hjd_guess = jd[0] + helio_corr(jd[0])
            return abs(hjd_guess - hjd)

        optim_mjd = least_squares(hjd_guess_diff, np.array([hjd]))
        return optim_mjd.x[0]
    except Exception as e:
        logger.error(f'[HJD TO JD CONVERSION] Error while converting HJD {hjd}: {e}')
        return time.Time(hjd, format='jd', scale='utc', location='greenwich').jd
