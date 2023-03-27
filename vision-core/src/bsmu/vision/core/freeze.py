import sys


def is_app_frozen() -> bool:
    """
    :return: True, if the application is frozen into *.exe
    """
    return getattr(sys, 'frozen', False)
