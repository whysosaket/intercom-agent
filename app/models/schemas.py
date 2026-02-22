from pydantic import BaseModel, Field


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
