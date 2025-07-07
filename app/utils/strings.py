import ffmpeg
from loguru import logger
import spacy

import os
import shutil
import tempfile
from typing import Any
from cuid2 import Cuid
import ffmpeg
from loguru import logger
from pydub import AudioSegment

def split_by_dot_or_newline(text: str, min_char_len: int = 80) -> list[str]:
    """Splits text into sentences using spacy and merges short sentences to a minimum character length."""

    nlp = spacy.load("en_core_web_sm")
    doc = nlp(text)
    sentences = [sent.text.strip() for sent in doc.sents]

    # Merge sentences that are too short
    merged_sentences = []
    current_sentence = ""

    for sentence in sentences:
        if len(current_sentence) + len(sentence) < min_char_len:
            current_sentence += " " + sentence
        else:
            if current_sentence:
                merged_sentences.append(current_sentence.strip())
            current_sentence = sentence

    # Append the last sentence if not empty
    if current_sentence:
        merged_sentences.append(current_sentence.strip())

    merged_sentences = [sentence.replace("\n", " ") for sentence in merged_sentences]

    return merged_sentences



def log_attempt_number(retry_state):
    """return the result of the last call attempt"""
    logger.error(f"Retrying: {retry_state.attempt_number}...")


# the type of the ffmpeg from 'import ffmpeg'
FFMPEG_TYPE = Any


class FileClip:
    def __init__(self, filepath: str, **kwargs):
        self.filepath = filepath
        self.kwargs = kwargs
        self.real_duration = get_clip_duration(self.filepath)
        self.ffmpeg_clip: FFMPEG_TYPE = ffmpeg.input(filepath, **kwargs)

        if kwargs.get("t"):
            self.duration = float(kwargs.get("t"))  # type: ignore
        else:
            self.duration = self.real_duration

    def duplicate(self) -> "FileClip":
        duplicates_dir = os.path.join(os.path.dirname(self.filepath), "duplicates")
        os.makedirs(duplicates_dir, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            delete=False,
            dir=duplicates_dir,
            suffix=f"_{os.path.basename(self.filepath)}",
        ) as temp_file:
            shutil.copyfile(self.filepath, temp_file.name)

        return FileClip(temp_file.name, **self.kwargs)


def get_video_size(input_path: str) -> tuple[int, int]:
    # Use ffprobe to retrieve video metadata
    probe = ffmpeg.probe(input_path)
    video_stream = next(
        (stream for stream in probe["streams"] if stream["codec_type"] == "video"), None
    )
    if video_stream is None:
        raise ValueError("No video stream found")

    width = int(video_stream["width"])
    height = int(video_stream["height"])
    return width, height


def get_clip_duration(file_path):
    try:
        probe = ffmpeg.probe(file_path)
        duration = float(probe["format"]["duration"])
        duration = round(duration, 2)
    except Exception:
        logger.warning(f"Failed to get duration of {file_path}")
        duration = 0

    return duration


def web_color_to_ass(color_code: str, alpha: str = "00") -> str:
    # Strip the `#` if it's there
    color_code = color_code.lstrip("#")

    # Ensure the color code is valid
    if len(color_code) != 6:
        raise ValueError(
            f"Invalid color code format, {color_code}. Must be a 6-character hex code."
        )

    # Split into Red, Green, Blue
    red = color_code[:2]
    green = color_code[2:4]
    blue = color_code[4:]

    # ASS format is &HAABBGGRR&
    ass_color = f"&H{alpha}{blue}{green}{red}&"
    return ass_color


def adjust_audio_to_target_dBFS(audio_file_path: str | None, target_dBFS=-30.0):
    if not audio_file_path:
        return None
    audio = AudioSegment.from_file(audio_file_path)
    change_in_dBFS = target_dBFS - audio.dBFS
    adjusted_audio = audio.apply_gain(change_in_dBFS)
    adjusted_audio.export(audio_file_path, format="mp3")
    logger.info(f"Adjusted audio to target dBFS: {target_dBFS}")
    return audio_file_path



def make_cuid(prefix: str) -> str:
    """
    Generates a CUID (Collision-resistant internal identifier) with the given prefix.

    Args:
        prefix (str): The prefix to be added to the generated CUID.

    Returns:
        str: The generated CUID with the prefix appended.

    """
    id = Cuid(length=23).generate()
    return f"{prefix}{id}"
