import random
import typing
from typing import Literal
from app.utils.strings import log_attempt_number
from langchain_community.cache import SQLiteCache
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import ChatPromptTemplate
from langchain_core.globals import set_llm_cache
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, Field
from app.config import settings
from tenacity import retry, stop_after_attempt, wait_fixed
from app.config import llm_cache_path




class HashtagsSchema(BaseModel):
    """the hashtags response"""

    sentences: list[str] = Field(description="List of search terms for the sentence")


class ImageLLMResponse(BaseModel):
    """the image prompt response"""

    image_prompts: list[str] = Field(description="List of MidJourney image prompt")


class ImagePromptResponses(BaseModel):
    image_prompts: list[str] = []
    sentences: list[str] = []


class StoryMiscResponse(BaseModel):
    """Additional properties extracted from the script or added to the video"""

    hook_title: str = Field(
        "",
        description="Generate a hook for the story/script. eg: what will happen if the hunter kills the dragon?  Eg 2. Is Free Will an Illusion?",
    )
    post_title: str = Field(
        "",
        description="Generate a social media post title, for the beginning of the story/script",
    )
    hashtags: list[str] = Field(
        [], description="Generate 8-12 relevant hashtags for the story/script"
    )


StoryPromptType = Literal["fantasy story", "motivational quote"] | str


class PromptGenerator:
    def __init__(self, test_mode: bool = False):
        set_llm_cache(SQLiteCache(database_path=f"{llm_cache_path}/llm_cache.db"))

        self.test_mode = test_mode
        self.model = ChatOpenAI(model=settings.OPENAI_MODEL_NAME)

    async def genarate_script(
        self,
        video_type: StoryPromptType,
        sentence_prompt: str,
        duration: str = "30 seconds",
    ) -> str:
        """generates a sentence from a prompt"""

        system_tmpl = """You are a skilled storyteller who creates engaging short videos for social media. You write scripts that are easy to understand and connect with people's real lives.

CORE RULES:
- Use simple, everyday words that anyone can understand
- Tell specific, real stories with actual examples and names
- Avoid generic advice - give concrete, actionable insights
- Connect ideas to real people's experiences and current events
- Include specific numbers, dates, or facts when possible
- Make it personal and relatable, not abstract

AVOID: Generic phrases like "success comes to those who," "the key is," "remember that," or vague motivational speak."""

        user_tmpl = """
Create a {duration} voiceover script for a '{video_type}' about the topic below.

REQUIREMENTS:
- Use simple words (8th grade reading level)
- Include specific real-life examples, names, or stories 
- Give concrete, actionable insights instead of generic advice
- Connect to current events, famous people, or relatable situations
- Make it personal and engaging, not abstract
- Include specific details (numbers, dates, companies, people)
- Avoid clichés and overused motivational phrases

TOPIC: {sentence}

Write ONLY the voiceover text. No music cues, no parentheses, no stage directions.
 """

        prompt = ChatPromptTemplate(
            [
                ("system", system_tmpl),
                ("human", user_tmpl),
            ]
        )

        self.model.temperature = random.uniform(0.5, 1.2)
        chain = prompt | self.model | StrOutputParser()

        logger.debug(f"Generating sentence from prompt: {sentence_prompt}")

        if self.test_mode:
            p = prompt.format(
                video_type=video_type, sentence=sentence_prompt, duration=duration
            )
            return p

        return await chain.ainvoke(
            {
                "sentence": sentence_prompt,
                "video_type": video_type,
                "duration": duration,
            }
        )

    # depreciated
    async def generate_sentence(self, sentence: str) -> str:
        """generates a sentence from a prompt"""

        tmpl = """
You are a skilled storyteller who creates engaging motivational content. Write a short, powerful narrative that uses simple words and real-life examples.

RULES:
- Use everyday language anyone can understand
- Include specific examples, real stories, or concrete details
- Avoid generic motivational clichés
- Make it personal and relatable
- Connect to real experiences people have

TOPIC: {sentence}

Write only the narrative text, keep it short and impactful.
 """

        prompt = ChatPromptTemplate.from_template(tmpl)

        chain = prompt | self.model | StrOutputParser()

        logger.debug(f"Generating sentence from prompt: {sentence}")
        return await chain.ainvoke({"sentence": sentence})

    async def generate_stock_image_keywords(self, sentence: str) -> HashtagsSchema:
        """generates search keywords from a sentence"""

        system_template = """
generate pexels.com search terms for the sentence below, the search keywords will be used to query an API:

{format_instructions}

[(examples)]:
Timing and letting go, Weakness and strength, Focus and hustle, Resonate with life etc...

[(sentence)]:
{sentence}
 """

        parser = PydanticOutputParser(pydantic_object=HashtagsSchema)
        prompt = ChatPromptTemplate.from_messages(
            messages=[("system", system_template), ("user", "{sentence}")]
        )
        prompt = prompt.partial(format_instructions=parser.get_format_instructions())

        chain = prompt | self.model | parser

        logger.debug(f"Generating sentence from prompt: {sentence}")
        return await chain.ainvoke({"sentence": sentence})

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5), after=log_attempt_number) # type: ignore
    async def sentences_to_images(
        self,
        sentences: list[str],
        style: str,
    ) -> ImagePromptResponses:
        user_template = """
You are a master of crafting detailed visual narratives. Your task is to generate descriptions of scenes for an animator, based on a story. Each scene description will guide the animator in creating the corresponding visual frames for the video.
Respond only with vivid, intricate descriptions of the scenes. Focus exclusively on providing the animator with everything they need to visualize characters, locations, and concepts clearly and consistently.

For each paragraph, you must:
- Describe a new scene, environment, or characters, while preserving continuity with recurring elements and any significant objects in meticulous detail
- Use keywords and descriptive phrases rather than full sentences.
- Do not include titles, names, or captions.

Examples:
- Caesar (tall, muscular frame, with a sharp jawline and piercing brown eyes, wearing a laurel wreath, ornate armor with gold detailing, and a crimson cape flowing in the wind), standing on a grassy hilltop under a cloudy sky.
- A small, dimly lit room with worn wooden furniture, a single flickering candle casting shadows on the cracked walls, and an old woman (slightly hunched, wearing a faded shawl, with wisps of gray hair escaping from under a knitted cap) gazing thoughtfully out of a tiny window.
- A bustling marketplace, with colorful stalls lining the cobblestone streets, vendors shouting offers to passersby, and a young boy (dressed in ragged clothes, with tousled hair and bright green eyes) darting through the crowd, clutching a loaf of bread.

You will be penalized if descriptions are incomplete or lack detail, or if any additional text (headings, etc.) is included.
The visual narrative should be rich and immersive, allowing the animator to seamlessly create MidJourney-style artwork from your descriptions.

{format_instructions}

[(Paragraphs)]:
{sentences}

You must generate a total of {total_count} descriptions, each preserving a coherent visual narrative and maintaining distinct character features throughout.
"""

        parser = PydanticOutputParser(pydantic_object=ImageLLMResponse)

        formated_sentences = "- " + "\n- ".join(sentences)

        prompt = ChatPromptTemplate.from_messages(messages=[("system", user_template)])
        prompt = prompt.partial(
            format_instructions=parser.get_format_instructions(),
            total_count=len(sentences),
        )

        chain = prompt | self.model | parser

        logger.debug("Generating image prompts")
        data = await chain.ainvoke({"sentences": formated_sentences, "style": style})

        if len(data.image_prompts) != len(sentences):
            raise ValueError(
                f"Expected {len(sentences)} image prompts, got {len(data.image_prompts)}"
            )

        logger.info(f"Generated {len(data.image_prompts)} image prompts")
        logger.debug(f"image prompts: {data.image_prompts}")
        return ImagePromptResponses(
            sentences=sentences, image_prompts=data.image_prompts
        )

    async def generate_video_misc_info(self, script: str) -> StoryMiscResponse:
        """generates video misc info from a script"""

        system_template = """
Extracts relevant information from the script below.

{format_instructions}

[(Script)]:
{script}
"""

        logger.debug("Generating video misc info")

        parser = PydanticOutputParser(pydantic_object=StoryMiscResponse)

        prompt = ChatPromptTemplate.from_messages(
            messages=[("system", system_template)]
        )
        prompt = prompt.partial(
            format_instructions=parser.get_format_instructions(),
        )

        chain = prompt | self.model | parser
        data = await chain.ainvoke({"script": script})
        data = typing.cast(StoryMiscResponse, data)

        # removed # from hashtags - we only need the tag for social media
        data.hashtags = [
            tag if not tag.startswith("#") else tag.replace("#", "")
            for tag in data.hashtags
        ]

        return data
