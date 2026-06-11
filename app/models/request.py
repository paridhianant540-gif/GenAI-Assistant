from pydantic import BaseModel, Field, field_validator

class ChatRequest(BaseModel):
    sessionId: str = Field(..., description="Unique session identifier for managing chat history.")
    message: str = Field(..., description="The user's query message.")
    
    @field_validator("sessionId")
    @classmethod
    def validate_session(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Session ID cannot be blank.")
        return v

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message field is required")
        return v

class UserAuthRequest(BaseModel):
    username: str = Field(..., min_length=3, description="Username (minimum 3 characters)")
    password: str = Field(..., min_length=6, description="Password (minimum 6 characters)")
    
    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Username cannot be blank")
        return v
        
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v or len(v) < 6:
            raise ValueError("Password must be at least 6 characters long")
        return v
