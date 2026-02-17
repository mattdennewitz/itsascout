"""
Terms Discovery Module

This module provides functionality to discover and extract Terms of Service
and Privacy Policy URLs from website HTML content using pydantic-ai.
"""

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
You are an expert Web Scraper and Legal Document Classifier. Your sole purpose is to extract the authoritative "Terms of Service" URL from raw HTML content.

## TASK
Analyze the provided HTML and identify the primary URL for the Terms of Service (ToS). 

### 1. Recognition Patterns
Look for <a> tags where the text or href attribute contains:
- "Terms of Service", "ToS", "Terms of Use", "Terms & Conditions", "User Agreement", "Legal"
- **Exclude:** Privacy Policy, Cookie Policy, GDPR, or Data Processing Agreements.

### 2. Structural Priority
Weight your confidence based on where the link is found:
- **Highest Priority:** Footer `<footer>` or a `<nav>` specifically labeled "Legal" or "Site Map".
- **Secondary:** Header navigation or account registration areas.
- **Low Priority:** Generic mentions within body paragraphs or blog posts.

### 3. URL Construction Rules
- **Absolute URLs:** Return as-is.
- **Relative URLs:** If the provided context includes a base domain [INSERT BASE URL HERE], prepend it to the path (e.g., `/terms` becomes `https://example.com/terms`).
- **Javascript/Anchors:** If a link is a javascript void or a hashtag `#`, attempt to find the source in data-attributes or ignore it.

## NEGATIVE CONSTRAINTS
- DO NOT return a Privacy Policy URL.
- DO NOT invent a URL if it is not explicitly in the HTML.
- DO NOT return relative paths; they must be fully qualified.
"""


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

        # Analyze with pydantic-ai agent
        result = terms_discovery_agent.run_sync(
            f"Analyze this HTML content to find Terms of Service URLs. "
            f"Base URL for relative links: {url}\n\nHTML Content:\n{html_content}"
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
