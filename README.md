# Vision

Application to work with images and other visual information.  
The app contains a lot of plugins to preprocess and analyze segmentation results.
Necessary plugins can be enabled/disabled using plugin manager.

**Project handling**:
- **Folder-based projects**: Load layers from a directory structure (e.g., `images/`, `masks/`) without a project file.
- **Project files** (planned): Save and load complete layer state in two ways:
    - **Referenced**: Stores only links to your original files.
    - **Self-contained**: Embeds all data inside the project file.

> For architecture and design principles, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Python Environment

python 3.11
```bash
pip install pyside6 ruamel-yaml numpy opencv-python scikit-image scipy sortedcontainers onnxruntime-gpu pandas nibabel pydicom slideio tifffile pytest cx-freeze
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
  - **cx-freeze**: Creates standalone executables and installers.

## Running the Application from Source

To run the application, configure your IDE to recognize the `src` directory as the source root.  
Then run `bsmu/vision/app/main.py`:

### PyCharm

1. Right-click on the `src` folder.
2. Select **Mark Directory as** -> **Sources Root**.
3. Right-click on `bsmu/vision/app/main.py` and select **Run**.

### VS Code

Use predefined configurations in the `launch.json` file, located in the `.vscode` folder:
1. Open the **Run and Debug** view by clicking on the **Run and Debug** icon in the **Activity Bar**
(or use the shortcut `Ctrl+Shift+D`).
2. In the dropdown menu at the top of the **Run and Debug** view, select the configuration: `Python: Run main.py`.
3. Click the green play button (**Start Debugging**) next to the dropdown menu to run the selected configuration.
If you want to run without debugging, use the shortcut `Ctrl+F5`.

## Building the .exe

Run the `scripts/build.py` script with the argument `build`:

### PyCharm

1. Right-click on the `scripts/build.py` script and select **Modify Run Configuration...**.
2. In the **Script parameters** field, enter: `build`.
3. Right-click on the `scripts/build.py` script again and select **Run**.

### VS Code

1. In the **Run and Debug** view, select the configuration: `Python: Run build.py`.
2. Run the selected configuration (`Ctrl+F5` - without debugging; `F5` - with debugging).

## Contributing

For guidelines on contributing, please see [CONTRIBUTING.md](CONTRIBUTING.md).
