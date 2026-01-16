"""News fetcher for MLB and MLB Trade Rumors."""
import asyncio
import aiohttp
from typing import List, Dict
from datetime import datetime
import logging
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


class NewsFetcher:
    """Fetches MLB news from various sources."""

    def __init__(self):
        self.session: aiohttp.ClientSession = None
        self.stories: List[Dict] = []
        self.last_update: datetime = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def fetch_all_news(self) -> List[Dict]:
        """Fetch news from all sources."""
        stories = []

        try:
            # Fetch from MLB.com RSS (official MLB news)
            mlb_stories = await self._fetch_mlb_news()
            stories.extend(mlb_stories[:3])  # Top 3 stories

            # Fetch from MLB Trade Rumors RSS
            trade_stories = await self._fetch_trade_rumors()
            stories.extend(trade_stories[:5])  # Top 5 stories

            self.stories = stories
            self.last_update = datetime.now()
            logger.info(f"Fetched {len(stories)} news stories")

        except Exception as e:
            logger.error(f"Error fetching news: {e}", exc_info=True)

        return stories

    async def _fetch_mlb_news(self) -> List[Dict]:
        """Fetch news from MLB.com RSS feed."""
        url = "https://www.mlb.com/feeds/news/rss.xml"
        stories = []

        try:
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    content = await response.text()
                    root = ET.fromstring(content)

                    # Parse RSS feed
                    for item in root.findall('.//item')[:5]:
                        title = item.find('title')
                        link = item.find('link')
                        pub_date = item.find('pubDate')

                        if title is not None:
                            stories.append({
                                'title': title.text,
                                'link': link.text if link is not None else '',
                                'pub_date': pub_date.text if pub_date is not None else '',
                                'source': 'MLB.com'
                            })

        except Exception as e:
            logger.error(f"Error fetching MLB.com news: {e}")

        return stories

    async def _fetch_trade_rumors(self) -> List[Dict]:
        """Fetch news from MLB Trade Rumors RSS feed."""
        url = "https://www.mlbtraderumors.com/feed"
        stories = []

        try:
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    content = await response.text()
                    root = ET.fromstring(content)

                    # Parse RSS feed (WordPress format)
                    for item in root.findall('.//{http://www.w3.org/2005/Atom}entry')[:5]:
                        title = item.find('{http://www.w3.org/2005/Atom}title')
                        link = item.find('{http://www.w3.org/2005/Atom}link')
                        updated = item.find('{http://www.w3.org/2005/Atom}updated')

                        if title is not None:
                            stories.append({
                                'title': title.text,
                                'link': link.get('href') if link is not None else '',
                                'pub_date': updated.text if updated is not None else '',
                                'source': 'MLB Trade Rumors'
                            })

                    # If Atom feed doesn't work, try RSS format
                    if not stories:
                        for item in root.findall('.//item')[:5]:
                            title = item.find('title')
                            link = item.find('link')
                            pub_date = item.find('pubDate')

                            if title is not None:
                                stories.append({
                                    'title': title.text,
                                    'link': link.text if link is not None else '',
                                    'pub_date': pub_date.text if pub_date is not None else '',
                                    'source': 'MLB Trade Rumors'
                                })

        except Exception as e:
            logger.error(f"Error fetching MLB Trade Rumors: {e}")

        return stories

    def get_stories(self) -> List[Dict]:
        """Get cached stories."""
        return self.stories
