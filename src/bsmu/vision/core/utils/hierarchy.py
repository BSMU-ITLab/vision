from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Sequence


class HierarchyUtils:
    @staticmethod
    def inheritance_hierarchy(cls: type, base_cls: type, include_base_cls: bool = True) -> Sequence[type]:
        """
        Returns the sequence of classes representing the inheritance hierarchy
        from the given class up to and optionally including the specified base class.
        """
        mro = cls.mro()
        base_cls_index = mro.index(base_cls)
        last_cls_index = base_cls_index + 1 if include_base_cls else base_cls_index
        return mro[:last_cls_index]
