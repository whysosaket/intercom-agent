from enum import Enum

from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    """Whether the customer question is technical or non-technical."""

    TECHNICAL = "technical"
    NON_TECHNICAL = "non_technical"


class RoutingDecision(str, Enum):
    """Pre-check routing decision for the pipeline."""

    ESCALATE = "escalate"  # Skip answer generation, go straight to human
    KB_ONLY = "kb_only"  # Answer from FAQ/memory only, no doc agent
    FULL_PIPELINE = "full_pipeline"  # Full answer generation + doc agent fallback


class PreCheckResult(BaseModel):
    """Output of the pre-check classification agent."""

    question_type: QuestionType = QuestionType.TECHNICAL
    routing_decision: RoutingDecision = RoutingDecision.FULL_PIPELINE
    requires_human_intervention: bool = False
    is_followup: bool = False
    followup_context: str = ""
    answerable_from_context: bool = True
    reasoning: str = ""
    confidence_hint: float = 0.0


class GeneratedResponse(BaseModel):
    text: str
    confidence: float
    reasoning: str = ""
    requires_human_intervention: bool = False
    is_followup: bool = False
    followup_context: str = ""
    answerable_from_context: bool = True


class ContactInfo(BaseModel):
    id: str = ""
    name: str = ""
    email: str = ""


class PostProcessorInput(BaseModel):
    customer_message: str
    generated_response: str
    original_confidence: float
    original_reasoning: str = ""
    conversation_history: list[dict] = []


class PostProcessorOutput(BaseModel):
    refined_text: str
    final_confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    response_addresses_question: bool = True
