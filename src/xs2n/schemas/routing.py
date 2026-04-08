from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


RouteCategory = Literal["plain", "ambiguous", "images", "external"]


class RoutingTweetRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tweet_id: str
    text: str = ""
    quote_text: str = ""
    image_description: str = ""
    url_hint: str = ""


class PackedRoutingBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str
    short_to_tweet_id: dict[str, str] = Field(default_factory=dict)


class RoutingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plain_ids: list[str] = Field(default_factory=list)
    ambiguous_ids: list[str] = Field(default_factory=list)
    image_ids: list[str] = Field(default_factory=list)
    external_ids: list[str] = Field(default_factory=list)
