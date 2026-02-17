"""
Terms Evaluation Module

This module provides functionality to evaluate Terms of Service and Privacy Policy
content for scraping and data extraction permissions using pydantic-ai.
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from loguru import logger
from dotenv import load_dotenv
from enum import Enum

load_dotenv()


class PermissionStatus(str, Enum):
    """Enum for permission status values."""

    EXPLICITLY_PERMITTED = "explicitly_permitted"
    EXPLICITLY_PROHIBITED = "explicitly_prohibited"
    CONDITIONAL_AMBIGUOUS = "conditional_ambiguous"


class ActivityPermission(BaseModel):
    """Individual activity permission entry."""

    activity: str = Field(
        ...,
        description="Description of the specific activity (e.g., 'Manual reading for personal use', 'Automated web scraping')",
    )
    permission: PermissionStatus = Field(
        ...,
        description="Permission status: explicitly_permitted, explicitly_prohibited, or conditional_ambiguous",
    )
    notes: str = Field(
        ...,
        description="Detailed notes explaining the permission, including quoted text from the document and context",
    )


class TermsEvaluationResult(BaseModel):
    """Structured result containing evaluated permissions for various activities."""

    permissions: List[ActivityPermission] = Field(
        ..., description="List of activity permissions found in the terms document"
    )
    territorial_exceptions: Optional[str] = Field(
        None,
        description="Any territorial exceptions mentioned (e.g., EU copyright directives, U.S. law)",
    )
    arbitration_clauses: Optional[str] = Field(
        None,
        description="Information about arbitration, opt-out, or liability disclaimers that affect compliance risk",
    )
    document_type: Optional[str] = Field(
        None,
        description="Type of document analyzed (e.g., 'Terms of Service', 'Privacy Policy', 'Combined Terms and Privacy')",
    )
    confidence_score: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score from 0.0 to 1.0 indicating reliability of the analysis",
    )


TERMS_EVALUATION_PROMPT = """
You are a legal-policy analyst AI designed to review website Terms of Service (ToS) and Privacy Policies to determine what user or automated behaviors are permitted, prohibited, or restricted with conditions. Given a full ToS or Privacy Policy document, output a clear and comprehensive Activity Permission Table.

Instructions:
Identify explicit clauses that allow, forbid, or restrict:

1. Scraping or crawling (automated access, bots, spiders)
2. AI and machine learning usage (training, fine-tuning, retrieval-augmented generation)
3. Manual content usage (reading, printing, quoting)
4. Caching, archiving, and dataset creation
5. Text and Data Mining (TDM)
6. API and RSS feed usage
7. Content redistribution or reproduction
8. Use of user-generated content (UGC)

You must evaluate for all 8 of these rules individually.
Use their phrase exactly in your structured response.
Do not improvise or deviate.

Include any territorial exceptions (e.g., EU copyright directives, U.S. law).

For each activity, determine if it is:
- "explicitly_permitted": Clear permission is granted
- "explicitly_prohibited": Clear prohibition is stated
- "conditional_ambiguous": Conditional permission, unclear language, or ambiguous terms

When ambiguous, reason through the most conservative interpretation unless there's a fair use doctrine or statutory carve-out explicitly mentioned.

Additional Guidance:
- Quote directly or paraphrase key language from the document in the Notes field
- Distinguish between personal use, commercial use, and automated use
- Include specific activities even if they're variations of broader categories
- For each permission, provide detailed notes explaining the reasoning and citing relevant text
- Look for any territorial exceptions or jurisdiction-specific rules
- Note any arbitration clauses, opt-out provisions, or liability disclaimers that affect compliance risk

ANALYSIS REQUIREMENTS:
- Be thorough and identify all relevant activities mentioned in the document
- Provide specific, actionable activity descriptions
- Include verbatim quotes or close paraphrases in the notes
- Consider both explicit permissions and implicit restrictions
- Analyze the document holistically to understand the overall policy stance
- Assign a confidence score based on the clarity and completeness of the terms

Focus on providing practical, legally-informed guidance that helps users understand what they can and cannot do with the website's content.
"""


terms_evaluation_agent = Agent(
    "openai:gpt-4.1-nano",
    output_type=TermsEvaluationResult,
    system_prompt=TERMS_EVALUATION_PROMPT,
)


def evaluate_terms_and_conditions(url: str, publisher=None) -> TermsEvaluationResult:
    """
    Evaluate Terms of Service and Privacy Policy content for activity permissions.

    This function fetches the HTML content from the provided URL and uses
    the pydantic-ai agent to analyze the terms for various activity permissions.

    Args:
        url: The website URL containing terms/privacy policy to analyze

    Returns:
        TermsEvaluationResult containing the evaluated permissions and metadata

    Raises:
        ValueError: If ZYTE_API_KEY environment variable is not set
        requests.RequestException: If the URL cannot be fetched
        Exception: If the agent analysis fails
    """
    from .services import fetch_html_via_proxy

    logger.info(f"Starting terms evaluation for URL: {url}")

    try:
        # Fetch HTML content
        html_content = fetch_html_via_proxy(url, publisher=publisher)
        logger.debug(
            f"Successfully fetched HTML content ({len(html_content)} characters)"
        )

        # Analyze with pydantic-ai agent
        result = terms_evaluation_agent.run_sync(
            f"Analyze this HTML content from {url} to evaluate activity permissions. "
            f"Focus on the Terms of Service and Privacy Policy sections to determine what activities are permitted, prohibited, or conditional.\n\n"
            f"HTML Content:\n{html_content}"
        )

        logger.info(f"Terms evaluation completed for {url}")
        logger.debug(
            f"Found {len(result.output.permissions)} activity permissions with confidence {result.output.confidence_score}"
        )

        return result.output

    except Exception as e:
        logger.error(f"Error during terms evaluation for {url}: {e}")
        raise
