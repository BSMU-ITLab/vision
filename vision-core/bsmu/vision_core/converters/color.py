import numpy as np
from scipy import interpolate

from bsmu.vision_core.palette import Palette
from bsmu.vision_core.transfer_functions.color import ColorTransferFunction


def color_transfer_function_to_palette(color_transfer_function: ColorTransferFunction) -> Palette:
    xp = [point.x for point in color_transfer_function.points]
    fp = [point.color_array for point in color_transfer_function.points]
    interpolator = interpolate.interp1d(xp, fp, axis=0, assume_sorted=True)
    color_transfer_function_max_x = color_transfer_function.points[-1].x
    interpolated_colors_array = interpolator(np.arange(color_transfer_function_max_x + 1))
    palette_array = np.array(interpolated_colors_array.round(), dtype=np.uint8)
    return Palette(palette_array)
