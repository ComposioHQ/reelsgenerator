import asyncio
import os

import ffmpeg
from loguru import logger

from app.base import (
    BaseEngine,
    BaseGeneratorConfig,
    FileClip,
    StartResponse,
    TempData,
    VideoAssetCacheItem,
)
from app.config import audios_cache_path, images_cache_path
from app.utils.strings import get_clip_duration, split_by_dot_or_newline
from app.utils.path_util import download_resource


class StoryTellerConfig(BaseGeneratorConfig):
    pass


class StoryTeller(BaseEngine):
    def __init__(self, config: StoryTellerConfig):
        super().__init__(config)

        self.config = config
        self.sentences: list[str] = []

        self.audio_paths = []
        self.audio_clip_paths = []
        self.final_speech_path = ""

    async def start(self) -> StartResponse:
        await super().start()

        if self.config.background_audio_url:
            self.config.video_gen_config.background_music_path = (
                await download_resource(
                    self.cwd, self.config.background_audio_url, audios_cache_path
                )
            )

        logger.info(
            f"Starting story teller with: {self.config.model_dump_json(indent=3)}"
        )

        script = self.config.script
        script = script.strip()  # type: ignore
        sentences = split_by_dot_or_newline(script, 80)
        sentences = [
            sentence.replace("\n", "").replace("\n", " ").replace("\\", "").strip()
            for sentence in sentences
        ]

        new_sentences = []
        image_prompts = []

        cached: list[VideoAssetCacheItem] = []

        for i, sentence in enumerate(sentences):
            if i < len(cached):  # Check if there is a corresponding cached item
                cached_item = cached[i]
                # TODO: check similarity with score 99%
                if cached_item.sentence == sentence:
                    new_sentences.append(cached_item.sentence)
                    image_prompts.append(cached_item.image_prompt)
                else:
                    logger.debug(f"new sentence (not in cache): {sentence}")
                    new_sentences.append(sentence)
            else:
                logger.debug(f"new sentence (no cache available): {sentence}")
                new_sentences.append(sentence)

        if len(image_prompts) == 0 or len(new_sentences) != len(image_prompts):
            logger.debug("generating new image prompts")
            image_resp = await self.prompt_generator.sentences_to_images(
                sentences=new_sentences,
                style=self.config.image_gen_config.style,
            )

            image_prompts = image_resp.image_prompts

        # generate image for each sentence and audio
        data: list[TempData] = []

        # all cached assets we need to re-transform their urls
        cache_items: list[VideoAssetCacheItem] = []

        # for generated image prompts, use the prompt to generate an image
        for i, (image_prompt, sentence) in enumerate(zip(image_prompts, new_sentences)):
            speech_path, image_path = await asyncio.gather(
                self.synth_generator.synth_speech(sentence),
                self.image_generator.generate_image(
                    prompt=image_prompt, sentence=sentence
                ),
            )

            speech_duration = get_clip_duration(speech_path)
            data.append(
                TempData(
                    synth_clip=FileClip(speech_path),
                    media_clip=FileClip(image_path, loop=1, t=speech_duration),
                )
            )

            image_path = os.path.join(images_cache_path, image_path)

            cache_items.append(
                VideoAssetCacheItem(
                    image_prompt=image_prompt,
                    media_url=image_path,
                    sentence=sentence,
                    tts_speech_url=speech_path,
                )
            )

        # generate subtitles
        subtitles_path = await self.subtitle_generator.generate_subtitles(
            sentences=new_sentences,
            durations=[item.synth_clip.real_duration for item in data],
        )

        # merge all audio clips into one
        max_video_duration = sum(item.synth_clip.real_duration for item in data)

        logger.debug(f"video duration: {round(max_video_duration / 60, 1)}mins")

        # merge all audios
        final_speech = ffmpeg.concat(
            *[item.synth_clip.ffmpeg_clip for item in data], v=0, a=1
        )
        output_path = await self.video_generator.generate_video(
            clips=[item.media_clip for item in data],  # type: ignore
            subtitles_path=subtitles_path,
            speech_filter=final_speech,
            video_duration=max_video_duration,
        )
        return StartResponse(
            video_file_path=output_path,
        )