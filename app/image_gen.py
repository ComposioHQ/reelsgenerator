import base64
import io
import os
import random
import shutil
from typing import Literal
import typing

from app.utils.strings import log_attempt_number
import httpx
from loguru import logger
from PIL import Image
from pydantic import BaseModel

from app.config import images_cache_path
from app.utils.path_util import search_file, text_to_sha256_hash
from app.config import settings

from tenacity import retry, stop_after_attempt, wait_fixed
from together import AsyncTogether

together_client = AsyncTogether(api_key=settings.TOGETHER_API_KEY)

ImageGenStyle = Literal[
    "Human Realism",
    "Disney Toon",
    "Japanese Anime",
    "Line-drawing, colored",
]


class ImageGeneratorConfig(BaseModel):
    width: int = 1024
    height: int = 1024
    style: ImageGenStyle | str = "Human Realism"


class ImageGenerator:
    def __init__(self, cwd: str, config: ImageGeneratorConfig):
        self.config = config
        self.cwd = cwd
        self.base = os.path.join(self.cwd, "background_images")
        self.seed = random.randint(10, 100)

        logger.info(f"Using image generator with seed: {self.seed}")

        os.makedirs(self.base, exist_ok=True)

    async def image_valid(self, img_path: str) -> bool:
        try:
            im = Image.open(img_path)
            im.verify()
            return True
        except Exception as e:
            logger.error(f"Error in image_valid(): {e}")
            return False

    async def generate_with_deepinfra(self, fpath, prompt: str) -> str | None:
        url = "https://api.deepinfra.com/v1/inference/black-forest-labs/FLUX-1-schnell?width=1024&height=1024&seed=24&num_inference_steps=5&guidance_scale=10"

        logger.debug(f"Generating image from prompt: {prompt}")

        async with httpx.AsyncClient(timeout=httpx.Timeout(100.0)) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {os.getenv('DEEPINFRA_API_KEY')}"},
                json={"prompt": prompt},
            )

            response = response.json()

            # get base64 image
            base64_str = response["images"][0]
            self.save_b64_to_file(base64_str, fpath)

    def maybe_remove_b64_prefix(self, s: str) -> str:
        r = "data:image/png;base64,"
        if s.startswith(r):
            s = s[len(r) :]
        return s

    def save_b64_to_file(self, b64_str: str, fpath: str):
        b64_str = self.maybe_remove_b64_prefix(b64_str)
        img = Image.open(io.BytesIO(base64.decodebytes(bytes(b64_str, "utf-8"))))
        img.save(fpath, quality=100, subsampling=0)

    async def generate_maybe_anyai_pollination(self, fpath, prompt: str):
        style = self.config.style.lower()
        model = "flux"

        # don't add art styles to the prompt for human and anime
        if "human" not in style and "anime" not in style:
            prompt = f"{prompt} (Art Style: {self.config.style})"

        if "anime" in style:
            model = "flux-anime"

        if "disney" in style:
            model = "flux-disney"

        # for anyai, always rand seed
        self.seed = random.randint(300, 2000)

        logger.debug(f"Generating image from prompt: {prompt}")

        response: httpx.Response | None = None

        async def use_anyai():
            async with httpx.AsyncClient(timeout=None) as client:
                url = "https://api.airforce/v1/imagine"
                url = f"{url}?prompt={prompt}&width={self.config.width}&height={self.config.height}&model={model}&seed={self.seed}&nologo=true"
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    return response
                except httpx.HTTPStatusError as e:
                    logger.error(
                        f"AnyAI request failed with status {e.response.status_code}"
                    )
                except Exception as e:
                    logger.error(f"Error during AnyAI request: {e}")
                return None

        async def use_pollination():
            async with httpx.AsyncClient(timeout=None) as client:
                logger.debug("using pollination")
                url = "https://image.pollinations.ai/prompt"
                url = f"{url}/{prompt}?width={self.config.width}&height={self.config.height}&model=flux&seed={self.seed}&nologo=true"
                try:
                    response = await client.post(url)
                    response.raise_for_status()
                    return response
                except httpx.HTTPStatusError as e:
                    logger.error(
                        f"Pollination request failed with status {e.response.status_code}"
                    )
                except Exception as e:
                    logger.error(f"Error during Pollination request: {e}")
                return None

        response = await use_pollination()
        if not response:
            logger.debug("Falling back to anyai")
            response = await use_anyai()

        if not response:
            raise ValueError("Failed to generate image, all possibilities failed")

        with open(fpath, "wb") as f:
            f.write(response.content)

    async def generate_with_together(self, fpath, prompt: str):
        response = await together_client.images.generate(
            prompt=prompt,
            model="black-forest-labs/FLUX.1-schnell-Free",
            width=self.config.width,
            height=self.config.height,
            steps=4,
            response_format="b64_json",
            seed=self.seed,
        )

        data = typing.cast(str, response.data[0].b64_json)  # type: ignore

        self.save_b64_to_file(b64_str=data, fpath=fpath)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        after=log_attempt_number, # type: ignore
        reraise=True,
    )
    async def generate_image(self, prompt: str, sentence=None) -> str:
        prompt_hash = text_to_sha256_hash(prompt.lower() + "_" + self.config.style)
        fname = f"{prompt_hash}.jpg"
        fpath = os.path.join(os.getcwd(), images_cache_path, fname)

        cached_image_path = search_file(images_cache_path, fname)
        if cached_image_path:
            is_valid = await self.image_valid(fpath)
            if not is_valid:
                os.remove(fpath)

            logger.info(f"Found image in cache: {prompt}: {cached_image_path}")
            shutil.copy2(cached_image_path, self.base)

            return cached_image_path

        if settings.IMAGE_PROVIDER == "pollination":
            await self.generate_maybe_anyai_pollination(fpath, prompt)
        elif settings.IMAGE_PROVIDER == "deepinfra":
            await self.generate_with_deepinfra(fpath, prompt)
        elif settings.IMAGE_PROVIDER == "together":
            await self.generate_with_together(fpath, prompt)
        else:
            raise NotImplementedError("Unknown image provider")

        is_valid = await self.image_valid(fpath)
        if not is_valid:
            os.remove(fpath)
            raise ValueError("Failed to generate image")

        shutil.copy2(fpath, self.base)
        return fpath