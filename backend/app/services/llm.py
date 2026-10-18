import os
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env")

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = os.environ["GEMINI_MODEL"]


class EmailType(str, Enum):
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

Email:
{email}"""


def classify_email(text: str) -> EmailResult:
    response = client.models.generate_content(
        model=MODEL,
        contents=PROMPT.format(email=text[:4000]),
        config={
            "response_mime_type": "application/json",
            "response_schema": EmailResult,
        },
    )

    if response.parsed is None:
        raise ValueError(f"Gemini returned no valid result: {response.text!r}")

    return response.parsed
