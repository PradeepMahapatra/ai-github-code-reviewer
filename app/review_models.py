from pydantic import BaseModel, ConfigDict, Field


class ChangedFileReviewInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    filename: str = Field(min_length=1)
    status: str = Field(min_length=1)
    additions: int = Field(ge=0)
    deletions: int = Field(ge=0)
    changes: int = Field(ge=0)
    patch: str | None = None


class PullRequestReviewInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    repository_owner: str = Field(min_length=1)
    repository_name: str = Field(min_length=1)
    pull_request_number: int = Field(gt=0)
    pull_request_title: str = Field(min_length=1)
    action: str = Field(min_length=1)
    head_commit_sha: str = Field(min_length=1)
    changed_files: list[ChangedFileReviewInput]
