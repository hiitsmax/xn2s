from pydantic import BaseModel, ConfigDict, Field


class IssueTweetRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tweet_id: str
    account_handle: str
    text: str = ""
    quote_text: str = ""
    image_description: str = ""
    url_hint: str = ""


class IssueTweetLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tweet_id: str
    why: str


class IssueRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_id: str
    title: str
    description: str
    tweet_links: list[IssueTweetLink] = Field(default_factory=list)


class IssueMap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[IssueRecord] = Field(default_factory=list)
