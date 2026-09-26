# AI GitHub Code Reviewer

AI GitHub Code Reviewer will provide automated analysis of GitHub pull requests to identify code quality issues, potential bugs, and actionable improvements. The project will be expanded incrementally with application logic and integrations in later development chunks.

## Current Status

Initial project setup

## Local Setup

1. Create and activate a Python virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install the project dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` when configuration is introduced:

   ```bash
   cp .env.example .env
   ```

4. Export a GitHub token in the shell:

   ```bash
   export GITHUB_TOKEN="your-token"
   ```

5. Retrieve a pull request and its changed files:

   ```bash
   python -m app.github_pr_reviewer OWNER REPOSITORY PULL_REQUEST_NUMBER
   ```

Run the unit tests with:

```bash
python -m pytest
```
