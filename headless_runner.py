import asyncio
from uuid import uuid4

from loguru import logger

from app.reels_maker import ReelsMaker, ReelsMakerConfig
from app.video_gen import VideoGeneratorConfig

# Note: This script assumes you have a .env file in the root directory
# with your API keys, for example:
# OPENAI_API_KEY="sk-..."
# PEXELS_API_KEY="..."
# ELEVENLABS_API_KEY="..."


async def main():
    """
    Runs the ReelsMaker without the Streamlit frontend.
    """
    logger.info("Starting headless ReelsMaker...")

    # 1. Create a configuration object
    # Configuration for headless video generation.
    config = ReelsMakerConfig(
        job_id=str(uuid4()),
        prompt="Create a short test story about AI helping people be more productive. Make it engaging and brief.",
        script_duration=30,
        video_gen_config=VideoGeneratorConfig(
            fontsize=2,
            stroke_color="#000000",
            text_color="#ffffff",
            stroke_width=6,
            font_name="Arial",
            subtitles_position="center,center",
            watermark_path_or_text="AI Journey",
            watermark_type="text",
            aspect_ratio="9:16",
            color_effect="vibrant",
        ),
    )

    logger.info(f"Using config: {config.model_dump_json(indent=2)}")

    # 2. Instantiate ReelsMaker
    reels_maker = ReelsMaker(config)

    # 3. Start the video generation process

    logger.info("Generating reel about AI...")
    output = await reels_maker.start()
    logger.success("Reel generated successfully!")
    logger.info(f"Output video path: {output.video_file_path}")
    logger.info("Reel generated successfully!")
    logger.info(f"Output video path: {output.video_file_path}")
        



if __name__ == "__main__":
    asyncio.run(main()) 