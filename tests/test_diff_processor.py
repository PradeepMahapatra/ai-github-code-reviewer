from app.diff_processor import process_pull_request_diff
from app.review_models import ChangedFileReviewInput, PullRequestReviewInput


def make_review_input(
    changed_files: list[ChangedFileReviewInput],
) -> PullRequestReviewInput:
    return PullRequestReviewInput(
        repository_owner="octo-owner",
        repository_name="review-target",
        pull_request_number=42,
        pull_request_title="Improve reviewer output",
        action="opened",
        head_commit_sha="abc123",
        changed_files=changed_files,
    )


def make_file(
    filename: str,
    status: str = "modified",
    additions: int = 2,
    deletions: int = 1,
    changes: int = 3,
    patch: str | None = "@@ -1 +1 @@",
) -> ChangedFileReviewInput:
    return ChangedFileReviewInput(
        filename=filename,
        status=status,
        additions=additions,
        deletions=deletions,
        changes=changes,
        patch=patch,
    )


def test_normal_pull_request_with_one_changed_file() -> None:
    result = process_pull_request_diff(make_review_input([make_file("app/main.py")]))

    assert result.is_empty is False
    assert len(result.changed_files) == 1
    assert result.changed_files[0].filename == "app/main.py"


def test_multiple_changed_files_are_preserved_in_order() -> None:
    files = [make_file("app/main.py"), make_file("tests/test_main.py")]

    result = process_pull_request_diff(make_review_input(files))

    assert [file.filename for file in result.changed_files] == [
        "app/main.py",
        "tests/test_main.py",
    ]


def test_file_statuses_are_preserved() -> None:
    files = [
        make_file("modified.py", status="modified"),
        make_file("added.py", status="added"),
        make_file("deleted.py", status="removed"),
    ]

    result = process_pull_request_diff(make_review_input(files))

    assert [file.status for file in result.changed_files] == [
        "modified",
        "added",
        "removed",
    ]


def test_file_without_patch_is_preserved_without_inventing_code() -> None:
    result = process_pull_request_diff(make_review_input([make_file("binary.png", patch=None)]))

    assert result.changed_files[0].patch is None
    assert result.changed_files[0].patch_truncated is False
    assert result.total_diff_size == 0


def test_empty_diff_is_detected() -> None:
    result = process_pull_request_diff(make_review_input([]))

    assert result.is_empty is True
    assert result.changed_files == []
    assert result.total_diff_size == 0


def test_maximum_file_limit_is_explicit_and_predictable() -> None:
    files = [make_file("one.py"), make_file("two.py"), make_file("three.py")]

    result = process_pull_request_diff(make_review_input(files), max_files=2)

    assert [file.filename for file in result.changed_files] == ["one.py", "two.py"]
    assert result.files_truncated is True
    assert result.diff_truncated is False


def test_maximum_diff_size_limit_clips_patch_without_inventing_code() -> None:
    original_patch = "1234567890"
    result = process_pull_request_diff(
        make_review_input([make_file("app/main.py", patch=original_patch)]),
        max_total_diff_size=4,
    )

    processed_file = result.changed_files[0]
    assert processed_file.patch == "1234"
    assert processed_file.patch_truncated is True
    assert result.total_diff_size == 4
    assert result.diff_truncated is True


def test_diff_metadata_is_preserved() -> None:
    result = process_pull_request_diff(
        make_review_input(
            [
                make_file(
                    "app/main.py",
                    additions=7,
                    deletions=4,
                    changes=11,
                    patch="diff",
                )
            ]
        )
    )

    processed_file = result.changed_files[0]
    assert processed_file.filename == "app/main.py"
    assert processed_file.additions == 7
    assert processed_file.deletions == 4
    assert processed_file.changes == 11
    assert processed_file.patch == "diff"


def test_pull_request_metadata_is_preserved() -> None:
    result = process_pull_request_diff(make_review_input([make_file("app/main.py")]))

    assert result.repository_owner == "octo-owner"
    assert result.repository_name == "review-target"
    assert result.pull_request_number == 42
    assert result.pull_request_title == "Improve reviewer output"
    assert result.head_commit_sha == "abc123"
