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
)
from app.utils.strings import split_by_dot_or_newline
from app.utils.path_util import download_resource


class ReelsMakerConfig(BaseGeneratorConfig):
    use_subway_surfers_background: bool = False
    """ Use dynamic sports/action videos as background instead of keyword-based videos """
    
    subway_surfers_videos: list[str] = []
    """ List of custom background video URLs or local file paths to use (sports, action, or any engaging content) """


def create_concat_file(clips):
    concat_filename = "concat_list.txt"
    with open(concat_filename, "w") as f:
        for clip in clips:
            f.write(f"file '{clip}'\n")
    return concat_filename


def concatenate_with_filelist(clips, output_path):
    concat_filename = create_concat_file(clips)

    # Run FFmpeg with the concat demuxer
    ffmpeg.input(concat_filename, format="concat", safe=0).output(
        output_path, c="copy"
    ).run(overwrite_output=True)

    return output_path


def concatenate_clips(clips, output_path):
    """
    Concatenates a list of video clips.
    Args:
    - clips (list of str): List of file paths to each video clip to concatenate.
    - output_path (str): Path to save the final concatenated video.
    """
    # Prepare input streams for each clip
    streams = [ffmpeg.input(clip) for clip in clips]

    # Use concat filter
    concatenated_stream = ffmpeg.concat(*streams, v=1, a=1).output(output_path)

    # Run FFmpeg
    concatenated_stream.run(overwrite_output=True)
    return output_path


class ReelsMaker(BaseEngine):
    def __init__(self, config: ReelsMakerConfig):
        super().__init__(config)

        self.config = config

        logger.info(f"Starting Reels Maker with: {self.config.model_dump()}")

    async def generate_script(self, sentence: str):
        logger.debug(f"Generating script from prompt: {sentence}")
        duration = f"{self.config.script_duration} seconds"
        sentence = await self.prompt_generator.genarate_script(
            video_type="narrator",
            sentence_prompt=sentence,
            duration=duration
        )
        return sentence.replace('"', "")

    async def generate_search_terms(self, user_prompt: str, max_hashtags: int = 10):
        logger.debug("Generating enhanced search terms from user prompt...")
        response = await self.prompt_generator.generate_enhanced_video_keywords(
            user_prompt=user_prompt, 
            max_keywords=max_hashtags
        )
        tags = [tag.replace("#", "") for tag in response.sentences]
        if len(tags) > max_hashtags:
            logger.warning(f"Truncated search terms to {max_hashtags} tags")
            tags = tags[:max_hashtags]

        logger.info(f"Generated enhanced search terms: {tags}")
        return tags

    async def get_subway_surfers_videos(self) -> list[str]:
        """Get Subway Surfers or engaging background videos"""
        logger.info("🎮 Using Subway Surfers background video mode...")
        
        # Use user-provided videos if available (prioritize local Subway Surfers files)
        if self.config.subway_surfers_videos:
            logger.info(f"Using {len(self.config.subway_surfers_videos)} user-provided Subway Surfers videos")
            return self.config.subway_surfers_videos
        
        # Search for dynamic sports footage
        logger.info("🔍 Searching for engaging sports background videos...")
        
        # Search terms for dynamic sports content
        sports_search_terms = [
            "basketball player dribbling close up",
            "soccer football action slow motion", 
            "skateboarding tricks urban",
            "running athlete training",
            "tennis player serving",
            "boxing training punching bag",
            "cycling bike racing",
            "swimming pool underwater"
        ]
        
        remote_urls = []
        max_videos = int(os.getenv("MAX_BG_VIDEOS", 8))
        
        for search_term in sports_search_terms[:max_videos]:
            logger.debug(f"🔍 Searching for: {search_term}")
            try:
                video_url = await self.video_generator.get_video_url(search_term=search_term)
                if video_url:
                    remote_urls.append(video_url)
                    logger.success(f"✅ Found sports video for: {search_term}")
                else:
                    logger.warning(f"❌ No video found for: {search_term}")
            except Exception as e:
                logger.warning(f"Error searching for {search_term}: {e}")
        
        if not remote_urls:
            logger.error("❌ No sports videos found! Please provide your own videos in subway_surfers_videos config.")
            raise ValueError("No sports videos available")
        
        logger.success(f"🏀 Found {len(remote_urls)} dynamic sports videos!")
        return remote_urls

    async def start(self) -> StartResponse:
        await super().start()

        self.background_music_path = None
        if self.config.background_audio_url:
            self.background_music_path = await download_resource(
                self.cwd, self.config.background_audio_url
            )

        # generate script from prompt
        if self.config.prompt:
            script = await self.generate_script(self.config.prompt)
        elif self.config.script:
            script = self.config.script
        else:
            raise ValueError("No prompt or sentence provided")

        # split script into sentences
        assert script is not None, "Script should not be None"

        sentences = split_by_dot_or_newline(script, 100)
        sentences = list(filter(lambda x: x != "", sentences))

        video_paths = []
        if self.config.video_paths:
            logger.info("Using video paths from client...")
            video_paths = self.config.video_paths
        elif self.config.use_subway_surfers_background:
            logger.info("🎮 Subway Surfers Background Mode Enabled! Using local Subway Surfers gameplay...")
            # Get Subway Surfers or custom background videos
            subway_surfers_urls = await self.get_subway_surfers_videos()
            
            # Handle both local files and remote URLs
            valid_paths = []
            tasks = []
            
            for video_source in subway_surfers_urls:
                # Check if it's a local file or remote URL
                if video_source.startswith(('http://', 'https://')):
                    # Remote URL - download it
                    task = asyncio.create_task(download_resource(self.cwd, video_source))
                    tasks.append(task)
                else:
                    # Local file - use directly
                    import os
                    if os.path.exists(video_source):
                        logger.success(f"✅ Using local Subway Surfers video: {video_source}")
                        valid_paths.append(video_source)
                    else:
                        logger.warning(f"❌ Local file not found: {video_source}")

            # Download remote files if any
            if tasks:
                local_paths = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Filter out None values and exceptions, keep only valid video paths
                for path in local_paths:
                    if path and not isinstance(path, Exception):
                        try:
                            # Quick validation that file exists and has size > 0
                            import os
                            if os.path.exists(path) and os.path.getsize(path) > 1024:  # At least 1KB
                                valid_paths.append(path)
                            else:
                                logger.warning(f"Skipping corrupted video: {path}")
                        except Exception as e:
                            logger.warning(f"Error validating video {path}: {e}")
                        
            video_paths.extend(valid_paths)
            
            logger.success(f"🎮 Using {len(video_paths)} Subway Surfers background videos!")
        else:
            logger.debug("Generating enhanced search terms from user prompt...")
            search_terms = await self.generate_search_terms(
                user_prompt=self.config.prompt, max_hashtags=10
            )

            # holds all remote urls
            remote_urls = []

            max_videos = int(os.getenv("MAX_BG_VIDEOS", 10))

            for search_term in search_terms[:max_videos]:
                # search for a related background video
                video_path = await self.video_generator.get_video_url(
                    search_term=search_term
                )
                if not video_path:
                    continue

                remote_urls.append(video_path)

            # download all remote videos at once
            tasks = []
            for url in remote_urls:
                task = asyncio.create_task(download_resource(self.cwd, url))
                tasks.append(task)

            local_paths = await asyncio.gather(*tasks)
            video_paths.extend(set(local_paths))

        if len(video_paths) == 0:
            raise ValueError("No video paths found available")

        data: list[TempData] = []

        # for each sentence, generate audio
        for sentence in sentences:
            audio_path = await self.synth_generator.synth_speech(sentence)
            data.append(
                TempData(
                    synth_clip=FileClip(audio_path),
                )
            )

        # TODO: fix me
        self.video_generator.config.background_music_path = self.background_music_path

        final_speech = ffmpeg.concat(
            *[item.synth_clip.ffmpeg_clip for item in data], v=0, a=1
        )

        # get subtitles from script
        subtitles_path = await self.subtitle_generator.generate_subtitles(
            sentences=sentences,
            durations=[item.synth_clip.real_duration for item in data],
        )

        # the max duration of the final video
        video_duration = sum(item.synth_clip.real_duration for item in data)

        # each clip should be 5 seconds long
        max_clip_duration = 5

        tot_dur: float = 0

        temp_videoclip: list[FileClip] = [
            FileClip(video_path, t=max_clip_duration) for video_path in video_paths
        ]

        final_clips: list[FileClip] = []

        while tot_dur < video_duration:
            for clip in temp_videoclip:
                remaining_dur = video_duration - tot_dur
                subclip_duration = min(
                    max_clip_duration, remaining_dur, clip.real_duration
                )
                subclip = FileClip(clip.filepath, t=subclip_duration).duplicate()

                final_clips.append(subclip)
                tot_dur += subclip_duration

                logger.debug(
                    f"Total duration after adding this clip: {tot_dur}, target is {video_duration}, clip duration: {subclip_duration}"
                )

                if tot_dur >= video_duration:
                    break

        final_video_path = await self.video_generator.generate_video(
            clips=final_clips,
            subtitles_path=subtitles_path,
            speech_filter=final_speech,
            video_duration=video_duration,
        )

        logger.info((f"Final video: {final_video_path}"))
        logger.info("video generated successfully!")

        return StartResponse(
            video_file_path=final_video_path,
        )