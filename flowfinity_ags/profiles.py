from copy import deepcopy

from .datasets import BASE_DATASET_SPECS


def get_profile(profile_name: str):
    specs = deepcopy(BASE_DATASET_SPECS)

    if profile_name == "AGS 4.0 compact":
        return "4.0", specs

    if profile_name == "AGS 4.0.4 compact":
        return "4.0.4", specs

    if profile_name == "AGS 4.1 compact":
        return "4.1", specs

    if profile_name == "AGS 4.2 compact":
        return "4.2", specs

    return "4.0", specs


AGS_PROFILE_OPTIONS = [
    "AGS 4.0 compact",
    "AGS 4.0.4 compact",
    "AGS 4.1 compact",
    "AGS 4.2 compact",
]
