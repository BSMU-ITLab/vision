import numpy as np


def calculate_hsv_parameters(hsv: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    hsv_mean = np.mean(hsv, axis=0)
    hsv_std = np.std(hsv, axis=0)
    # hsv_min = np.min(hsv, axis=0)
    # hsv_max = np.max(hsv, axis=0)

    kth = int(hsv.shape[0] * 0.03)  # 3% of max/min pixels
    hsv_min_bin_3 = np.mean(np.partition(hsv, kth, axis=0)[:kth, :], axis=0)
    hsv_max_bin_3 = np.mean(np.partition(hsv, -kth, axis=0)[-kth:, :], axis=0)

    return hsv_mean, hsv_std, hsv_min_bin_3, hsv_max_bin_3
