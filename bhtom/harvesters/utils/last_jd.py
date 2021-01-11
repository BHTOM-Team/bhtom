from tom_targets.models import Target
import logging


logger: logging.Logger = logging.getLogger(__name__)


def update_last_jd(target: Target,
                   maglast: float = 0.0,
                   jdmax: float = 0.0):
    jdlast: float = jdmax
    previousjd: float = 0.0

    try:
        previousjd = float(target.targetextra_set.get(key='jdlastobs').value)
        target.save(extras={'maglast': maglast})
    except Exception as e:
        logger.error(f'Error while updating last JD for {target}: {e}')
    if jdlast > previousjd:
        target.save(extras={'jdlastobs': jdlast})
        logger.debug(f'Saving new jdlast for {target}: {jdlast}')
