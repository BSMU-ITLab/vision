import abc

from PySide6.QtCore import QObject


class QABCMeta(type(QObject), abc.ABCMeta):
    pass
