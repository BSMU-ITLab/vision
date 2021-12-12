import abc

from PySide2.QtCore import QObject


class QABCMeta(type(QObject), abc.ABCMeta):
    pass
