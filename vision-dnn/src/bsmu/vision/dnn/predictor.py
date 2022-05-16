from __future__ import annotations

from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
import onnxruntime as ort

from bsmu.vision.dnn.inferencer import Inferencer, preprocessed_image

if TYPE_CHECKING:
    from typing import Sequence, List


class Predictor(Inferencer):
    def predict_batch(self, images: Sequence[np.ndarray]) -> Sequence[float]:
        input_image_batch = []

        for image in images:
            # If it's an RGBA-image
            if image.shape[2] == 4:
                # Remove alpha-channel
                image = image[:, :, :3]

            if image.shape[:2] != self._model_params.input_image_size:
                image = cv.resize(image, self._model_params.input_image_size, interpolation=cv.INTER_AREA)

            image = preprocessed_image(image, normalize=True, preprocessing_mode=self._model_params.preprocessing_mode)

            input_image_batch.append(image)

        self._create_inference_session()
        model_inputs: List[ort.NodeArg] = self._inference_session.get_inputs()
        assert len(model_inputs) == 1, 'Predictor can process only models with one input'
        input_feed = {model_inputs[0].name: input_image_batch}
        model_outputs: List[ort.NodeArg] = self._inference_session.get_outputs()
        output_names = [model_output.name for model_output in model_outputs]
        outputs = self._inference_session.run(output_names, input_feed)
        assert len(outputs) == 1, 'Predictor can process only models with one output'
        output_batch = outputs[0]

        output_batch = np.squeeze(output_batch, axis=-1)
        return output_batch

    def predict(self, image: np.ndarray) -> float:
        return self.predict_batch([image])[0]
