from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar('T')


class HandleRegistry(Generic[T]):
    """
    Registry mapping auto-incrementing integer handles to objects.

    Handles provide stable logical references that survive object recreation,
    making them ideal for undo/redo commands and serialization.
    """

    def __init__(self):
        self._next_handle: int = 1
        self._handle_to_obj: dict[int, T] = {}
        self._obj_to_handle: dict[T, int] = {}

    def register(self, obj: T, handle: int | None = None) -> int:
        """
        Register an object and return its handle.

        - handle=None: Auto-assigns. If already registered, returns existing handle (idempotent).
        - handle=int: Claims/reassigns. Safely overrides any auto-handle.
        """
        if handle is None:
            # Idempotent auto-assign
            if (existing_handle := self._obj_to_handle.get(obj)) is not None:
                return existing_handle

            handle = self._next_handle
            self._next_handle += 1
        else:
            # Claim mode
            if (existing_obj := self._handle_to_obj.get(handle)) is not None and existing_obj is not obj:
                raise ValueError(f'Handle {handle} is already claimed by another object: {existing_obj}.')

            # Remove old auto-handle before claiming new one
            old_handle = self._obj_to_handle.pop(obj, None)
            if old_handle is not None:
                self._handle_to_obj.pop(old_handle, None)

        self._handle_to_obj[handle] = obj
        self._obj_to_handle[obj] = handle
        return handle

    def unregister(self, handle: int) -> None:
        """Remove an object from the registry by its handle (if still alive)."""
        obj = self._handle_to_obj.pop(handle, None)
        if obj is not None:
            self._obj_to_handle.pop(obj, None)

    def resolve(self, handle: int) -> T | None:
        """Return the object for handle, or None if missing/collected."""
        return self._handle_to_obj.get(handle)

    def get_handle(self, obj: T) -> int | None:
        """Return the handle of a live registered object, or None."""
        return self._obj_to_handle.get(obj)

    def __contains__(self, handle: int) -> bool:
        """Check if handle refers to a currently alive object."""
        return handle in self._handle_to_obj

    def __len__(self) -> int:
        """Number of currently alive registered objects."""
        return len(self._handle_to_obj)
