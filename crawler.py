#!/usr/bin/env python3
"""Fudan University Course Data Crawler"""

import argparse
import asyncio
import json
import logging
import ssl
from argparse import Namespace
from typing import Any


import aiohttp
from tqdm.asyncio import tqdm_asyncio


class Args(Namespace):
    semester_id: int
    output: str

API_URL = "https://fdjwgl.fudan.edu.cn/student/for-all/lesson-search/semester/{sid}/search/504"
PAGE_SIZE = 1000

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def fetch_courses(session: aiohttp.ClientSession, semester_id: int) -> list[dict[str, Any]]:
    """Fetch all courses for a given semester."""
    url = API_URL.format(sid=semester_id)

    # First request to get total count
    async with session.get(url, params={"queryPage__": "1,1"}) as resp:
        total = (await resp.json())["_page_"]["totalRows"]

    # Calculate number of pages needed
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

    # Fetch all pages concurrently with progress bar
    async def fetch_page(page: int) -> list[dict[str, Any]]:
        async with session.get(url, params={"queryPage__": f"{page},{PAGE_SIZE}"}) as resp:
            return (await resp.json())["data"]

    tasks = [fetch_page(p) for p in range(1, total_pages + 1)]
    pages = await tqdm_asyncio.gather(*tasks, desc="Fetching pages")
    return [course for page in pages for course in page]


def transform(raw: dict[str, Any]) -> dict[str, Any]:
    """Transform API response to RawJwfwCourse format."""
    return {
        "name": raw.get("course", {}).get("nameZh", ""),
        "no": raw.get("code", ""),
        "teachers": ",".join(t["person"]["nameZh"] for t in raw.get("teacherAssignmentList", [])),
        "credits": float(raw.get("course", {}).get("credits", 0)),
        "department": raw.get("openDepartment", {}).get("nameZh", ""),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl course data from Fudan University")
    parser.add_argument("-s", "--semester-id", type=int, required=True, help="Semester ID (e.g., 504)")
    parser.add_argument("-o", "--output", default="courses.json", help="Output file path")
    args = parser.parse_args(namespace=Args())

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as session:
        logger.info("Fetching courses for semester %d...", args.semester_id)
        raw = await fetch_courses(session, args.semester_id)
        logger.info("Found %d courses", len(raw))

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump([transform(c) for c in raw], f, ensure_ascii=False, indent=2)
    logger.info("Saved to %s", args.output)


if __name__ == "__main__":
    asyncio.run(main())
