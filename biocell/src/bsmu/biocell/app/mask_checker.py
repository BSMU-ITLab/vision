from pathlib import Path

import cv2 as cv
import numpy as np


def fix_mask(mask: np.ndarray, min_value: int, max_value: int) -> bool:
    # Check mask values outside the range [min_value, max_value]. 0 is valid value too.
    outside_range = ((mask < min_value) | (mask > max_value)) & (mask != 0)
    need_to_fix = np.any(outside_range)
    if need_to_fix:
        print(f'Warning: Mask contains values outside the range [{min_value}, {max_value}].')
        unique, counts = np.unique(mask[outside_range], return_counts=True)
        for value, count in zip(unique, counts):
            print(f'Number of pixels with value {value}: {count}')

        # Nullify mask values outside the range
        mask[outside_range] = 0

    return need_to_fix


def check_masks_in_dir(mask_dir: Path, save_dir: Path):
    for mask_path in mask_dir.iterdir():
        if not mask_path.is_file():
            continue

        print(f'\t--- {mask_path} ---')
        mask = cv.imread(str(mask_path), cv.IMREAD_UNCHANGED)
        print(mask.shape, mask.dtype, mask.min(), mask.max())

        mask_was_fixed = fix_mask(mask, min_value=3, max_value=9)

        if mask_was_fixed:
            save_path = save_dir / mask_path.name
            saved = cv.imwrite(str(save_path), mask)
            if not saved:
                print('Warning: Can not save the fixed mask. Maybe save_dir does not exist.')


def main():
    check_masks_in_dir(
        Path(r'D:\Projects\pathological-cells\data\NewLabeled\GleasonSegmentation\2023.09.05-pack\masks'),
        Path(r'D:\Projects\pathological-cells\data\NewLabeled\GleasonSegmentation\2023.09.05-pack\fixed-masks'))


if __name__ == '__main__':
    main()
