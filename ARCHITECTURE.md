# Architecture Overview

## Core Principles

- Model/View separation (using PySide signals)
- Layered data model with raster and vector support
- Extensible to plots and other viewers

## Plugin System

The application uses a **configuration-driven plugin architecture**.
Plugins are **explicitly listed in `App.conf.yaml`** and loaded at startup.
Each user profile (e.g., radiologist, pathologist) uses a **dedicated config file** enabling only relevant plugins,
so keeping the UI uncluttered and workflow-focused.

Each plugin can:
- Provide file readers, data visualizers, annotation tools, UI panels, and more
- Declare dependencies (ensuring correct initialization order)

## Key Classes

### Plugin Infrastructure

```python
class App(QObject):
    plugin_manager: PluginManager

class PluginManager(QObject):
    plugins: list[Plugin]

class Plugin(QObject): ...
class MdiLayoutPlugin(Plugin): ...
class FileDropperPlugin(Plugin): ...
class FileReaderPlugin(Plugin): ...
class DataVisualizerPlugin(Plugin): ...
class ViewerToolPlugin(Plugin): ...
class TaskStorageViewPlugin(Plugin): ...
```

### Model

#### Data

```python
class Data(QObject): ...
    path: Path | None
class Raster(Data):
    pixels: np.ndarray  # spatial grid values (2D, 3D, etc.)
    spatial_ndim: int  # e.g., 2 for 2D images: (H,W) or (H,W,C); 3 for volumes: (D,H,W) or (D,H,W,C)
    role: type[RasterRole] | None = None  # semantic role; if None, consumers inspect pixels to decide usage

    @classmethod
    def image(cls, pixels: np.ndarray) -> Raster:
        """Create a 2D image (any channel count: grayscale, RGB, RGBA, multispectral, etc.)."""
        return cls(pixels, spatial_ndim=2, role=ImageRole)

    @classmethod
    def mask(cls, pixels: np.ndarray) -> Raster:
        """Create a 2D segmentation mask."""
        return cls(pixels, spatial_ndim=2, role=MaskRole)

    @classmethod
    def volume_image(cls, pixels: np.ndarray) -> Raster:
        """Create a 3D volume (e.g., CT, MRI, microscopy) with any channel count."""
        return cls(pixels, spatial_ndim=3, role=ImageRole)

    @classmethod
    def volume_mask(cls, pixels: np.ndarray) -> Raster:
        """Create a 3D segmentation volume."""
        return cls(pixels, spatial_ndim=3, role=MaskRole)

class Vector(Data):  # vector-based annotation data
    shapes: list[VectorShape]
class Plot(Data): ...
class LayeredData(Data):
    # `path` is None in folder-based (loose) mode - layers are loaded from separate files
    root: LayerGroup  # logical root only; no LayerGroupActor is created for it
```

#### Layers

```python
class Layer(QObject):
    data: Data | None; name: str
class LayerGroup(Layer):  # recursive container of layers/groups
    children: list[Layer]
class RasterLayer(Layer): ...
class VectorLayer(Layer): ...
class PlotLayer(Layer): ...
```

#### Raster Roles

```python
class RasterRole:
    """
    Base class for raster semantic roles. Not instantiable.
    Assign the *class itself* to Raster.role (e.g., role=ImageRole).
    Plugins can subclass to define new roles.
    """
    name: str

    def __new__(cls, *args, **kwargs):
        raise TypeError(f'{cls.__name__} is not instantiable. Use the class itself as a role token.')

class ImageRole(RasterRole):
    name = 'image'
class MaskRole(RasterRole):
    name = 'mask'

# In the module, where RasterRole is defined
RASTER_NAME_TO_ROLE: dict[str, type[RasterRole]] = {}

def register_raster_role(cls: type[RasterRole]):
    RASTER_NAME_TO_ROLE[cls.name] = cls

for role in (ImageRole, MaskRole):
    register_raster_role(role)

# Serialization
role_name = raster.role.name
# Deserialization
raster.role = RASTER_NAME_TO_ROLE[role_name]
```

#### Vector Shapes

```python
class VectorShape(QObject): ...
class Polyline(VectorShape):
    points: list[QPointF]
class Point(VectorShape):
    pos: QPointF
```

### Actors (Scene Representation)

```python
class GraphicsActor(QObject):  # Generic
    model: QObject
    graphics_item: QGraphicsItem

class LayerActor(GraphicsActor):
    @property
    def layer(self) -> Layer:
        return self.model
class RasterLayerActor(LayerActor):
    graphics_item: QGraphicsPixmapItem
class VectorLayerActor(LayerActor):
    graphics_item: QGraphicsItem  # non-rendering container for shape actors

class VectorShapeActor(GraphicsActor):
    @property
    def shape(self) -> VectorShape:
        return self.model
class PolylineActor(VectorShapeActor):
    graphics_item: QGraphicsPathItem
class PointActor(VectorShapeActor):
    graphics_item: QGraphicsEllipseItem
```

### Views

```python
class DataViewer(QWidget): ...
class GraphicsViewer(DataViewer): ...  # QGraphicsView-based
    def add_actor(self, actor: GraphicsActor):
        self._graphics_scene.addItem(actor.graphics_item)
class LayeredDataViewer(GraphicsViewer): ...
```

### Tools

```python
class ViewerTool(QObject): ...
    viewer: DataViewer
class GraphicsViewerTool(ViewerTool): ...
class LayeredDataViewerTool(GraphicsViewerTool): ...
class SmartBrushImageViewerTool(LayeredDataViewerTool): ...
class PolylineViewerTool(LayeredDataViewerTool) ...
```

## Data Flow

User + Tool -> modifies Data -> emits signal -> View updates

## Planned Features

### Whole-Slide Imaging (Multi-Resolution Raster Support)

Support for **pyramidal/multi-resolution raster formats** (e.g., `.svs`, `.tif`, `.ndpi`) is planned.
The design extends `Raster` with on-demand region reading
and introduces tiled rendering - **without adding new model types** like `WsiData`.
Key additions:
- **Unified `Raster` API** for both in-memory images and WSI,
- **`TiledRasterLayerActor`** for efficient, tile-based display,
- **`RasterRegion`** - a transient pixel buffer for the visible area, enabling tools to work uniformly on any raster.

**Sample code (needs correction):**
```python
class Raster(Data):
    _pixels: np.ndarray | None = None   # for in-memory rasters
    _backend: Any = None                # e.g., SlideIO, OpenSlide, TiffFile

    def read_region(self, level: int, x: int, y: int, width: int, height: int) -> np.ndarray:
        if self._pixels is not None:
            # Level 0 only; no downsample
            h, w = self._pixels.shape[:2]
            x1, y1 = min(x + width, w), min(y + height, h)
            return self._pixels[y:y1, x:x1]
        elif self._backend:
            return self._backend.read_region(level, x, y, width, height)
        else:
            raise RuntimeError("No data source")

    def get_level_dimensions(self, level: int) -> tuple[int, int]:
        if self._pixels is not None:
            return (self._pixels.shape[1], self._pixels.shape[0]) if level == 0 else (0, 0)
        return self._backend.level_dimensions(level)

    def get_best_level_for_downsample(self, downsample: float) -> int:
        if self._backend:
            return self._backend.get_best_level_for_downsample(downsample)
        return 0

    def get_level_downsample(self, level: int) -> float:
        if self._backend:
            return self._backend.get_level_downsample(level)
        return 1.0 if level == 0 else float('inf')


class RasterRegion:
    """Transient pixel data for a visible rectangular region (any raster type)."""
    def __init__(self, pixels: np.ndarray, origin: QPointF, downsample: float):
        self.pixels = pixels
        self.origin = origin        # top-left in full-res (level 0) coordinates
        self.downsample = downsample  # 1.0 = full resolution

    def map_from_full_res(self, point: QPointF) -> tuple[int, int]:
        """Convert full-res image coordinate → local pixel index."""
        x = int((point.x() - self.origin.x()) / self.downsample)
        y = int((point.y() - self.origin.y()) / self.downsample)
        return x, y


class GraphicsViewer(DataViewer):
    def get_visible_raster_region(self) -> RasterRegion | None:
        """Return pixel data for currently visible region (same for WSI and regular images)."""
        if not self._active_raster_actor:
            return None
        return RasterRegionProvider.get_region(self._active_raster_actor, self.viewport())


class RasterRegionProvider:
    @staticmethod
    def get_region(actor: LayerActor, viewport_rect: QRect) -> RasterRegion:
        raster = actor.layer.data
        if not isinstance(raster, Raster):
            raise ValueError("Only raster layers supported")

        # Map viewport -> full-res image coordinates
        scene_rect = actor.viewer.viewport().rect()
        image_rect = actor.graphics_item.mapRectFromScene(actor.viewer.mapToScene(scene_rect))
        x0, y0 = int(image_rect.left()), int(image_rect.top())
        width, height = int(image_rect.width()), int(image_rect.height())

        # Choose optimal pyramid level based on current zoom
        downsample = max(image_rect.width() / width, 1.0) if width > 0 else 1.0
        level = raster.get_best_level_for_downsample(downsample)
        level_downsample = raster.get_level_downsample(level)

        # Read region at selected level
        src_x = int(x0 / level_downsample)
        src_y = int(y0 / level_downsample)
        src_w = int(width / level_downsample)
        src_h = int(height / level_downsample)

        pixels = raster.read_region(level, src_x, src_y, src_w, src_h)

        return RasterRegion(pixels, QPointF(x0, y0), level_downsample)


# Tool usage (identical for WSI and regular images)
class SmartBrushImageViewerTool(LayeredDataViewerTool):
    def on_mouse_click(self, event):
        region = self.viewer.get_visible_raster_region()
        if not region:
            return

        image_pos = self.viewer.mapToScene(event.pos())
        local_x, local_y = region.map_from_full_res(image_pos)

        # Operate on small patch only
        cluster_id = self._cluster(region.pixels, local_x, local_y)
        mask_patch = self._create_mask(region.pixels, cluster_id)

        # Write back to mask layer at full-res coordinates
        self._update_mask_layer(mask_patch, int(region.origin.x()), int(region.origin.y()))
```
