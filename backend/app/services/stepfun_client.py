"""StepFun API client - unified interface for LLM, Image, TTS."""

from openai import OpenAI
from app.config import get_settings


class StepFunClient:
    def __init__(self, api_key: str = None, base_url: str = None):
        settings = get_settings()
        self.client = OpenAI(
            api_key=api_key or settings.STEPFUN_API_KEY,
            base_url=base_url or settings.STEPFUN_BASE_URL,
        )

    def llm_chat(self, messages: list, model: str = "step-3.7-flash", **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=model, messages=messages, **kwargs
        )
        return response.choices[0].message.content

    def image_generate(self, prompt: str, model: str = "step-image-edit-2", **kwargs) -> bytes:
        response = self.client.images.generate(
            model=model, prompt=prompt, response_format="b64_json", **kwargs
        )
        import base64
        return base64.b64decode(response.data[0].b64_json)

    def image_edit(self, image: bytes, prompt: str, model: str = "step-image-edit-2", **kwargs) -> bytes:
        response = self.client.images.edit(
            model=model, image=image, prompt=prompt, response_format="b64_json", **kwargs
        )
        import base64
        return base64.b64decode(response.data[0].b64_json)

    def tts(self, text: str, voice: str = "cixingnansheng", model: str = "stepaudio-2.5-tts", **kwargs) -> bytes:
        response = self.client.audio.speech.create(
            model=model, voice=voice, input=text, **kwargs
        )
        return response.content
