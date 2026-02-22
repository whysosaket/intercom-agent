from pydantic import BaseModel, Field


class GeneratedResponse(BaseModel):
    text: str
    confidence: float
    reasoning: str = ""


class ContactInfo(BaseModel):
    id: str = ""
    name: str = ""
    email: str = ""


class PostProcessorInput(BaseModel):
    customer_message: str
    generated_response: str
    original_confidence: float
    original_reasoning: str = ""


class PostProcessorOutput(BaseModel):
    refined_text: str
    final_confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
