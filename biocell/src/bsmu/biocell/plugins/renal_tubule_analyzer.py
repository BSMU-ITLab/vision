from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import List

import imageio.v3 as iio
import numpy as np
import skimage as ski
import slideio


def out_of_bounds(image: np.ndarray, x: int, y: int) -> bool:
    if -1 < x < image.shape[0] and -1 < y < image.shape[1]:
        return False
    return True


def point_on_line(x0: int, y0: int, x1: int, y1: int, x_coord: int) -> int:
    return int((y1 - y0) * (x_coord - x0) / (x1 - x0) + y0)


def measure_width(skeleton: np.ndarray, shell: np.ndarray, x: int, y: int, prev_x: int, prev_y: int) -> float:
    next_x = -1
    next_y = -1

    for i in range(-1, 2, 2):
        for j in range(-1, 2):
            if not out_of_bounds(skeleton, x + i, y + j) and skeleton[x + i][y + j] == 1 and shell[x + i][y + j] != 0:
                next_x, next_y = x + i, y + j
                break

    if next_x == -1:
        for j in range(-1, 2, 2):
            if not out_of_bounds(skeleton, x, y + j) and skeleton[x][y + j] == 1 and shell[x][y + j] != 0:
                next_x, next_y = x, y + j
                break

    if next_x == -1:
        next_x, next_y = prev_x, prev_y
        prev_x, prev_y = x, y

    support_vector = [[-1 * (next_y - y) + x, (next_x - x) + y], [-1 * (prev_y - y) + x, (prev_x - x) + y]]
    check_points = [[x, y], [x, y]]
    result_points = [[0, 0], [0, 0]]

    while True:
        check_points[0][0] += 1
        check_points[0][1] += 1
        check_points[1][0] -= 1
        check_points[1][1] -= 1

        if support_vector[0][0] == support_vector[1][0]:
            check_points[0][0] = support_vector[0][0]
            check_points[1][0] = support_vector[0][0]
        elif support_vector[0][1] == support_vector[1][1]:
            check_points[0][1] = support_vector[0][1]
            check_points[1][1] = support_vector[0][1]
        else:
            check_points[0][1] = point_on_line(support_vector[0][0], support_vector[0][1],
                                               support_vector[1][0], support_vector[1][1],
                                               check_points[0][0])
            check_points[1][1] = point_on_line(support_vector[0][0], support_vector[0][1],
                                               support_vector[1][0], support_vector[1][1],
                                               check_points[1][0])

        if out_of_bounds(skeleton, check_points[0][0], check_points[0][1]) or \
                not shell[check_points[0][0]][check_points[0][1]]:
            result_points[0] = check_points[0]
            result_points[1][0] = 2 * x - result_points[0][0]
            result_points[1][1] = 2 * y - result_points[0][1]

            return math.dist(result_points[0], result_points[1])

        if out_of_bounds(skeleton, check_points[1][0], check_points[1][1]) or \
                not shell[check_points[1][0]][check_points[1][1]]:
            result_points[1] = check_points[1]
            result_points[0][0] = 2 * x - result_points[1][0]
            result_points[0][1] = 2 * y - result_points[1][1]

            return math.dist(result_points[0], result_points[1])


def skeleton_walker(skeleton: np.ndarray, shell: np.ndarray, result: List[float], x: int, y: int,
                    pixels_num: int, current_cell_data: List[float], prev_x: int, prev_y: int) -> None:
    if pixels_num > 10:
        current_width = measure_width(skeleton, shell, x, y, prev_x, prev_y)
        current_cell_data.append(current_width)
        pixels_num = 0

    for i in range(-1, 2, 2):
        for j in range(-1, 2):
            if not out_of_bounds(skeleton, x + i, y + j) and \
                    skeleton[x + i, y + j] == 1 and \
                    shell[x + i, y + j] != 0:
                skeleton[x + i, y + j] = 0
                skeleton_walker(skeleton, shell, result, x + i, y + j, pixels_num + 1, current_cell_data, x, y)

    for j in range(-1, 2, 2):
        if not out_of_bounds(skeleton, x, y + j) and \
                skeleton[x][y + j] == 1 and \
                shell[x][y + j] != 0:
            skeleton[x, y + j] = 0
            skeleton_walker(skeleton, shell, result, x, y + j, pixels_num + 1, current_cell_data, x, y)

    if len(current_cell_data) > 1:
        result.append(np.average(current_cell_data[1:]))
        current_cell_data.clear()
        current_cell_data.append(0)

    skeleton[x, y] = 0


def read_wsi(path: Path) -> np.ndarray:
    file_extension = path.suffix
    slideio_driver_by_file_extension = {
        '.svs': 'SVS',
        '.afi': 'AFI',
        '.scn': 'SCN',
        '.czi': 'CZI',
        '.zvi': 'ZVI',
        '.ndpi': 'NDPI',
        '.tiff': 'GDAL',
        '.tif': 'GDAL',
    }
    slideio_driver = slideio_driver_by_file_extension[file_extension]
    slide = slideio.open_slide(str(path), slideio_driver)
    scene = slide.get_scene(0)
    full_resolution_width = scene.rect[2]
    print('full_resolution_width', full_resolution_width)
    region = scene.read_block(size=(round(full_resolution_width / 8), 0))
    return region


def main():
    sys.setrecursionlimit(100000)
    image = iio.imread(r'D:\Temp\kidney\Kidney.png')
    # image = read_wsi(Path(r'D:\Temp\kidney\108_2022_MSB.svs'))
    image_hed = ski.color.rgb2hed(image)

    skel = ski.morphology.skeletonize(image_hed[:, :, 2] > 0.10)
    iio.imwrite(r'D:\Temp\kidney\Kidney-skel.png', (skel * 255).astype(np.uint8))

    result = [0]
    stop_flag = False
    while not stop_flag:
        stop_flag = True
        for i in range(skel.shape[0]):
            for j in range(skel.shape[1]):
                if skel[i, j] == 1:
                    stop_flag = False
                    skel[i, j] = 0
                    pixels_num = 0
                    current_cell_data = [0]
                    skeleton_walker(skel, image_hed[:, :, 2] > 0.10, result, i, j, pixels_num, current_cell_data, -1, -1)

    print(result[1:])
    print(np.average(result[1:]))


if __name__ == '__main__':
    main()
