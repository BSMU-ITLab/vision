from __future__ import annotations

from PySide6.QtGui import QUndoCommand


class UndoCommand(QUndoCommand):
    _type_id: int = 0
    _next_type_id: int = 1

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        cls._type_id = UndoCommand._next_type_id  # every inherited class type should have unique ID
        UndoCommand._next_type_id += 1

    def __init__(self, text: str = '', parent: QUndoCommand = None):
        super().__init__(text, parent)

        # print(f'{self.__class__.__name__} id={self._type_id}')

    @classmethod
    def command_type_id(cls) -> int:
        return cls._type_id
