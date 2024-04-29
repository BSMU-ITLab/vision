CPU_PROVIDER = 'CPUExecutionProvider'
CUDA_PROVIDER = 'CUDAExecutionProvider'


class OnnxConfig:
    providers = [CUDA_PROVIDER, CPU_PROVIDER]
