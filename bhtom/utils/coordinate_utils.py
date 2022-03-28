from datetime import datetime

from astropy import units as u
from astropy.coordinates import get_sun, SkyCoord
from astropy.time import Time
from tom_targets.models import Target


def update_sun_separation(target: Target):
    """
    Update the sun separation using astropy
    @param target: Observation target
    """
    sun_pos = get_sun(Time(datetime.utcnow()))
    obj_pos = SkyCoord(target.ra, target.dec, unit=u.deg)
    Sun_sep = sun_pos.separation(obj_pos).deg
    target.save(extras={'Sun_separation': Sun_sep})
    print("DEBUG: new Sun separation: ", Sun_sep)


def fill_galactic_coordinates(target: Target) -> Target:
    """
    Automatically calculate galactic coordinates for a target
    (if they aren't already filled in), using ra and dec
    @param target: Observation target
    @return: Observation target (changed in-place)
    """

    # If at least one of ra and dec is unfilled, return without changing
    # (there is nothing to calculate basing on)
    if not target.ra or not target.dec:
        return target

    # If the galactic coordinates are filled in, return without changing
    if target.galactic_lat and target.galactic_lng:
        return target

    coordinates: SkyCoord = SkyCoord(ra=target.ra,
                                     dec=target.dec,
                                     unit='deg')
    target.galactic_lat = coordinates.galactic.b.degree
    target.galactic_lng = coordinates.galactic.l.degree
    return target
