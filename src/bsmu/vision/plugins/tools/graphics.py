from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from bsmu.vision.plugins.tools import ViewerTool
from bsmu.vision.widgets.viewers.graphics import GraphicsViewer

if TYPE_CHECKING:
    from bsmu.vision.plugins.tools import ViewerToolSettings
    from bsmu.vision.plugins.undo import UndoManager

GraphicsViewerT = TypeVar('GraphicsViewerT', bound=GraphicsViewer)


class GraphicsViewerTool(ViewerTool[GraphicsViewerT]):
    viewer_type: type[GraphicsViewer] = GraphicsViewer

    def __init__(self, viewer: GraphicsViewerT, undo_manager: UndoManager, settings: ViewerToolSettings):
        super().__init__(viewer, undo_manager, settings)
