import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from ..services.github import GitHubClient
from ..services.health import analyze_repo_health, RepoHealthReport

logger = logging.getLogger("mergewise.agent.tools")


def get_setup_source_priority(file_path: str) -> int:
    """
    Returns source priority rank for setup commands:
    1: CONTRIBUTING/contributing docs
    2: development/dev docs
    3: README docs
    4: quickstart/install docs
    5: Other / configs
    """
    p = file_path.lower()
    if "contribut" in p:
        return 1
    if "develop" in p or "/dev." in p or p.startswith("dev.") or "/dev/" in p or p in ("dev.md", "dev.rst"):
        return 2
    if "readme" in p:
        return 3
    if "quickstart" in p or "install" in p:
        return 4
    return 5


class RepoHealthToolInput(BaseModel):
    repo_full_name: str = Field(description="Target repository in 'owner/repo' format")


class SearchRepoDocsToolInput(BaseModel):
    repo_full_name: str = Field(description="Target repository in 'owner/repo' format")
    query: str = Field(description="What to search for, e.g. 'setup commands', 'test commands', 'contributing guidelines'")


class VerifyRepoFilesToolInput(BaseModel):
    repo_full_name: str = Field(description="Target repository in 'owner/repo' format")
    file_paths: List[str] = Field(description="List of relative file paths proposed to edit or inspect, e.g. ['src/core/parser.py']")


class EstimateEffortToolInput(BaseModel):
    repo_full_name: str = Field(description="Target repository in 'owner/repo' format")
    issue_title: str = Field(description="Title of the issue")
    body_length: int = Field(default=0, description="Length of issue description in characters")
    labels: List[str] = Field(default_factory=list, description="Labels on the issue")
    has_code_snippet: bool = Field(default=False, description="Whether the issue description includes code blocks")
    matching_frameworks_count: int = Field(default=0, description="How many repo dependencies match user skills")


# Definitions of the 4 supported agent tools for Gemini function declarations
TOOL_DEFINITIONS = [
    {
        "name": "get_repo_health",
        "description": "Calculates real maintainer responsiveness metrics (median response time, first-time PR merge rate, days since push, contributing guide).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "repo_full_name": {
                    "type": "STRING",
                    "description": "Target repository in 'owner/repo' format"
                }
            },
            "required": ["repo_full_name"]
        }
    },
    {
        "name": "search_repo_docs",
        "description": "Searches README, CONTRIBUTING, workflow files, and package manifests for verified setup and test commands with file citations.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "repo_full_name": {
                    "type": "STRING",
                    "description": "Target repository in 'owner/repo' format"
                },
                "query": {
                    "type": "STRING",
                    "description": "Query to search for, e.g. 'setup test workflow instructions'"
                }
            },
            "required": ["repo_full_name", "query"]
        }
    },
    {
        "name": "verify_repo_files",
        "description": "Checks the GitHub Git Tree API to strictly verify whether proposed files to edit actually exist in the repository file tree.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "repo_full_name": {
                    "type": "STRING",
                    "description": "Target repository in 'owner/repo' format"
                },
                "file_paths": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "List of relative file paths to verify"
                }
            },
            "required": ["repo_full_name", "file_paths"]
        }
    },
    {
        "name": "estimate_effort",
        "description": "Estimates realistic effort, difficulty level, and hours range based on issue labels, description clarity, and developer familiarity.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "repo_full_name": {
                    "type": "STRING",
                    "description": "Target repository in 'owner/repo' format"
                },
                "issue_title": {
                    "type": "STRING",
                    "description": "Title of the issue"
                },
                "body_length": {
                    "type": "INTEGER",
                    "description": "Character length of the issue description"
                },
                "labels": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "List of issue labels"
                },
                "has_code_snippet": {
                    "type": "BOOLEAN",
                    "description": "Whether description has backtick code snippets"
                },
                "matching_frameworks_count": {
                    "type": "INTEGER",
                    "description": "Count of shared frameworks"
                }
            },
            "required": ["repo_full_name", "issue_title"]
        }
    }
]


class AgentToolExecutor:
    """
    Executes agent tools with:
    - Per-tool timeouts
    - Strict target repository validation (guards against prompt injection directing tool to other repos)
    - Grounding validation: file tree verification and file citations
    """
    def __init__(self, target_repo: str, gh_client: GitHubClient, per_tool_timeout: float = 25.0):
        self.target_repo = target_repo.lower().strip()
        self.gh_client = gh_client
        self.per_tool_timeout = per_tool_timeout

    def _validate_repo(self, repo_full_name: str):
        cleaned = repo_full_name.lower().strip()
        if cleaned != self.target_repo:
            raise ValueError(
                f"Unauthorized repository '{repo_full_name}'. Tool execution is strictly restricted to '{self.target_repo}'."
            )

    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches tool execution with per-tool timeout, timing logs, and security validation."""
        if tool_name not in {"get_repo_health", "search_repo_docs", "verify_repo_files", "estimate_effort"}:
            return {"error": f"Tool '{tool_name}' is not recognized. Only 4 registered tools are allowed."}

        # Guard: check repo_full_name argument if present
        if "repo_full_name" in args:
            try:
                self._validate_repo(args["repo_full_name"])
            except ValueError as ve:
                return {"error": str(ve)}

        start_time = time.perf_counter()
        try:
            res = await asyncio.wait_for(
                self._dispatch(tool_name, args),
                timeout=self.per_tool_timeout
            )
            elapsed = time.perf_counter() - start_time
            logger.info(f"[TOOL-TIMER] Tool '{tool_name}' finished in {elapsed:.3f}s")
            return res
        except asyncio.TimeoutError:
            elapsed = time.perf_counter() - start_time
            logger.warning(f"[TOOL-TIMER] Tool '{tool_name}' timed out after {elapsed:.3f}s (limit={self.per_tool_timeout}s)")
            return {"error": f"Tool '{tool_name}' timed out after {self.per_tool_timeout}s."}
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.error(f"[TOOL-TIMER] Tool '{tool_name}' failed after {elapsed:.3f}s: {e}")
            return {"error": f"Tool execution failed: {str(e)}"}

    async def _dispatch(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "get_repo_health":
            return await self._tool_get_repo_health(args)
        elif tool_name == "search_repo_docs":
            return await self._tool_search_repo_docs(args)
        elif tool_name == "verify_repo_files":
            return await self._tool_verify_repo_files(args)
        elif tool_name == "estimate_effort":
            return await self._tool_estimate_effort(args)
        return {"error": "Unknown tool"}

    async def _tool_get_repo_health(self, args: Dict[str, Any]) -> Dict[str, Any]:
        health = await analyze_repo_health(self.target_repo, self.gh_client)
        return health.model_dump()

    async def _tool_search_repo_docs(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inspects README, CONTRIBUTING, dev docs, quickstart/install docs, package manifests, and CI workflows.
        Extracts verified commands with file citations.
        Prefers setup commands in priority order:
        1. CONTRIBUTING/contributing docs
        2. development/dev docs
        3. README
        4. quickstart/install docs
        Returns 'not found in repo docs' if absent.
        """
        # Exhaustive list of documentation, CI workflow, and configuration file candidates
        doc_candidates = [
            # 1. CONTRIBUTING in root, .github/, and docs/
            "CONTRIBUTING.md", "CONTRIBUTING.rst", "CONTRIBUTING.txt", "CONTRIBUTING",
            "contributing.md", "contributing.rst", "contributing.txt", "contributing",
            ".github/CONTRIBUTING.md", ".github/CONTRIBUTING.rst", ".github/CONTRIBUTING",
            "docs/contributing.md", "docs/contributing.rst", "docs/contributing.txt",
            "docs/CONTRIBUTING.md", "docs/CONTRIBUTING.rst",
            # 2. Development / Dev docs
            "DEVELOPMENT.md", "DEVELOPMENT.rst", "DEVELOPMENT.txt", "DEVELOPMENT",
            "development.md", "development.rst", "development.txt", "development",
            ".github/DEVELOPMENT.md", ".github/DEVELOPMENT.rst",
            "docs/development.md", "docs/development.rst", "docs/development.txt", "docs/development",
            "docs/DEVELOPMENT.md", "docs/DEVELOPMENT.rst",
            "DEV.md", "dev.md", "docs/dev.md", "docs/dev.rst",
            # 3. README candidates
            "README.md", "README.rst", "README.txt", "README",
            "readme.md", "readme.rst",
            # 4. Quickstart / Install guides
            "docs/quickstart.md", "docs/quickstart.rst", "quickstart.md", "quickstart.rst",
            "docs/install.md", "docs/install.rst", "INSTALL.md", "INSTALL.rst", "install.md",
            # Testing guides & workflows & configs
            "docs/testing.md", "docs/testing.rst", "docs/tests.rst", "docs/tests.md",
            ".github/workflows/tests.yaml", ".github/workflows/tests.yml",
            ".github/workflows/test.yaml", ".github/workflows/test.yml",
            ".github/workflows/ci.yaml", ".github/workflows/ci.yml",
            "tox.ini", "noxfile.py", "Makefile", "pyproject.toml", "package.json"
        ]

        found_citations: Dict[str, str] = {}
        setup_candidates: List[tuple[int, str, str]] = []  # (priority, citation_file, command)
        test_candidates: List[tuple[int, str, str]] = []   # (priority, citation_file, command)

        # Check git tree first if available to avoid firing dozens of requests for nonexistent files
        files_to_check = doc_candidates
        try:
            tree = await self.gh_client.get_repo_git_tree(self.target_repo)
            if tree:
                tree_set = {t.lower() for t in tree}
                filtered = [p for p in doc_candidates if p.lower() in tree_set]
                if filtered:
                    files_to_check = filtered
        except Exception as e:
            logger.debug(f"Git tree lookup in search_repo_docs fell back to candidate list: {e}")

        # Fetch contents of available files concurrently
        async def fetch_one(path: str):
            try:
                c = await self.gh_client.get_file_content(self.target_repo, path)
                return path, c
            except Exception:
                return path, None

        fetched = await asyncio.gather(*[fetch_one(p) for p in files_to_check])

        for doc_file, content in fetched:
            if not content:
                continue

            found_citations[doc_file] = content[:4000]
            setup_prio = get_setup_source_priority(doc_file)

            # 1. Search for setup commands in this file
            if "uv sync" in content or "setup-uv" in content:
                cmd = "uv sync" if "uv sync" in content else "uv pip install -e '.[dev]'"
                setup_candidates.append((setup_prio, doc_file, cmd))
            elif "pip install" in content:
                if "pip install -e" in content:
                    cmd = "pip install -e '.[dev]'" if "dev" in content else "pip install -e ."
                elif "requirements.txt" in content:
                    cmd = "pip install -r requirements.txt"
                else:
                    cmd = "pip install ."
                setup_candidates.append((setup_prio, doc_file, cmd))
            elif "poetry install" in content:
                setup_candidates.append((setup_prio, doc_file, "poetry install"))
            elif "npm install" in content or "pnpm install" in content or "yarn install" in content:
                pkg_manager = "pnpm" if "pnpm" in content else ("yarn" if "yarn" in content else "npm")
                setup_candidates.append((setup_prio, doc_file, f"{pkg_manager} install"))
            elif "cargo build" in content:
                setup_candidates.append((setup_prio, doc_file, "cargo build"))
            elif "make setup" in content or "make install" in content:
                cmd = "make setup" if "make setup" in content else "make install"
                setup_candidates.append((setup_prio, doc_file, cmd))

            # 2. Search for test commands in this file
            test_prio = setup_prio
            if "tox run" in content or "tox r " in content or "tox -e" in content or ("tox" in content and doc_file.endswith(".ini")):
                test_candidates.append((test_prio, doc_file, "tox"))
            elif "pytest" in content or "[tool.pytest" in content:
                test_candidates.append((test_prio, doc_file, "pytest"))
            elif "nox" in content and doc_file.endswith(".py"):
                test_candidates.append((test_prio, doc_file, "nox"))
            elif "npm test" in content or '"test":' in content:
                test_candidates.append((test_prio, doc_file, "npm test"))
            elif "cargo test" in content:
                test_candidates.append((test_prio, doc_file, "cargo test"))
            elif "go test ./..." in content:
                test_candidates.append((test_prio, doc_file, "go test ./..."))
            elif "make test" in content:
                test_candidates.append((test_prio, doc_file, "make test"))

        # Select highest-priority setup command
        setup_command = "Not documented in this repo's docs"
        setup_citation = "Not documented in this repo's docs"
        if setup_candidates:
            # Sort by priority ascending (1 is highest priority)
            setup_candidates.sort(key=lambda x: x[0])
            _, best_setup_cit, best_setup_cmd = setup_candidates[0]
            setup_command = best_setup_cmd
            setup_citation = best_setup_cit

        # Select highest-priority test command
        test_command = "Not documented in this repo's docs"
        test_citation = "Not documented in this repo's docs"
        if test_candidates:
            test_candidates.sort(key=lambda x: x[0])
            _, best_test_cit, best_test_cmd = test_candidates[0]
            test_command = best_test_cmd
            test_citation = best_test_cit

        return {
            "setup_command": setup_command,
            "setup_citation": setup_citation,
            "test_command": test_command,
            "test_citation": test_citation,
            "indexed_files": list(found_citations.keys()),
        }

    async def _tool_verify_repo_files(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uses GitHub Git Tree API to strictly verify if proposed files exist in repo tree.
        Filters out nonexistent files.
        """
        raw_paths = args.get("file_paths", [])
        if not isinstance(raw_paths, list):
            return {"error": "file_paths must be a list of string file paths"}

        tree_files = await self.gh_client.get_repo_git_tree(self.target_repo)
        tree_set = set(tree_files)

        verified: List[str] = []
        nonexistent: List[str] = []

        for p in raw_paths:
            clean_p = str(p).strip().lstrip("/")
            if clean_p in tree_set:
                verified.append(clean_p)
            else:
                nonexistent.append(clean_p)

        return {
            "repo": self.target_repo,
            "total_repo_files_indexed": len(tree_files),
            "verified_files": verified,
            "nonexistent_files": nonexistent,
            "grounding_status": "All verified" if not nonexistent else f"{len(nonexistent)} nonexistent file(s) rejected"
        }

    async def _tool_estimate_effort(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates realistic effort, hours range, and complexity reasoning.
        Allows UI override.
        """
        labels = [l.lower() for l in args.get("labels", [])]
        body_len = args.get("body_length", 0)
        has_snippet = args.get("has_code_snippet", False)
        fw_count = args.get("matching_frameworks_count", 0)

        is_good_first = any("good first" in l or "beginner" in l or "easy" in l for l in labels)
        is_doc = any("doc" in l for l in labels)
        is_bug = any("bug" in l for l in labels)

        if is_doc or (is_good_first and body_len < 800):
            difficulty = "Beginner"
            hours_range = "1–3 hours"
            reason = "Well-scoped task with minimal architectural complexity and existing patterns."
        elif is_bug and (has_snippet or fw_count > 0):
            difficulty = "Intermediate"
            hours_range = "3–6 hours"
            reason = "Concrete bug with code context, requiring test reproduction and targeted fix."
        elif is_good_first:
            difficulty = "Beginner"
            hours_range = "2–4 hours"
            reason = "Flagged as accessible for new contributors; requires standard setup and test verification."
        else:
            difficulty = "Intermediate"
            hours_range = "4–8 hours"
            reason = "Requires understanding module conventions, adding test coverage, and documentation."

        return {
            "difficulty": difficulty,
            "hours_range": hours_range,
            "reasoning": reason,
            "user_can_override": True
        }
