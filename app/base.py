import asyncio
import json
import multiprocessing
import os
import shutil
from typing import Any, Literal
from app.config import images_cache_path, speech_cache_path
from app.utils.path_util import download_resource
from app.utils.strings import FileClip


from app.utils.strings import log_attempt_number
from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel
from app.image_gen import ImageGenerator, ImageGeneratorConfig
from app.prompt_gen import PromptGenerator
from app.subtitle_gen import SubtitleGenerator
from app.synth_gen import SynthConfig, SynthGenerator
from app.video_gen import VideoGenerator, VideoGeneratorConfig
from pydantic import computed_field

from abc import ABC
from pydantic.json import pydantic_encoder
from tenacity import retry, stop_after_attempt, wait_fixed

load_dotenv()


VideoType = Literal["narrator", "motivational"]


class TempData:
    def __init__(
        self, synth_clip: FileClip, media_clip: FileClip | None = None
    ) -> None:
        self.synth_clip = synth_clip
        self.media_clip = media_clip


class VideoAssetCacheItem(BaseModel):
    """an item in the video asset cache"""

    sentence: str
    """ sentence to generate video from """

    image_prompt: str
    """ prompt used to generate image """

    tts_speech_url: str
    """ uploaded url to text-to-speech audio """

    media_url: str
    """ uploaded url to image """


class BaseGeneratorConfig(BaseModel):
    job_id: str
    video_type: VideoType = "narrator"

    @computed_field
    @property
    def cwd(self) -> str:
        job_cwd = f"/tmp/narrator/{self.job_id}"
        os.makedirs(job_cwd, exist_ok=True)
        return job_cwd

    video_gen_config: VideoGeneratorConfig = VideoGeneratorConfig()
    """ config for the video generator """

    synth_config: SynthConfig = SynthConfig()
    """ config for the synthesizer """

    image_gen_config: ImageGeneratorConfig = ImageGeneratorConfig()
    """ config for the image generator """

    threads: int = multiprocessing.cpu_count()
    background_audio_url: str | None = None

    prompt: str | None = None
    """ ai prompt to generate script """

    script: str | None = None
    """ script to use instead of prompt """

    script_duration: int = 30
    """ duration of the sentence in seconds """

    video_paths: list[str] = []


class StartResponse(BaseModel):
    video_file_path: str


class BaseEngine(ABC):
    def __init__(self, config: BaseGeneratorConfig):
        self.config = config
        self.cwd = config.cwd

        self.subtitle_generator = SubtitleGenerator(self)
        self.video_generator = VideoGenerator(self)

        self.synth_generator = SynthGenerator(self.cwd, config.synth_config)
        self.prompt_generator = PromptGenerator()
        self.image_generator = ImageGenerator(self.cwd, self.config.image_gen_config)
        self.threads: int = multiprocessing.cpu_count()

        self.db_available = True
 
    async def start(self) -> Any | StartResponse:
        pass
 
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5), after=log_attempt_number) # type: ignore
    async def post_complete(self, data: StartResponse):

        logger.debug(f"Post complete started with: {data.model_dump_json(indent=3)}")
        gif_path = await self.video_generator.create_gif(data.video_file_path)
        await self.cleanup()

    async def cleanup(self):
        try:
            # remove all individual speech files
            shutil.rmtree(self.synth_generator.base)
            self.db_available = True
            # shutil.rmtree(self.cwd)
        except Exception as e:
            logger.error(f"failed to remove speech path: {e}")

 