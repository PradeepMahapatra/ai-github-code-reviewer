from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PullRequestEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    repository_owner: str = Field(min_length=1)
    repository_name: str = Field(min_length=1)
    pull_request_number: int = Field(gt=0)
    pull_request_title: str = Field(min_length=1)
    action: str = Field(min_length=1)
    head_commit_sha: str = Field(min_length=1)


def parse_pull_request_event(payload: Mapping[str, Any]) -> PullRequestEvent:
    repository = payload.get("repository")
    pull_request = payload.get("pull_request")
    if not isinstance(repository, Mapping) or not isinstance(pull_request, Mapping):
        raise ValueError("Missing required pull request payload fields")

    owner = repository.get("owner")
    if not isinstance(owner, Mapping):
        raise ValueError("Missing required repository owner")

    try:
        return PullRequestEvent(
            repository_owner=owner["login"],
            repository_name=repository["name"],
            pull_request_number=payload["number"],
            pull_request_title=pull_request["title"],
            action=payload["action"],
            head_commit_sha=pull_request["head"]["sha"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Missing required pull request payload fields") from exc
