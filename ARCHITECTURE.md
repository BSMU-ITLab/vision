# Architecture Overview

## Core Principles
- Model/View separation (using PySide signals)
- Layered data model with raster and vector support
- Extensible to plots and other viewers

## Plugin System
The application uses a **configuration-driven plugin architecture**.
Plugins are **explicitly listed in `App.conf.yaml`** and loaded at startup.
Each user profile (e.g., radiologist, pathologist) uses a **dedicated config file** enabling only relevant plugins, so keeping the UI uncluttered and workflow-focused.

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
    layers: list[Layer]
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

### Views
```python
class DataViewer(QWidget): ...
class GraphicsViewer(DataViewer): ...  # QGraphicsView-based
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
