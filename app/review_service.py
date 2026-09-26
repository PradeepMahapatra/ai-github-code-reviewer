from app.github_client import GitHubApiClient
from app.review_models import ChangedFileReviewInput, PullRequestReviewInput
from app.webhook_events import PullRequestEvent


def retrieve_pull_request_review_input(
    event: PullRequestEvent,
    client: GitHubApiClient,
) -> PullRequestReviewInput:
    pull_request = client.get_pull_request(
        event.repository_owner,
        event.repository_name,
        event.pull_request_number,
    )
    changed_files = client.get_changed_files(
        event.repository_owner,
        event.repository_name,
        event.pull_request_number,
    )

    return PullRequestReviewInput(
        repository_owner=event.repository_owner,
        repository_name=event.repository_name,
        pull_request_number=pull_request.number,
        pull_request_title=pull_request.title,
        action=event.action,
        head_commit_sha=pull_request.head_sha,
        changed_files=[
            ChangedFileReviewInput(
                filename=changed_file.filename,
                status=changed_file.status,
                additions=changed_file.additions,
                deletions=changed_file.deletions,
                changes=changed_file.changes,
                patch=changed_file.patch,
            )
            for changed_file in changed_files
        ],
    )
