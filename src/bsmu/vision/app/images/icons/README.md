# Icon Generation
ImageMagick-7.1.0 was used to generate *.ico from *.svg.\
Command example:\
`magick convert -density 256x256 -background none vision.svg -define icon:auto-resize vision.ico`

The resulted *.ico file contains multiple images with different resolutions.\
The `-density` flag is needed to get clearer image (when the *.svg is rasterized).
