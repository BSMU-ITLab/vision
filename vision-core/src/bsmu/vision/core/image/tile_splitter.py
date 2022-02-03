from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from typing import Sequence


def split_image_into_tiles(image, tile_grid_shape: Sequence = (2, 2), border_size: int = 0) -> list:
    border_axis_qty = 2
    border_pad_width = ((border_size, border_size),) * border_axis_qty \
                       + ((0, 0),) * (len(image.shape) - border_axis_qty)
    bordered_image = np.pad(image, pad_width=border_pad_width)

    tile_grid_row_qty = tile_grid_shape[0]
    tile_grid_col_qty = tile_grid_shape[1]
    row_tile_size = int(round(image.shape[0] / tile_grid_row_qty))
    col_tile_size = int(round(image.shape[1] / tile_grid_col_qty))

    tiles = []
    tile_row_begin = 0
    borders_size = 2 * border_size
    for row in range(tile_grid_row_qty):
        tile_row_end = image.shape[0] if row == tile_grid_row_qty - 1 else tile_row_begin + row_tile_size
        tile_col_begin = 0
        for col in range(tile_grid_col_qty):
            tile_col_end = image.shape[1] if col == tile_grid_col_qty - 1 else tile_col_begin + col_tile_size
            tile = bordered_image[
                   tile_row_begin:tile_row_end + borders_size,
                   tile_col_begin:tile_col_end + borders_size,
                   ...]
            tiles.append(tile)

            tile_col_begin = tile_col_end

        tile_row_begin = tile_row_end

    return tiles


def merge_tiles_into_image(tiles, tile_grid_shape: Sequence, border_size: int = 0):
    tile_grid_row_qty = tile_grid_shape[0]
    tile_grid_col_qty = tile_grid_shape[1]

    rows = []
    row_begin_tile_index = 0
    for row in range(tile_grid_row_qty):
        row_end_tile_index = row_begin_tile_index + tile_grid_col_qty
        merged_row_tile = np.concatenate(
            tiles[row_begin_tile_index:row_end_tile_index,
                  border_size:tiles.shape[1] - border_size,
                  border_size:tiles.shape[2] - border_size],
            axis=1)
        rows.append(merged_row_tile)

        row_begin_tile_index = row_end_tile_index

    return np.concatenate(rows, axis=0)


def merge_tiles_into_image_with_blending(tiles, tile_grid_shape: Sequence, border_size: int = 0):
    removed_border_size = int(border_size / 2)
    blended_border_size = border_size - removed_border_size

    tiles = tiles[
            :,
            removed_border_size:tiles.shape[1] - removed_border_size,
            removed_border_size:tiles.shape[2] - removed_border_size,
            ...]

    tile_grid_row_qty = tile_grid_shape[0]
    tile_grid_col_qty = tile_grid_shape[1]

    rows = []
    row_begin_tile_index = 0
    blending_matrix = np.linspace(0, 1, 2 * blended_border_size)
    if tiles.shape[-1] == 1:
        # Add new axis for correct broadcasting while multiplying by an image with a shape (X, Y, 1)
        blending_matrix = blending_matrix[:, np.newaxis]

    for row in range(tile_grid_row_qty):
        row_end_tile_index = row_begin_tile_index + tile_grid_col_qty

        merged_row = merge_tiles_horizontally_with_blending(
            tiles[row_begin_tile_index:row_end_tile_index], blended_border_size, blending_matrix)
        rows.append(merged_row)

        row_begin_tile_index = row_end_tile_index

    rotated_rows = [np.rot90(row) for row in rows]
    rotated_merged_image = merge_tiles_horizontally_with_blending(rotated_rows, blended_border_size, blending_matrix)
    merged_image = np.rot90(rotated_merged_image, 3)
    return merged_image


def merge_tiles_horizontally_with_blending(tiles, blended_border_size: int, blending_matrix):
    flipped_blending_matrix = np.flip(blending_matrix)
    tiles_and_blended_parts_to_concatenate = []
    for tile_index, tile in enumerate(tiles):
        tile_begin = blended_border_size if tile_index == 0 \
            else 2 * blended_border_size
        tile_end = tile.shape[1] - blended_border_size if tile_index == len(tiles) - 1 \
            else tile.shape[1] - 2 * blended_border_size

        tile_with_cropped_blended_borders = tile[:, tile_begin:tile_end, ...]
        tiles_and_blended_parts_to_concatenate.append(tile_with_cropped_blended_borders)

        if blended_border_size != 0 and tile_index != len(tiles) - 1:
            curr_tile_blended_part = tile[:, -2 * blended_border_size:, ...]
            next_tile_blended_part = tiles[tile_index + 1][:, :2 * blended_border_size, ...]
            tile_part_blended_with_next_tile = \
                (curr_tile_blended_part * flipped_blending_matrix) + (next_tile_blended_part * blending_matrix)
            tiles_and_blended_parts_to_concatenate.append(tile_part_blended_with_next_tile)

    merged_image = np.concatenate(tiles_and_blended_parts_to_concatenate, axis=1)
    return merged_image
