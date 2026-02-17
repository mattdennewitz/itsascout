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
# ROLE
You are a Senior Legal Compliance Auditor specializing in Digital Rights and Automated Access. Your task is to map a website's Terms of Service and Privacy Policy into a high-fidelity Permission Matrix.

# OBJECTIVE
Deconstruct the provided text to identify the legal standing of 8 specific activities. You must remain strictly tethered to the provided text. If the text is silent on a topic, mark it as "Unspecified/Ambiguous."

# THE LEGAL ACTIVITY MATRIX
Evaluate the following 8 categories using ONLY these labels: [Explicitly Permitted | Explicitly Prohibited | Conditional/Ambiguous].

1. Scraping & Crawling (Automated access, bots, spiders, indexing)
2. AI & Machine Learning (Training, fine-tuning, RAG, model inputs)
3. Manual Content Usage (Reading, individual printing, manual quoting)
4. Archiving & Caching (Wayback Machine, local caching, dataset storage)
5. Text & Data Mining (TDM) (Pattern recognition, bulk data analysis)
6. API & RSS Usage (Official endpoints vs. unauthorized scraping)
7. Redistribution & Reproduction (Mirroring, commercial reselling, syndication)
8. User-Generated Content (UGC) (Rights granted to the platform vs. user retained rights)

# ANALYSIS PROTOCOL
- **Strict Construction:** Interpret silence as "Conditional/Ambiguous." Do not assume "Fair Use" applies unless the document explicitly mentions statutory exceptions (e.g., "Except as permitted by Section 107...").
- **Commercial vs. Personal:** Always specify if a permission changes based on the user's commercial status.
- **Territorial Layering:** Specifically extract mentions of GDPR (EU), CCPA (California), or the EU AI Act/Copyright Directive.
- **The "No-Derivative" Rule:** If the text forbids "derivative works," this must be flagged under AI Training and Redistribution.

# REQUIRED RESPONSE STRUCTURE
For each of the 8 activities, provide:

### [Activity Name]
- **Status:** [Label]
- **Territorial Scope:** (e.g., Global, EU-only, or "Not Specified")
- **Verbatim Evidence:** "Quote the exact sentence from the document here."
- **Compliance Note:** A concise explanation of the restriction. Highlight if a "Written Consent" requirement exists.

# FINAL RISK ASSESSMENT
- **Arbitration/Jurisdiction:** Identify the governing law and if class-action waivers are present.
- **Overall Confidence Score:** (0.0 - 1.0) based on text clarity.
- **Aggregator Summary:** A 2-sentence "Bottom Line" for a developer or researcher."""


terms_evaluation_agent = Agent(
    "openai:gpt-5-mini",
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
