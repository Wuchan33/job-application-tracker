import logging
import time

import ollama
from google import genai
from google.genai import errors
from pydantic import BaseModel

from app.config import settings
from app.models import EmailType

logger = logging.getLogger(__name__)
MAX_ROUNDS = 5
REQUEST_DELAY_SECONDS = 4
MAX_EMAIL_CHARS = 4000
OLLAMA_CONTEXT_TOKENS = 8192
RETRYABLE_STATUS_CODES = (429, 503)


class LLMUnavailableError(Exception):
    pass


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
- online_assessment: a task the candidate completes alone, without an interviewer present
  (e.g. Codility or HackerRank tests, questionnaires, case studies, home assignments)
- hr_interview: invitation to a first interview or call with HR or a recruiter
- interview: invitation to any later interview with people from the company
  (e.g. technical, with a manager or the team, final round)
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
    if not settings.gemini_model_list:
        raise LLMUnavailableError("GEMINI_MODELS is not set")

    client = genai.Client(api_key=settings.gemini_api_key)

    for round_number in range(MAX_ROUNDS):
        for model in settings.gemini_model_list:
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
            except errors.APIError as err:
                if err.code not in RETRYABLE_STATUS_CODES:
                    raise
                logger.warning("%s failed (round %d): %s", model, round_number + 1, err)
                continue
            finally:
                time.sleep(REQUEST_DELAY_SECONDS)

            if response.parsed is None:
                raise ValueError(f"Gemini returned no valid result: {response.text!r}")

            return response.parsed

    raise LLMUnavailableError("All Gemini models failed")


PROVIDERS = {
    "ollama": _classify_with_ollama,
    "gemini": _classify_with_gemini,
}


def classify_email(text: str, applications: str = "(none)") -> EmailResult:
    prompt = PROMPT.format(applications=applications, email=text[:MAX_EMAIL_CHARS])
    return PROVIDERS[settings.llm_provider](prompt)
