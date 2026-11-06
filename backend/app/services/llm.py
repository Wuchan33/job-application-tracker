import logging
import time
from enum import StrEnum

import ollama
from google import genai
from google.genai import errors
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)
MODELS = settings.gemini_model_list
MAX_ROUNDS = 5
RETRY_DELAY_SECONDS = 15
MAX_EMAIL_CHARS = 4000
OLLAMA_CONTEXT_TOKENS = 8192
RETRYABLE_STATUS_CODES = (429, 503)


class LLMUnavailableError(Exception):
    pass


class EmailType(StrEnum):
    APPLIED = "applied"
    ONLINE_TEST = "online_test"
    HR_INTERVIEW = "hr_interview"
    TECHNICAL_INTERVIEW = "technical_interview"
    TAKE_HOME = "take_home"
    FINAL_INTERVIEW = "final_interview"
    OFFER = "offer"
    REJECTION = "rejection"
    OTHER = "other"


class EmailResult(BaseModel):
    is_recruitment: bool
    company: str | None
    position: str | None
    type: EmailType
    application_id: int | None


PROMPT = """You analyze emails related to a job search.
Decide whether the email is about a specific job application, extract the company
and position if present, and classify the email type:

- applied: the candidate submitted an application, or the company confirms receiving it
- online_test: invitation to a timed online test (e.g. Codility, HackerRank, TestGorilla)
- hr_interview: invitation to an interview with HR or a recruiter
- technical_interview: invitation to a technical interview
- take_home: a home assignment to complete over several days
- final_interview: final round, e.g. with a manager or the team
- offer: a job offer
- rejection: the company ends the process for this candidate
- other: anything else, including newsletters and job alerts and unrelated emails

Company is the employer, not a job portal or recruitment agency (e.g. not LinkedIn, Pracuj.pl).
Return the company's short common name without legal form (e.g. "Allegro", not "Allegro sp. z o.o.").

Open applications:
{applications}

If the email clearly refers to one of the open applications above, return its id in application_id.
Use reference numbers, company and position to match. If it's a new application or you're unsure, return null.

Email:
{email}"""  # noqa: E501


def _classify_with_ollama(prompt: str) -> EmailResult:
    try:
        response = ollama.chat(
            model=settings.ollama_model,
            messages=[{"role": "user", "content": prompt}],
            format=EmailResult.model_json_schema(),
            options={"temperature": 0, "num_ctx": OLLAMA_CONTEXT_TOKENS},
        )
    except (ConnectionError, ollama.ResponseError) as e:
        raise LLMUnavailableError(f"Ollama unavailable: {e}") from e
    return EmailResult.model_validate_json(response.message.content)


def _classify_with_gemini(prompt: str) -> EmailResult:
    if not settings.gemini_api_key:
        raise LLMUnavailableError("GEMINI_API_KEY is not set")
    if not MODELS:
        raise LLMUnavailableError("GEMINI_MODELS is not set")
    client = genai.Client(api_key=settings.gemini_api_key)

    for round_number in range(MAX_ROUNDS):
        for model in MODELS:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": EmailResult,
                        "automatic_function_calling": {"disable": True},
                    },
                )
            except errors.APIError as e:
                if e.code not in RETRYABLE_STATUS_CODES:
                    raise
                logger.warning("%s failed (round %d): %s", model, round_number + 1, e)
                continue

            if response.parsed is None:
                raise ValueError(f"Gemini returned no valid result: {response.text!r}")
            return response.parsed

        if round_number < MAX_ROUNDS - 1:
            time.sleep(RETRY_DELAY_SECONDS)

    raise LLMUnavailableError("All Gemini models failed")


def classify_email(text: str, applications: str = "(none)") -> EmailResult:
    prompt = PROMPT.format(applications=applications, email=text[:MAX_EMAIL_CHARS])
    if settings.llm_provider == "gemini":
        return _classify_with_gemini(prompt)
    return _classify_with_ollama(prompt)
