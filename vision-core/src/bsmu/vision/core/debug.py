import numpy as np


def print_array_info(array: np.ndarray, title: str = ''):
    print(f'{title}: shape={array.shape} type={array.dtype} min={array.min()} max={array.max()}')
    print(f'unique: {np.unique(array)}')
