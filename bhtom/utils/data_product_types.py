from enum import auto, Enum


class DataProductType(Enum):
    PHOTOMETRY_CPCS = auto()
    FITS_FILE = auto()
    SPECTROSCOPY = auto()
    PHOTOMETRY = auto()

    def __eq__(self, other):
        return self.name.lower() == other.lower()
