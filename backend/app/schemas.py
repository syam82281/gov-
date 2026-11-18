
from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


class OpportunityBase(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    organization: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=80)
    state: str = "All India"
    qualification: str = "See official notification"
    age_limit: str = "See official notification"
    application_fee: str = "See official notification"
    last_date: str = "Check official website"

    apply_url: HttpUrl
    notification_url: HttpUrl | None = None

    description: str = ""
    featured: bool = False
    verified: bool = False
    active: bool = True

    @field_validator("notification_url", mode="before")
    @classmethod
    def empty_notification_url_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value


class OpportunityCreate(OpportunityBase):
    pass


class OpportunityOut(OpportunityBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class JobLinkCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    apply_url: HttpUrl
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_application_window(self):
        if self.end_date < self.start_date:
            raise ValueError("End date must be on or after the start date")
        return self


class JobLinkOut(JobLinkCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int

