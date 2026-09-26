from app.review_models import PullRequestReviewInput
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_MAX_FILES = 50
DEFAULT_MAX_TOTAL_DIFF_SIZE = 100_000


class ProcessedDiffFile(BaseModel):
    """A changed file prepared for a bounded review input."""

    model_config = ConfigDict(frozen=True)

    filename: str = Field(min_length=1)
    status: str = Field(min_length=1)
    additions: int = Field(ge=0)
    deletions: int = Field(ge=0)
    changes: int = Field(ge=0)
    patch: str | None
    patch_truncated: bool = False


class ProcessedPullRequestDiff(BaseModel):
    """Bounded Pull Request data for a future AI reviewer."""

    model_config = ConfigDict(frozen=True)

    repository_owner: str = Field(min_length=1)
    repository_name: str = Field(min_length=1)
    pull_request_number: int = Field(gt=0)
    pull_request_title: str = Field(min_length=1)
    head_commit_sha: str = Field(min_length=1)
    changed_files: list[ProcessedDiffFile]
    max_files: int
    max_total_diff_size: int
    total_diff_size: int
    files_truncated: bool
    diff_truncated: bool
    is_empty: bool


class DiffProcessor:
    def __init__(
        self,
        max_files: int = DEFAULT_MAX_FILES,
        max_total_diff_size: int = DEFAULT_MAX_TOTAL_DIFF_SIZE,
    ) -> None:
        if max_files < 1:
            raise ValueError("max_files must be positive")
        if max_total_diff_size < 1:
            raise ValueError("max_total_diff_size must be positive")
        self.max_files = max_files
        self.max_total_diff_size = max_total_diff_size

    def process(self, review_input: PullRequestReviewInput) -> ProcessedPullRequestDiff:
        source_files = review_input.changed_files
        selected_files = source_files[: self.max_files]
        files_truncated = len(source_files) > self.max_files
        total_diff_size = 0
        diff_truncated = False
        processed_files: list[ProcessedDiffFile] = []

        for source_file in selected_files:
            patch = source_file.patch
            patch_truncated = False
            if patch is not None:
                remaining_size = self.max_total_diff_size - total_diff_size
                bounded_patch = patch[:remaining_size]
                patch_truncated = len(bounded_patch) < len(patch)
                diff_truncated = diff_truncated or patch_truncated
                patch = bounded_patch
                total_diff_size += len(patch)

            processed_files.append(
                ProcessedDiffFile(
                    filename=source_file.filename,
                    status=source_file.status,
                    additions=source_file.additions,
                    deletions=source_file.deletions,
                    changes=source_file.changes,
                    patch=patch,
                    patch_truncated=patch_truncated,
                )
            )

        return ProcessedPullRequestDiff(
            repository_owner=review_input.repository_owner,
            repository_name=review_input.repository_name,
            pull_request_number=review_input.pull_request_number,
            pull_request_title=review_input.pull_request_title,
            head_commit_sha=review_input.head_commit_sha,
            changed_files=processed_files,
            max_files=self.max_files,
            max_total_diff_size=self.max_total_diff_size,
            total_diff_size=total_diff_size,
            files_truncated=files_truncated,
            diff_truncated=diff_truncated,
            is_empty=not processed_files,
        )


def process_pull_request_diff(
    review_input: PullRequestReviewInput,
    max_files: int = DEFAULT_MAX_FILES,
    max_total_diff_size: int = DEFAULT_MAX_TOTAL_DIFF_SIZE,
) -> ProcessedPullRequestDiff:
    return DiffProcessor(max_files, max_total_diff_size).process(review_input)
