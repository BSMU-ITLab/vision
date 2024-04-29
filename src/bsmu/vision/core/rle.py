from __future__ import annotations

import zlib
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from typing import Sequence


def encode_rle(array: np.ndarray) -> tuple[np.ndarray | None, np.ndarray | None]:
    """
    From: https://stackoverflow.com/a/32681075
    :param array: one dimensional array
    :return: tuple of (values, run lengths)
    """
    n = len(array)
    if n == 0:
        return None, None

    y = array[1:] != array[:-1]  # pairwise unequal (string safe)
    i = np.append(np.where(y), n - 1)  # must include last element position
    run_lengths = np.diff(np.append(-1, i))
    return array[i], run_lengths


def encode_rle_by_zlib(array: np.ndarray) -> bytes:
    compressor = zlib.compressobj(level=zlib.Z_BEST_SPEED, strategy=zlib.Z_RLE)
    return compressor.compress(array) + compressor.flush()


def decode_rle(
        values: np.ndarray | Sequence[int],
        run_lengths: np.ndarray | Sequence[int],
        dtype=np.uint8
) -> np.ndarray:
    # return np.repeat(values, run_lengths)  # It's do the work, but for our use cases it's slow

    run_start_positions = np.cumsum(np.append(0, run_lengths)[:-1])
    run_end_positions = run_start_positions + run_lengths
    size = run_end_positions[-1]
    array = np.empty(size, dtype)
    for run_start_pos, run_end_pos, value in zip(run_start_positions, run_end_positions, values):
        array[run_start_pos:run_end_pos].fill(value)
    return array


def decode_rle_by_zlib(compressed_data: bytes, dtype=np.uint8) -> np.ndarray:
    data = zlib.decompress(compressed_data)
    return np.frombuffer(data, dtype=dtype)
