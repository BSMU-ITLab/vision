from __future__ import annotations

from pathlib import Path

import skimage.io

from bsmu.vision.dnn.inferencer import ImageModelParams as DnnModelParams
from bsmu.vision.dnn.segmenter import Segmenter as DnnSegmenter


def cut_disk_region_for_images_in_dir(dir_with_images: Path, save_dir: Path):
    disk_segmenter_model_params = DnnModelParams(
        path=Path(r'D:\Projects\vision\retinal-fundus\src\bsmu\retinal_fundus\plugins\dnn-models\disk-model-005.onnx'),
        input_size=(352, 352, 3),
        preprocessing_mode='image-net-tf')
    disk_segmenter = DnnSegmenter(disk_segmenter_model_params)

    for image_path in dir_with_images.rglob("*"):
        if not image_path.is_file():
            continue

        extension = image_path.suffix.lower()
        if extension not in ('.png', '.jpg', '.jpeg', '.bmp', '.tiff'):
            continue

        print(image_path)

        image = skimage.io.imread(str(image_path))

        # Disk segmentation
        disk_mask, disk_bbox = disk_segmenter.segment_largest_connected_component_and_return_mask_with_bbox(image)
        if disk_bbox is None or disk_bbox.empty:
            print(f'WARNING! {image_path} has invalid disk bbox!')
            continue

        disk_region_bbox = disk_bbox.margins_added(
            round((disk_bbox.width + disk_bbox.height) / 2))
        disk_region_bbox.clip_to_shape(image.shape)
        disk_region_image = disk_region_bbox.pixels(image)

        # Save into |save_dir| but with path relative to |dir_with_images|
        save_image_path = save_dir / image_path.relative_to(dir_with_images)
        # Save always into *.png to avoid quality loss
        save_image_path = save_image_path.with_suffix('.png')

        save_image_path.parent.mkdir(parents=True, exist_ok=True)
        skimage.io.imsave(str(save_image_path), disk_region_image)


def run():
    cut_disk_region_for_images_in_dir(
        Path(r'D:\Projects\retinal-fundus-models\databases\OUR_IMAGES\sorted2\part-4'),
        Path(r'D:\Projects\retinal-fundus-models\databases\OUR_IMAGES\sorted2\part-4-disk-region')
    )


if __name__ == '__main__':
    run()
