from tom_targets.models import Target
import logging
from typing import Optional


logger: logging.Logger = logging.getLogger(__name__)


def update_last_jd(target: Target,
                   maglast: Optional[float] = None,
                   jdmax: Optional[float] = None):
    jdlast: float = jdmax

    try:
        previousjd = target.extra_fields.get('jdlastobs')

        if maglast:
            target.save(extras={'maglast': maglast})
            logger.debug(f'Saving new maglast for {target}: {maglast}')

        if jdlast and (previousjd is None or jdlast > previousjd):
            target.save(extras={'jdlastobs': jdlast})
            logger.debug(f'Saving new jdlast for {target}: {jdlast}')
    except Exception as e:
        logger.error(f'Error while updating last JD for {target}: {e}')
