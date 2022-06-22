from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import onnxruntime as ort

from bsmu.vision.dnn.inferencer import Inferencer, preprocessed_image_batch

if TYPE_CHECKING:
    from typing import Callable, Sequence, List


class Predictor(Inferencer):
    def predict_batch(self, images: Sequence[np.ndarray]) -> np.ndarray:
        input_image_batch = preprocessed_image_batch(images, self._model_params)

        self._create_inference_session()
        model_inputs: List[ort.NodeArg] = self._inference_session.get_inputs()
        assert len(model_inputs) == 1, 'Predictor can process only models with one input'
        input_feed = {model_inputs[0].name: input_image_batch}
        model_outputs: List[ort.NodeArg] = self._inference_session.get_outputs()
        output_names = [model_output.name for model_output in model_outputs]
        outputs = self._inference_session.run(output_names, input_feed)
        assert len(outputs) == 1, 'Predictor can process only models with one output'
        output_batch = outputs[0]
        return output_batch

    def predict(self, image: np.ndarray) -> float | np.ndarray:
        prediction = self.predict_batch([image])[0]
        if len(prediction) == 1:
            # Cast from numpy.float32 into float
            prediction = float(prediction)
        return prediction

    def predict_async(self, callback: Callable, image: np.ndarray):
        self._call_async_with_callback(callback, self.predict, image)
