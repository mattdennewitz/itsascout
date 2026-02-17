"""
Terms Discovery Module

This module provides functionality to discover and extract Terms of Service
and Privacy Policy URLs from website HTML content using pydantic-ai.
"""

from html.parser import HTMLParser
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl
from pydantic_ai import Agent
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


class TermsDiscoveryResult(BaseModel):
    """Structured result containing discovered terms and privacy policy URLs."""

    terms_of_service_url: Optional[HttpUrl] = Field(
        None, description="Complete URL to the Terms of Service page"
    )
    confidence_score: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score from 0.0 to 1.0 indicating reliability of the found URLs",
    )
    notes: Optional[str] = Field(
        None, description="Additional notes about the discovery process or findings"
    )


TERMS_DISCOVERY_PROMPT = """
## ROLE
You are an expert Legal Document Classifier. Your sole purpose is to identify the authoritative "Terms of Service" URL from a list of links extracted from a webpage.

## TASK
You will receive a list of links (href + text) extracted from a webpage. Identify the primary Terms of Service (ToS) URL.

### 1. Recognition Patterns
Look for links where the text or href contains:
- "Terms of Service", "ToS", "Terms of Use", "Terms & Conditions", "User Agreement", "Legal"
- **Exclude:** Privacy Policy, Cookie Policy, GDPR, or Data Processing Agreements.

### 2. URL Construction Rules
- **Absolute URLs:** Return as-is.
- **Relative URLs:** Prepend the base URL provided in the message (e.g., `/terms` becomes `https://example.com/terms`).
- **Javascript/Anchors:** Ignore javascript: or # links.

## NEGATIVE CONSTRAINTS
- DO NOT return a Privacy Policy URL.
- DO NOT invent a URL if it is not in the provided links.
- DO NOT return relative paths; they must be fully qualified.
"""


class _LinkExtractor(HTMLParser):
    """Extract <a> tags with their href and visible text."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            attr_dict = {k.lower(): (v or "") for k, v in attrs}
            href = attr_dict.get("href", "")
            if href:
                self._current_href = href
                self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_text.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_href is not None:
            text = " ".join(t for t in self._current_text if t)
            self.links.append({"href": self._current_href, "text": text})
            self._current_href = None
            self._current_text = []


def _extract_links(html: str) -> str:
    """Parse HTML and return a compact text listing of all <a> links."""
    parser = _LinkExtractor()
    try:
        parser.feed(html)
    except Exception:
        return ""
    lines = []
    for link in parser.links:
        href = link["href"]
        text = link["text"]
        if text:
            lines.append(f"{href} | {text}")
        else:
            lines.append(href)
    return "\n".join(lines)


terms_discovery_agent = Agent(
    "openai:gpt-5-mini",
    output_type=TermsDiscoveryResult,
    system_prompt=TERMS_DISCOVERY_PROMPT,
)


def discover_terms_and_privacy(url: str, publisher=None) -> TermsDiscoveryResult:
    """
    Discover Terms of Service and Privacy Policy URLs from a website.

    This function fetches the HTML content from the provided URL and uses
    the pydantic-ai agent to extract structured information about the
    terms of service and privacy policy URLs.

    Args:
        url: The website URL to analyze

    Returns:
        TermsDiscoveryResult containing the discovered URLs and metadata

    Raises:
        ValueError: If ZYTE_API_KEY environment variable is not set
        requests.RequestException: If the URL cannot be fetched
        Exception: If the agent analysis fails
    """
    from .services import fetch_html_via_proxy

    logger.info(f"Starting terms discovery for URL: {url}")

    try:
        # Fetch HTML content
        html_content = fetch_html_via_proxy(url, publisher=publisher)
        logger.debug(
            f"Successfully fetched HTML content ({len(html_content)} characters)"
        )

        # Extract just the links to avoid sending massive HTML to the LLM
        links_text = _extract_links(html_content)
        logger.debug(
            f"Extracted links ({len(links_text)} characters from {len(html_content)} chars HTML)"
        )

        # Analyze with pydantic-ai agent
        result = terms_discovery_agent.run_sync(
            f"Find the Terms of Service URL from these links extracted from {url}.\n"
            f"Base URL for relative links: {url}\n\nLinks (href | text):\n{links_text}"
        )

        logger.info(f"Terms discovery completed for {url}")
        logger.debug(
            f"Results: ToS={result.output.terms_of_service_url}, Confidence={result.output.confidence_score}"
        )

        return result.output

    except Exception as e:
        logger.error(f"Error during terms discovery for {url}: {e}")
        raise


if __name__ == "__main__":

    def main():
        """Example usage of the terms discovery module."""
        test_url = "https://nytimes.com"
        try:
            result = discover_terms_and_privacy(test_url)
            print(f"Terms of Service: {result.terms_of_service_url}")
            print(f"Confidence Score: {result.confidence_score}")
            print(f"Notes: {result.notes}")
        except Exception as e:
            print(f"Error: {e}")

    main()
