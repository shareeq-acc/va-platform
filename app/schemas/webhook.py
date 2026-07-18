from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class Customer(BaseModel):
    number: Optional[str] = None
    
    class Config:
        extra = "ignore"

class CallMetadata(BaseModel):
    id: str
    customer: Optional[Customer] = None
    
    class Config:
        extra = "ignore"

class FunctionDetails(BaseModel):
    name: str
    arguments: Any

    class Config:
        extra = "ignore"

class ToolCall(BaseModel):
    id: str
    type: str = "function"
    function: FunctionDetails

    class Config:
        extra = "ignore"

class WebhookMessage(BaseModel):
    type: str
    call: CallMetadata
    toolCalls: Optional[List[ToolCall]] = Field(default=None, alias="toolCalls")
    transcript: Optional[str] = None
    endedReason: Optional[str] = Field(default=None, alias="endedReason")

    class Config:
        populate_by_name = True
        extra = "ignore"

class WebhookPayload(BaseModel):
    message: WebhookMessage

    class Config:
        extra = "ignore"
