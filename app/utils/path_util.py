import os
from app.config import videos_cache_path
import asyncio
import hashlib
import os
import shutil

import aiohttp
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed


def text_to_sha256_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()



def search_file(directory, file) -> str | None:
    assert os.path.isdir(directory)
    import re

    pattern = re.compile(re.escape(file), re.IGNORECASE)
    for cur_path, directories, files in os.walk(directory):
        for filename in files:
            if pattern.search(filename):
                return os.path.join(directory, cur_path, filename)
    return None


@retry(stop=stop_after_attempt(5), wait=wait_fixed(5)) # type: ignore
async def download_resource(
    dir, url, cache_dir=videos_cache_path, disable_cache=False
) -> str:
    filename = os.path.basename(url)
    file_path = os.path.join(dir, filename)

    if not disable_cache:
        file_cache_path = search_file(cache_dir, filename)
        if file_cache_path:
            shutil.copy2(file_cache_path, file_path)
            logger.info(f"Found resource in cache: {file_cache_path}")
            return file_path

    async with aiohttp.ClientSession() as session:
        logger.info(f"Downloading resource from: {url}")
        async with session.get(url) as response:
            with open(file_path, "wb") as f:
                f.write(await response.read())
                logger.debug(f"Downloaded resource from: {url}")

                # save to cache audios
                shutil.copy2(file_path, cache_dir)
                return os.path.join(dir, os.path.basename(url))

