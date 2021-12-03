from bsmu.vision.core.converters.color import color_transfer_function_to_palette
from bsmu.vision.core.transfer_functions.color import ColorTransferFunction


def test_color_transfer_function_to_palette_one():
    color_transfer_function = ColorTransferFunction.from_x_fractions_colors_array(
        [[0, 255, 255, 255, 0],
         [1, 255, 255, 255, 255]])
    palette = color_transfer_function_to_palette(color_transfer_function)
    assert (palette.array[0] == [255, 255, 255, 0]).all()
    assert (palette.array[128] == [255, 255, 255, 128]).all()
    assert (palette.array[255] == [255, 255, 255, 255]).all()


def test_color_transfer_function_to_palette_two():
    color_transfer_function = ColorTransferFunction.from_x_fractions_colors_array(
        [[0, 0, 0, 0, 0],
         [1, 255, 255, 255, 255]])
    palette = color_transfer_function_to_palette(color_transfer_function)
    assert (palette.array[0] == [0, 0, 0, 0]).all()
    assert (palette.array[128] == [128, 128, 128, 128]).all()
    assert (palette.array[255] == [255, 255, 255, 255]).all()
