from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import onnxruntime as ort

from bsmu.vision.core.concurrent import ThreadPool
from bsmu.vision.dnn.inferencer import Inferencer

if TYPE_CHECKING:
    from typing import Callable, Sequence, List


class Predictor(Inferencer):
    def predict_batch(self, images: Sequence[np.ndarray]) -> np.ndarray:
        input_image_batch = self._model_params.preprocessed_input_batch(images)

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

    def predict_async(self, image: np.ndarray, callback: Callable):
        prediction_task = ThreadPool.call_async_dnn(self.predict, image)
        prediction_task.on_finished = callback


class MlPredictor(Inferencer):
    """
    Predictor for machine learning models, converted to ONNX (e.g. XGBoost models)
    """

    def predict(self, params: list) -> float:
        self._create_inference_session()

        # See: http://onnx.ai/sklearn-onnx/auto_tutorial/plot_gexternal_xgboost.html
        predict = self._inference_session.run(None, {'input': [params]})
        predicted_class = int(predict[0])  # Cast from numpy.int64 into int
        predicted_class_probabilities = predict[1][0]
        predicted_class_1_probability = predicted_class_probabilities[1]
        return predicted_class_1_probability
