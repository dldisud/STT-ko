from __future__ import annotations

from typing import List

from settings import AppPaths, model_ready


def determine_available_models(paths: AppPaths, gpu_enabled: bool) -> List[str]:
    models: List[str] = []

    if model_ready("moonshine", paths.moonshine_model_dir):
        models.append("moonshine")

    if gpu_enabled and model_ready("qwen3", paths.qwen3_model_dir):
        models.append("qwen3")

    return models
