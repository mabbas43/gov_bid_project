"""Picks the model. Demo mode never builds a network client."""
from backend.llm import LLM, DeepSeekLLM


def get_llm(demo_mode: bool) -> LLM:
    if demo_mode:
        from backend.agent.demo_llm import DemoLLM

        return DemoLLM()
    return DeepSeekLLM()
