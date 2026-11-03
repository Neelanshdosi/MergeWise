import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
import httpx
from fastapi import HTTPException, status
from mergewise_features.schemas import ResourceRateLimit
from mergewise_features.extractor import extract_frameworks_from_manifest

logger = logging.getLogger("mergewise.github")

# Global in-memory cache: key -> (value, expires_at)
_CACHE: Dict[str, tuple[Any, float]] = {}


class GitHubRateLimitError(HTTPException):
    def __init__(self, resource: str = "core", reset_epoch: Optional[int] = None, remaining: int = 0):
        self.resource = resource
        self.reset_epoch = reset_epoch
        self.remaining = remaining
        reset_time = time.strftime("%H:%M UTC", time.gmtime(reset_epoch)) if reset_epoch else "soon"
        detail = f"GitHub {resource.upper()} rate limit reached. Resets at {reset_time}."
        super().__init__(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)


class GitHubClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "MergeWise-OSS-Match-Agent/1.0",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

        self.rate_limits: Dict[str, ResourceRateLimit] = {
            "core": ResourceRateLimit(resource="core", remaining=5000, limit=5000),
            "search": ResourceRateLimit(resource="search", remaining=30, limit=30),
        }
        self.total_search_calls = 0

    def _get_cache(self, key: str, force_refresh: bool = False) -> Optional[Any]:
        if force_refresh:
            if key in _CACHE:
                del _CACHE[key]
            return None

        if key in _CACHE:
            val, expires_at = _CACHE[key]
            if time.time() < expires_at:
                return val
            del _CACHE[key]
        return None

    def _set_cache(self, key: str, value: Any, ttl_seconds: int = 600):
        # Never cache empty search results or empty lists
        if value is None:
            return
        if isinstance(value, list) and len(value) == 0:
            return
        if isinstance(value, dict) and value.get("total_count", 0) == 0:
            return

        _CACHE[key] = (value, time.time() + ttl_seconds)

    def _record_rate_limit(self, resp: httpx.Response):
        resource = resp.headers.get("x-ratelimit-resource")
        if not resource:
            resource = "search" if "/search/" in str(resp.url) else "core"

        rem_str = resp.headers.get("x-ratelimit-remaining")
        lim_str = resp.headers.get("x-ratelimit-limit")
        reset_str = resp.headers.get("x-ratelimit-reset")

        limit = int(lim_str) if lim_str and lim_str.isdigit() else (30 if resource == "search" else 5000)
        reset_epoch = int(reset_str) if reset_str and reset_str.isdigit() else int(time.time() + 60)
        reset_time = time.strftime("%H:%M UTC", time.gmtime(reset_epoch))

        # Identify if this response is an actual 403/429 rate-limit error
        is_actual_limit_response = (resp.status_code == 429) or (
            resp.status_code == 403 and (
                "rate limit" in resp.text.lower()
                or "secondary rate limit" in resp.text.lower()
            )
        )

        if rem_str and rem_str.isdigit():
            remaining = int(rem_str)
        elif is_actual_limit_response:
            remaining = 0
        else:
            remaining = limit

        # Resource-specific thresholds:
        # Search: trigger ONLY on actual limit response or when remaining is 0 (30 req/min).
        # Core: trigger on actual limit response or small safety buffer <= 50 (5000 req/hr).
        if resource == "search":
            is_limited = is_actual_limit_response or (remaining <= 0)
        else:
            is_limited = is_actual_limit_response or (remaining <= 50)

        self.rate_limits[resource] = ResourceRateLimit(
            resource=resource,
            remaining=remaining,
            limit=limit,
            reset_epoch=reset_epoch,
            reset_time=reset_time,
            is_limited=is_limited,
        )

        logger.info(
            f"[GH-RATELIMIT] Resource: {resource.upper()} | Remaining: {remaining}/{limit} | "
            f"Reset: {reset_time} | Status: {resp.status_code} | Limited: {is_limited}"
        )

        if is_limited:
            raise GitHubRateLimitError(resource=resource, reset_epoch=reset_epoch, remaining=remaining)

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        ttl_seconds: int = 600,
        force_refresh: bool = False,
    ) -> Any:
        cache_key = f"{url}?{sorted(params.items()) if params else ''}"
        cached = self._get_cache(cache_key, force_refresh=force_refresh)
        if cached is not None:
            return cached

        resource = "search" if "/search/" in url else "core"
        cached_limit = self.rate_limits.get(resource)
        if cached_limit and cached_limit.is_limited:
            if cached_limit.reset_epoch and time.time() < cached_limit.reset_epoch:
                raise GitHubRateLimitError(
                    resource=resource,
                    reset_epoch=cached_limit.reset_epoch,
                    remaining=cached_limit.remaining,
                )
            else:
                cached_limit.is_limited = False

        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(url, headers=self.headers, params=params)
            self._record_rate_limit(resp)
            resp.raise_for_status()
            data = resp.json()

        self._set_cache(cache_key, data, ttl_seconds)
        return data

    async def get_user_profile(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Fetches the authenticated user profile."""
        url = "https://api.github.com/user"
        return await self.get(url, ttl_seconds=1800, force_refresh=force_refresh)

    async def get_user_repos(self, username: str, max_repos: int = 15, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Fetches user's recent repositories (cached for 1 hour; not busted by issue refresh)."""
        url = f"https://api.github.com/users/{username}/repos"
        params = {"sort": "updated", "per_page": max_repos, "type": "all"}
        return await self.get(url, params=params, ttl_seconds=3600, force_refresh=force_refresh)

    async def get_user_events(self, username: str, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Fetches user's public contribution events (cached for 30 minutes)."""
        url = f"https://api.github.com/users/{username}/events"
        params = {"per_page": 100}
        return await self.get(url, params=params, ttl_seconds=1800, force_refresh=force_refresh)

    async def get_file_content(self, repo_full_name: str, path: str) -> Optional[str]:
        """Fetches manifest content (cached for 2 hours)."""
        url = f"https://api.github.com/repos/{repo_full_name}/contents/{path}"
        try:
            data = await self.get(url, ttl_seconds=7200)
            if isinstance(data, dict) and "content" in data:
                import base64
                return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        except Exception:
            return None
    async def get_repo_details(self, repo_full_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetches repository details including stargazers_count, pushed_at, open_issues_count, and topics.
        Cached for 30 minutes (1800s).
        """
        url = f"https://api.github.com/repos/{repo_full_name}"
        try:
            return await self.get(url, ttl_seconds=1800)
        except Exception as e:
            logger.warning(f"Failed to fetch repo details for {repo_full_name}: {e}")
            return None

    async def get_repo_manifest_frameworks(
        self,
        repo_full_name: str,
        language: Optional[str] = None,
    ) -> List[str]:
        """
        Fetches and extracts dependencies from candidate repository manifest files.
        Cached for 2 hours (7200s).
        """
        cache_key = f"repo_manifest_fw:{repo_full_name}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        lang_lower = (language or "").lower()
        if "python" in lang_lower:
            manifest_candidates = ["requirements.txt", "pyproject.toml", "Pipfile"]
        elif any(js in lang_lower for js in ["javascript", "typescript", "node"]):
            manifest_candidates = ["package.json"]
        elif "go" in lang_lower:
            manifest_candidates = ["go.mod"]
        elif "rust" in lang_lower:
            manifest_candidates = ["Cargo.toml"]
        else:
            manifest_candidates = ["package.json", "requirements.txt", "pyproject.toml"]

        all_frameworks: set[str] = set()
        for mf in manifest_candidates:
            content = await self.get_file_content(repo_full_name, mf)
            if content:
                extracted = extract_frameworks_from_manifest(mf, content)
                all_frameworks.update(extracted)
                if all_frameworks:
                    break

        result = sorted(list(all_frameworks))
        self._set_cache(cache_key, result, ttl_seconds=7200)
        return result

    async def search_single_query(
        self,
        query: str,
        limit: int = 50,
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Executes a search query against GitHub Issues Search API.
        Enforces a short pacing delay to protect against burst rate limits.
        """
        self.total_search_calls += 1
        # Pacing delay between search queries
        await asyncio.sleep(0.35)

        url = "https://api.github.com/search/issues"
        params = {"q": query, "sort": "updated", "order": "desc", "per_page": limit}
        try:
            data = await self.get(url, params=params, ttl_seconds=300, force_refresh=force_refresh)
            items = data.get("items", []) if isinstance(data, dict) else []
            return items
        except GitHubRateLimitError:
            raise
        except Exception as e:
            logger.error(f"Search query failed: '{query}' -> {e}")
            return []

    async def get_issue_comments(self, comments_url: str) -> List[Dict[str, Any]]:
        """Fetches recent comments for an issue."""
        return await self.get(comments_url, params={"per_page": 15}, ttl_seconds=600)

    async def get_issue_timeline(self, issue_url: str) -> List[Dict[str, Any]]:
        """Fetches issue timeline events (cross-references, linked PRs)."""
        timeline_url = f"{issue_url.rstrip('/')}/timeline"
        try:
            return await self.get(timeline_url, params={"per_page": 20}, ttl_seconds=600)
        except Exception:
            return []
