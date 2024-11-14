# Vision

Application to work with images and other visual information.<br>
The app contains a lot of plugins to preprocess and analyze segmentation results. Necessary plugins can be enabled/disabled using plugin manager.

## Python environment

python 3.10
```bash
pip install pyside6 ruamel-yaml numpy opencv-python scikit-image scipy sortedcontainers onnxruntime-gpu pandas nibabel pydicom slideio tifffile pytest toml cx-freeze
```

### Mandatory Dependencies

- **Python** 3.10+
- **PySide6** 6.5+: Python bindings for Qt, used for GUI and signal/slot mechanism.
- **ruamel-yaml** 0.17+: YAML parser and emitter for config files.

### Common Optional Dependencies

- **numpy**: Stores and processes image data.
- **opencv-python**: Provides optimized image processing algorithms.
- **scikit-image**: Wide range of image processing algorithms not in opencv-python (most often opencv-python methods have better performance).
- **scipy**: Mostly for data interpolation.
- **sortedcontainers**: Sorted collections library.

### Specialized Dependencies
- **Neural Network Inference**
  - **onnxruntime-gpu**: Infers neural network models on GPUs and CPUs.

- **Data Analysis and File Format Handling**
  - **pandas**: Data analysis tool.
  - **nibabel**: Reads NIfTI files.
  - **pydicom**: Reads DICOM files.
  - **slideio**: Reads high-resolution medical slides (Whole Slide Imaging).
  - **tifffile**: Manages tiled multi-resolution (pyramid) TIFF files.

- **Testing**
  - **pytest**: Testing framework.

- **Build and Packaging**
  - **toml**: Configuration for PyPI packages.
  - **cx-freeze**: Creates standalone executables and installers.

## Contributing

For guidelines on contributing, please see [CONTRIBUTING.md](CONTRIBUTING.md).
