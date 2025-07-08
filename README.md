# ReelsMaker - Headless Video Generation

ReelsMaker is a Python-based application designed to create captivating faceless videos for social media platforms like TikTok and YouTube. This version focuses on headless functionality with YouTube integration via MCP Composio.

## Features

- **AI-Powered Content Generation**: Automatically generate creative scripts for your video content
- **Text-to-Speech**: Use TikTok or ElevenLabs voices to add synthetic narration
- **Auto Subtitles**: Generate professional subtitles with customizable fonts and styling
- **Background Videos**: Automatically fetch relevant stock videos from Pexels
- **Headless Operation**: Run without UI for automation and batch processing
- **YouTube Integration**: Upload generated videos directly to YouTube via MCP Composio

## Installation

```sh
git clone <your-repo-url>
cd reelsmaker
```

Create a virtual environment and install dependencies:

```sh
poetry shell
poetry install
```

Copy and update the environment file:

```sh
cp .env.example .env
```

Edit `.env` with your API keys:
```
OPENAI_API_KEY="your_openai_api_key_here"
PEXELS_API_KEY="your_pexels_api_key_here"
TOGETHER_API_KEY="your_together_api_key_here"
SENTRY_DSN=""
OPENAI_MODEL_NAME="gpt-4-turbo"
```

Download required spaCy model:

```sh
poetry run python -m spacy download en_core_web_sm
```

## Required Assets

### Background Video Download

For Subway Surfers background videos, download the gameplay video from:

**YouTube Link**: https://youtu.be/QPW3XwBoQlw?feature=shared

1. Use any YouTube downloader tool (e.g., yt-dlp, online converters)
2. Download the video in MP4 format
3. Place the downloaded file in your project directory
4. The system will automatically use it for background gameplay footage

**Note**: Ensure the downloaded video file is named appropriately and is accessible in your project directory.

## Usage

### Headless Video Generation

Run the headless script to generate videos:

```sh
poetry run python headless_runner.py
```

### YouTube Integration Setup

1. **Go to MCP Composio Dashboard**
   - Visit: https://mcp.composio.dev
   - Sign in to your account

2. **Authenticate YouTube**
   - Go to the dashboard
   - Search for "youtube" 
   - Click on YouTube and authenticate with your Google account

3. **Create MCP Server**
   - After authentication, create a new MCP Server
   - Copy the terminal command shown after creation

4. **Run MCP Server**
   - Run the copied terminal command in your terminal
   - This will start the MCP server for YouTube integration

5. **Use MCP Client**
   - Use your MCP client to connect to the server
   - Upload and post the generated videos directly to YouTube

## Configuration

You can customize video generation by modifying the `ReelsMakerConfig` in `headless_runner.py`:

- `prompt`: Content theme for your video
- `script_duration`: Target video length in seconds
- `fontsize`: Subtitle font size
- `font_name`: Font family for subtitles
- `stroke_color` / `text_color`: Subtitle styling
- `watermark_path_or_text`: Custom watermark

## API Keys Required

- **OpenAI**: For script generation and content creation
- **Pexels**: For stock video downloads
- **Together AI**: For enhanced AI capabilities
- **ElevenLabs** (optional): For premium voice synthesis

## Output

Generated videos are saved in the `cache/` directory with the following structure:
- High-quality MP4 format
- 9:16 aspect ratio (optimized for mobile)
- Professional subtitles with custom styling
- Background music support (optional)

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
