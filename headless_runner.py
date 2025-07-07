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
    # This replaces the input from the Streamlit UI.
    config = ReelsMakerConfig(
        job_id=str(uuid4()),
        prompt="Create an inspirational story about overcoming challenges and achieving your dreams. Talk about the importance of persistence, learning from failures, and celebrating small victories along the way. Include specific examples of how setbacks can become stepping stones to success.",
        script_duration=60,  # Target 60 seconds for a longer video
        # Better video generation settings for clearer subtitles
        video_gen_config=VideoGeneratorConfig(
            fontsize=2,  # Larger font size like we had with Arial
            stroke_color="#000000",  # Black stroke for better contrast
            text_color="#ffffff",   # White text
            stroke_width=6,  # Thicker stroke like before
            font_name="Arial",  # Back to Arial like before
            subtitles_position="center,center",
            watermark_path_or_text="VoidFace",
            watermark_type="text",
            aspect_ratio="9:16",
            color_effect="gray",
        ),
        # You can customize other configs here. For example, to use a different voice:
        # from app.synth_gen import SynthConfig
        # synth_config=SynthConfig(voice="en_us_002", voice_provider="tiktok"),
    )

    logger.info(f"Using config: {config.model_dump_json(indent=2)}")

    # 2. Instantiate ReelsMaker
    reels_maker = ReelsMaker(config)

    # 3. Start the video generation process
    try:
        logger.info("Generating reel... This might take a few minutes.")
        output = await reels_maker.start()
        logger.success("Reel generated successfully!")
        logger.info(f"Output video path: {output.video_file_path}")
        print(f"\n✅ Video saved to: {output.video_file_path}")
    except Exception as e:
        logger.exception("An error occurred during reel generation.")
        print(f"\n❌ An error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 