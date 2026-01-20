"""
Inference worker for processing async jobs.

This worker is run by RQ and processes inference requests in the background.
"""

import httpx
from rq import get_current_job

from app.core.config import settings


def process_inference(request_data: dict) -> dict:
    """
    Process an inference request synchronously.

    This function is called by RQ workers to process inference jobs.
    """
    job = get_current_job()

    # Update job progress
    if job:
        job.meta["progress"] = 10
        job.save_meta()

    # Prepare the request to vLLM
    vllm_url = f"{settings.vllm_base_url}/v1/chat/completions"

    # Make synchronous request to vLLM
    with httpx.Client(timeout=settings.vllm_timeout) as client:
        if job:
            job.meta["progress"] = 30
            job.save_meta()

        response = client.post(vllm_url, json=request_data)

        if job:
            job.meta["progress"] = 90
            job.save_meta()

        if response.status_code != 200:
            raise Exception(f"vLLM error: {response.status_code} - {response.text}")

        result = response.json()

        if job:
            job.meta["progress"] = 100
            job.save_meta()

        return result
