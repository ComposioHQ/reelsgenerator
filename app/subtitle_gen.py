import os
from datetime import timedelta

import srt_equalizer
from loguru import logger
from pydantic import BaseModel

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.base import BaseEngine


class SubtitleConfig(BaseModel):
    cwd: str
    job_id: str
    max_chars: int = 15


class SubtitleGenerator:
    def __init__(self, base_class: "BaseEngine"):
        self.base_class = base_class
        self.config = SubtitleConfig(
            cwd=base_class.cwd, job_id=base_class.config.job_id
        )

    async def wordify(self, srt_path: str, max_chars) -> None:
        """Wordify the srt file, each line is a word

        Example:
        --------------
        1
        00:00:00,000 --> 00:00:00,333
        Imagine

        2
        00:00:00,333 --> 00:00:00,762
        waking up

        3
        00:00:00,762 --> 00:00:01,143
        each day
        ----------------
        """

        srt_equalizer.equalize_srt_file(srt_path, srt_path, max_chars)

    async def generate_subtitles(
        self,
        sentences: list[str],
        durations: list[float],
    ) -> str:
        logger.info("Generating subtitles...")

        subtitles_path = os.path.join(self.config.cwd, f"{self.config.job_id}.srt")

        subtitles = await self.locally_generate_subtitles(
            sentences=sentences, durations=durations
        )
        with open(subtitles_path, "w+") as file:
            file.write(subtitles)

        await self.wordify(srt_path=subtitles_path, max_chars=self.config.max_chars)
        return subtitles_path

    async def locally_generate_subtitles(
        self, sentences: list[str], durations: list[float]
    ) -> str:
        logger.debug("using local subtitle generation...")

        def convert_to_srt_time_format(total_seconds):
            # Convert total seconds to the SRT time format: HH:MM:SS,mmm
            if total_seconds == 0:
                return "0:00:00,0"
            return str(timedelta(seconds=total_seconds)).rstrip("0").replace(".", ",")

        start_time = 0
        subtitles = []

        for i, (sentence, duration) in enumerate(zip(sentences, durations), start=1):
            end_time = start_time + duration

            # Format: subtitle index, start time --> end time, sentence
            subtitle_entry = f"{i}\n{convert_to_srt_time_format(start_time)} --> {convert_to_srt_time_format(end_time)}\n{sentence}\n"
            subtitles.append(subtitle_entry)

            start_time += duration  # Update start time for the next subtitle

        return "\n".join(subtitles)