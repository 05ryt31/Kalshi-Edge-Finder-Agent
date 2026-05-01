from src.clients.tavily import TavilyClient
from src.schemas.market import Market
from src.utils.logger import get_logger

logger = get_logger(__name__)

MAX_CONTENT_LENGTH = 2000


class WebSearchResearcher:
    def __init__(self, client: TavilyClient) -> None:
        self.client = client

    async def research(self, market: Market) -> dict:
        query = self._build_query(market)

        try:
            results = await self.client.search(query)

            articles = [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")[:MAX_CONTENT_LENGTH],
                    "score": r.get("score", 0),
                }
                for r in results.get("results", [])
            ]

            answer = results.get("answer", "")

            return {
                "category": market.category,
                "data_sources": ["Tavily Web Search"],
                "collected_data": {
                    "query": query,
                    "answer": answer,
                    "articles": articles,
                },
                "summary": answer if answer else self._summarize_articles(articles),
            }
        except Exception as e:
            logger.error("web_search_error", query=query, error=str(e))
            return self._empty_report(f"Web search failed: {e}")

    def _build_query(self, market: Market) -> str:
        title = market.title
        category = market.category

        if category == "sports":
            return f"{title} latest odds predictions news"

        return f"{title} latest news analysis"

    def _summarize_articles(self, articles: list[dict]) -> str:
        if not articles:
            return "No relevant articles found."
        titles = [a["title"] for a in articles[:3] if a["title"]]
        return f"Found {len(articles)} articles: {'; '.join(titles)}"

    def _empty_report(self, reason: str) -> dict:
        return {
            "category": "sports",
            "data_sources": [],
            "collected_data": {},
            "summary": reason,
        }
