"""
Confluence Reader - Fetches and parses PRD documents from Confluence.
"""

import re
from dataclasses import dataclass
from html.parser import HTMLParser

import httpx


@dataclass
class ConfluencePage:
    """Represents a parsed Confluence page."""
    title: str
    content: str  # Clean text/markdown
    page_id: str
    space_key: str
    labels: list[str]
    last_modified: str


class HTMLToMarkdownParser(HTMLParser):
    """Simple HTML to Markdown converter for Confluence storage format."""

    def __init__(self):
        super().__init__()
        self.result = []
        self.current_tag = None
        self.list_depth = 0

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        attrs_dict = dict(attrs)
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            self.result.append("\n" + "#" * level + " ")
        elif tag == "li":
            self.result.append("\n" + "  " * self.list_depth + "- ")
        elif tag in ("ul", "ol"):
            self.list_depth += 1
        elif tag == "br":
            self.result.append("\n")
        elif tag == "p":
            self.result.append("\n\n")
        elif tag == "strong" or tag == "b":
            self.result.append("**")
        elif tag == "em" or tag == "i":
            self.result.append("*")
        elif tag == "code":
            self.result.append("`")
        elif tag == "a":
            self.result.append("[")
        elif tag == "table":
            self.result.append("\n\n")

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.result.append("\n")
        elif tag in ("ul", "ol"):
            self.list_depth = max(0, self.list_depth - 1)
        elif tag == "strong" or tag == "b":
            self.result.append("**")
        elif tag == "em" or tag == "i":
            self.result.append("*")
        elif tag == "code":
            self.result.append("`")
        elif tag == "a":
            self.result.append("]")
        self.current_tag = None

    def handle_data(self, data):
        self.result.append(data)

    def get_markdown(self) -> str:
        text = "".join(self.result)
        # Clean up excessive newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


class ConfluenceReader:
    """
    Reads and parses documents from Confluence using the REST API.

    Supports:
    - Fetching by page URL
    - Fetching by page ID
    - Fetching all pages in a space
    - Converting Confluence storage format to Markdown
    """

    def __init__(self, url: str, token: str, username: str = ""):
        """
        Initialize Confluence reader.

        Args:
            url: Confluence base URL (e.g., https://your-org.atlassian.net)
            token: API token for authentication
            username: Username for basic auth (cloud) or empty for PAT (server)
        """
        self.base_url = url.rstrip("/")
        self.token = token
        self.username = username

        # Set up HTTP client with auth
        if username:
            # Atlassian Cloud: Basic auth with email + API token
            auth = httpx.BasicAuth(username, token)
        else:
            # Server/DC: Bearer token
            auth = None

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=auth,
            headers={
                "Accept": "application/json",
                **({"Authorization": f"Bearer {token}"} if not username else {}),
            },
            timeout=30.0,
        )

    async def fetch_page(self, url_or_id: str) -> str:
        """
        Fetch a Confluence page and return its content as Markdown.

        Args:
            url_or_id: Either a full Confluence page URL or a page ID

        Returns:
            Page content as Markdown string
        """
        page_id = self._extract_page_id(url_or_id)
        page = await self._get_page(page_id)
        return page.content

    async def fetch_page_structured(self, url_or_id: str) -> ConfluencePage:
        """Fetch a page with full metadata."""
        page_id = self._extract_page_id(url_or_id)
        return await self._get_page(page_id)

    async def fetch_space_pages(
        self, space_key: str, label: str | None = None, limit: int = 50
    ) -> list[ConfluencePage]:
        """
        Fetch all pages in a space, optionally filtered by label.

        Args:
            space_key: Confluence space key
            label: Optional label to filter pages
            limit: Maximum number of pages to fetch

        Returns:
            List of ConfluencePage objects
        """
        cql = f'space="{space_key}" AND type="page"'
        if label:
            cql += f' AND label="{label}"'

        response = await self.client.get(
            "/wiki/rest/api/content/search",
            params={
                "cql": cql,
                "limit": limit,
                "expand": "body.storage,metadata.labels,version",
            },
        )
        response.raise_for_status()
        data = response.json()

        pages = []
        for result in data.get("results", []):
            page = self._parse_page_response(result)
            pages.append(page)

        return pages

    async def _get_page(self, page_id: str) -> ConfluencePage:
        """Fetch a single page by ID."""
        response = await self.client.get(
            f"/wiki/rest/api/content/{page_id}",
            params={
                "expand": "body.storage,metadata.labels,version,space",
            },
        )
        response.raise_for_status()
        return self._parse_page_response(response.json())

    def _parse_page_response(self, data: dict) -> ConfluencePage:
        """Parse Confluence API response into ConfluencePage."""
        html_content = data.get("body", {}).get("storage", {}).get("value", "")
        markdown_content = self._html_to_markdown(html_content)

        labels = [
            label["name"]
            for label in data.get("metadata", {})
            .get("labels", {})
            .get("results", [])
        ]

        return ConfluencePage(
            title=data.get("title", ""),
            content=markdown_content,
            page_id=str(data.get("id", "")),
            space_key=data.get("space", {}).get("key", ""),
            labels=labels,
            last_modified=data.get("version", {}).get("when", ""),
        )

    def _html_to_markdown(self, html: str) -> str:
        """Convert Confluence storage format HTML to Markdown."""
        parser = HTMLToMarkdownParser()
        parser.feed(html)
        return parser.get_markdown()

    def _extract_page_id(self, url_or_id: str) -> str:
        """Extract page ID from a URL or return as-is if already an ID."""
        if url_or_id.isdigit():
            return url_or_id

        # Try to extract from URL patterns
        # Pattern 1: /pages/123456/Page+Title
        match = re.search(r"/pages/(\d+)", url_or_id)
        if match:
            return match.group(1)

        # Pattern 2: /wiki/spaces/SPACE/pages/123456
        match = re.search(r"/pages/(\d+)", url_or_id)
        if match:
            return match.group(1)

        # Pattern 3: pageId=123456
        match = re.search(r"pageId=(\d+)", url_or_id)
        if match:
            return match.group(1)

        raise ValueError(
            f"Could not extract page ID from: {url_or_id}. "
            "Please provide a valid Confluence URL or page ID."
        )

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
