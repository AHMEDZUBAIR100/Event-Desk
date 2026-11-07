from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str = "ok"
    service: str = "EventDesk API"
    version: str = "0.1.0"


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    database: str
    redis: str
    service: str = "EventDesk API"
