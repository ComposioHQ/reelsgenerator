import asyncio
from app.reels_maker import ReelsMaker, ReelsMakerConfig
from app.base import BaseGeneratorConfig
import uuid

async def main():
    # Create configuration
    config = ReelsMakerConfig(
        job_id=str(uuid.uuid4()),  # Generate a unique job ID
        prompt="Create a short video about the top 5 AI tools that are revolutionizing productivity in 2025. Focus on practical applications and benefits. Make it engaging and informative.",
        model_name="gpt-4",
        background_audio_url="https://www.youtube.com/watch?v=8HXxEixGM_Y",  # Replace with actual background music URL
        output_path="ai_tools_video.mp4",
        duration="60 seconds"
    )

    # Initialize ReelsMaker
    reels_maker = ReelsMaker(config)

    # Generate and save the video
    try:
        response = await reels_maker.start()
        print(f"Video generated successfully! Saved to: {response.output_path}")
    except Exception as e:
        print(f"Error generating video: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 