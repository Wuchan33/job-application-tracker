import time
from enum import StrEnum

from google import genai
from google.genai import errors
from pydantic import BaseModel

from app.config import settings

client = genai.Client(api_key=settings.gemini_api_key)
MODELS = settings.gemini_model_list
MAX_ROUNDS = 5
RETRY_DELAY_SECONDS = 15


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


def classify_email(text: str, applications: str = "(none)") -> EmailResult:
    for round_ in range(MAX_ROUNDS):
        for model in MODELS:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=PROMPT.format(email=text[:4000], applications=applications),
                    config={
                        "automatic_function_calling": {"disable": True},
                        "response_mime_type": "application/json",
                        "response_schema": EmailResult,
                    },
                )
            except errors.APIError as e:
                if e.code not in (429, 503):
                    raise
                last_error = e
                continue

            if response.parsed is None:
                raise ValueError(f"Gemini returned no valid result: {response.text!r}")
            return response.parsed

        if round_ < MAX_ROUNDS - 1:
            time.sleep(RETRY_DELAY_SECONDS)

    raise last_error
