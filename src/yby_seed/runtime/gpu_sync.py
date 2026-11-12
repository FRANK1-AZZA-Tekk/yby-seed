"""Reexport do slot síncrono (mesmo lock que inference_slot)."""

from src.yby_seed.runtime.gpu_gate import sync_inference_slot

__all__ = ["sync_inference_slot"]
