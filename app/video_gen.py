import multiprocessing
import os
import random
from typing import TYPE_CHECKING, Literal
from pathlib import Path

from app.effects import zoom_in_effect, zoom_out_effect
from app.utils.strings import (
    FFMPEG_TYPE,
    FileClip,
    adjust_audio_to_target_dBFS,
    get_video_size,
    web_color_to_ass,
)
from loguru import logger
from app.pexel import search_for_stock_videos
from PIL import Image
from PIL import Image as pil
from pkg_resources import parse_version
from pydantic import BaseModel
import ffmpeg


if parse_version(pil.__version__) >= parse_version("10.0.0"):
    Image.ANTIALIAS = Image.LANCZOS  # type: ignore

if TYPE_CHECKING:
    from app.base import BaseEngine

# TODO: implement me
positions = {
    "center": ["center", "center"],
    "left": ["left", "center"],
    "right": ["right", "center"],
    "top": ["center", "top"],
    "bottom": ["center", "bottom"],
}


class VideoGeneratorConfig(BaseModel):
    fontsize: int = 70
    stroke_color: str = "#ffffff"
    text_color: str = "#ffffff"
    stroke_width: int | None = 5
    font_name: str = "Luckiest Guy"
    bg_color: str | None = None
    subtitles_position: str = "center,center"
    threads: int = multiprocessing.cpu_count()

    watermark_path_or_text: str | None = "VoidFace"
    watermark_opacity: float = 0.5
    watermark_type: Literal["image", "text", "none"] = "text"
    background_music_path: str | None = None

    aspect_ratio: str = "9:16"
    """ aspect ratio of the video """

    color_effect: str = "gray"


class VideoGenerator:
    def __init__(
        self,
        base_class: "BaseEngine",
    ):
        self.job_id = base_class.config.job_id
        self.config = base_class.config.video_gen_config
        self.cwd = base_class.cwd
        self.base_engine = base_class

        self.ffmpeg_cmd = "ffmpeg"  # Use system FFmpeg

    async def get_video_url(self, search_term: str) -> str | None:
        try:
            urls = await search_for_stock_videos(
                limit=2,
                min_dur=10,
                query=search_term,
            )
            return urls[0] if len(urls) > 0 else None
        except Exception as e:
            logger.error(f"Consistency Violation: {e}")

        return None

    def apply_subtitle(self, clip, subtitle_path: str):
        position = self.config.subtitles_position.split(",")[0]
        styles = {
            "bottom": "Alignment=2",
            "center": "Alignment=10",
            "top": "Alignment=6",
        }

        text_color = web_color_to_ass(self.config.text_color)
        # Use black stroke for better contrast against white text
        stroke_color = web_color_to_ass("#000000")  # Black stroke
        font_size = round(self.config.fontsize / 3)  # Remove minimum limit for full control

        style = (
            f"FontName={self.config.font_name},FontSize={font_size},"
            f"PrimaryColour={text_color},OutlineColour={stroke_color},Outline={self.config.stroke_width},"
            f"Bold=1,Spacing=0.1,ScaleX=50,ScaleY=50,MarginLeft=10,MarginRight=10,"
            f"{styles.get(position, 'Alignment=10')}"
        )

        # Use the correct fonts directory path
        fonts_dir = "./fonts"
        return clip.filter(
            "subtitles", filename=subtitle_path, fontsdir=fonts_dir, force_style=style
        )

    def add_audio_mix(self, video_stream, background_music_filter, tts_audio_filter):
        audio_mix = ffmpeg.filter(
            stream_spec=[background_music_filter, tts_audio_filter],
            filter_name="amix",
            duration="longest",
            dropout_transition=0,
        )
        return ffmpeg.concat(video_stream, audio_mix, v=1, a=1)

    def concatenate_clips(self, inputs: list[FileClip], effects: list = []):
        processed_clips = []
        for data in inputs:
            clip = data.ffmpeg_clip

            if len(effects) > 0:
                effect = random.choice(effects)
                clip = effect(clip)
            clip = clip.filter("scale", 1080, 1920)

            # apply gray effect for motivational video
            if (
                self.config.color_effect == "gray"
                and self.base_engine.config.video_type == "motivational"
            ):
                clip = clip.filter("format", "gray")

            processed_clips.append(clip)
        final_video = ffmpeg.concat(*processed_clips, v=1, a=0)
        return final_video

    async def generate_video(
        self,
        clips: list[FileClip],  # the list of clips from ffmpeg
        speech_filter: FFMPEG_TYPE,
        subtitles_path: str,
        video_duration: float,
    ) -> str:
        logger.info("Generating video...")
        effects = [zoom_out_effect, zoom_in_effect]

        # Define output path
        output_path = (Path(self.cwd) / f"{self.job_id}_final.mp4").as_posix()

        if self.base_engine.config.video_type == "motivational":
            effects = []

        video_stream = self.concatenate_clips(clips, effects)
        video_stream = self.apply_watermark(video_stream)
        video_stream = self.apply_subtitle(video_stream, subtitles_path)
        
        # Handle background music only if available
        if self.config.background_music_path:
            # music must end at the end of the speech, add extra 3 seconds to make it look good
            music_input = ffmpeg.input(
                adjust_audio_to_target_dBFS(self.config.background_music_path),
                t=video_duration,
            )
            video_stream = self.add_audio_mix(
                video_stream=video_stream,
                tts_audio_filter=speech_filter,
                background_music_filter=music_input,
            )
        else:
            # No background music, just add the speech audio
            video_stream = ffmpeg.concat(video_stream, speech_filter, v=1, a=1)

        output = ffmpeg.output(
            video_stream,
            output_path,
            vcodec="libx264",
            acodec="aac",
            preset="veryfast",
            threads=2,
            # loglevel="quiet",
        )

        logger.debug(f"FFMPEG CMD: {output.get_args()}")
        output.run(overwrite_output=True, cmd=self.ffmpeg_cmd)

        logger.info("Video generation complete.")
        return output_path

    # def get_background_audio(self, video_clip: VideoClip, song_path: str) -> AudioClip:
    #     """Takes the original audio and adds the background audio"""
    #     logger.info(f"Getting background music: {song_path}")

    #     def adjust_audio_to_target_dBFS(audio_file_path: str, target_dBFS=-30.0):
    #         audio = AudioSegment.from_file(audio_file_path)
    #         change_in_dBFS = target_dBFS - audio.dBFS
    #         adjusted_audio = audio.apply_gain(change_in_dBFS)
    #         adjusted_audio.export(audio_file_path, format="mp3")
    #         logger.info(f"Adjusted audio to target dBFS: {target_dBFS}")
    #         return audio_file_path

    #     # set the volume of the song to 10% of the original volume
    #     song_path = adjust_audio_to_target_dBFS(song_path)

    #     background_audio = AudioFileClip(song_path)

    #     if background_audio.duration < video_clip.duration:
    #         # calculate how many times the background audio needs to repeat
    #         repeats_needed = int(video_clip.duration // background_audio.duration) + 1

    #         # create a list of the background audio repeated
    #         background_audio_repeated = concatenate_audioclips(
    #             [background_audio] * repeats_needed
    #         )

    #         # trim the repeated audio to match the video duration
    #         background_audio_repeated = background_audio_repeated.subclip(
    #             0, video_clip.duration
    #         )
    #     else:
    #         background_audio_repeated = background_audio.subclip(0, video_clip.duration)

    #     comp_audio = CompositeAudioClip([video_clip.audio, background_audio_repeated])

    #     return comp_audio

    def crop(self, clip: FileClip) -> FFMPEG_TYPE:
        width, height = get_video_size(clip.filepath)
        aspect_ratio = width / height
        ffmpeg_clip = clip.ffmpeg_clip

        if aspect_ratio < 0.5625:
            crop_height = int(width / 0.5625)
            return ffmpeg_clip.filter(
                "crop", w=width, h=crop_height, x=0, y=(height - crop_height) // 2
            )
        else:
            crop_width = int(0.5625 * height)
            return ffmpeg_clip.filter(
                "crop", w=crop_width, h=height, x=(width - crop_width) // 2, y=0
            )

    def apply_watermark(self, video_stream):
        """Adds a watermark to the bottom-right of the video."""

        sysfont = os.path.join(os.getcwd(), "narrator/sys/fonts/luckiestguy.ttf")

        # Check if watermark path/text is set and watermark type is valid
        if (
            not self.config.watermark_path_or_text
            or self.config.watermark_type == "none"
        ):
            return video_stream  # No watermark, return original stream

        # Text-based watermark
        if self.config.watermark_type == "text":
            watermark_text = self.config.watermark_path_or_text
            video_stream = video_stream.filter(
                "drawtext",
                text=watermark_text,
                x="if(lt(mod(t,20),10), (main_w-text_w)-16, if(lt(mod(t,20),10), 16, if(lt(mod(t,20),15), 16, (main_w-text_w)-16)))",
                y="if(lt(mod(t,20),10), (main_h-text_h)-100, if(lt(mod(t,20),10), 50, if(lt(mod(t,20),15), (main_h-text_h)-100, 50)))",
                fontsize=40,
                fontcolor="white",
                fontfile=sysfont,
            )
            logger.warning(f"Using text watermark with font: {sysfont}")

        # Image-based watermark
        elif self.config.watermark_type == "image":
            watermark_path = self.config.watermark_path_or_text
            watermark = ffmpeg.input(watermark_path)

            # Resize watermark to a height of 100 while maintaining aspect ratio
            watermark = watermark.filter("scale", -1, 100)

            # Overlay the watermark in the bottom-right corner with 8px padding
            video_stream = ffmpeg.overlay(
                video_stream,
                watermark,
                x="(main_w-overlay_w)-8",
                y="(main_h-overlay_h)-8",
            )

        logger.debug("Added watermark to video.")
        return video_stream

    async def create_gif(
        self, master_video_path: str, start_time: float = 1.0, end_time: float = 1.5
    ) -> str:
        logger.debug("Creating GIF...")
        gif_path = f"{self.cwd}/{self.job_id}.gif"

        (
            ffmpeg.input(master_video_path, ss=start_time, t=end_time - start_time)
            .filter("fps", fps=6)
            .filter("scale", "iw/2", "ih/2")
            .output(gif_path, format="gif", loop=0, pix_fmt="rgb24")
            .run(overwrite_output=True)
        )

        return gif_path