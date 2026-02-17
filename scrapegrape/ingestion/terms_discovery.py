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
You are a specialized web content analyzer focused on discovering Terms of Service URLs from HTML content.

Your task is to carefully analyze the provided HTML content and identify URLs that lead to:
1. Terms of Service (also known as Terms of Use, Terms and Conditions, Legal Terms, User Agreement. NOT a privacy policy.)

ANALYSIS GUIDELINES:
- Look for anchor tags (<a>) with href attributes containing relevant URLs
- Search for common patterns in link text, such as:
  - Terms: "terms", "terms of service", "terms of use", "terms and conditions", "legal", "user agreement", "tos", "terms & conditions"
- Check footer sections, navigation menus, and legal sections where these links are commonly placed
- Prioritize links that appear to be official/primary rather than secondary references
- Look for both absolute URLs (starting with http/https) and relative URLs
- If you find relative URLs, construct complete URLs by considering the base domain context

URL VALIDATION:
- Ensure URLs are properly formatted and accessible
- For relative URLs, assume they should be prefixed with the base domain
- Verify that the URLs actually point to terms content, not just contain keywords
- Look for patterns that indicate legitimate legal pages vs. generic mentions

CONFIDENCE SCORING:
- High confidence (0.8-1.0): Clear, unambiguous links in typical locations (footer, legal section)
- Medium confidence (0.5-0.7): Links found but in less typical locations or with ambiguous text
- Low confidence (0.0-0.4): Weak matches or URLs that may not be the primary legal documents

RESPONSE REQUIREMENTS:
- Return complete, valid URLs (not fragments or relative paths without domain)
- If no relevant URLs are found, return null for those fields
- Provide a confidence score based on the clarity and reliability of the found URLs
- Include notes explaining your findings, especially if there are multiple candidates or ambiguities

Be thorough but precise in your analysis. Focus on finding the most authoritative and official terms and privacy policy pages.
"""


terms_discovery_agent = Agent(
    "openai:gpt-4.1-nano",
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
