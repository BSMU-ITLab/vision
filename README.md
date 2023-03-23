# Vision
Application to work with images and other visual information.\
The app contains a lot of plugins to preprocess and analyze segmentation results.

## Python environment
python 3.10\
`pip install cx-freeze nibabel numpy onnxruntime-gpu opencv-python openslide-python pandas pydicom pyside6 pytest ruamel-yaml "scikit-image<0.20.0" scipy slideio sortedcontainers tifffile toml`

Used "scikit-image<0.20.0", cause version 0.20.0 uses lazy_loader 0.1 library, and frozen *.exe by cx_Freeze throw an error during run.\
See the same error with other library (librosa): https://github.com/marcelotduarte/cx_Freeze/issues/1837 \
According to the issue thread, lazy_loader 0.2 will be frozen correctly.
