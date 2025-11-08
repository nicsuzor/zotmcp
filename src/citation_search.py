"""
Citation Explorer - Academic literature search via OpenAlex API.

This module provides tools for discovering and exploring academic literature
using the OpenAlex database (240M+ works, no auth required).

Migrated from outlook_mcp to zotmcp and adapted to async.
"""

import asyncio
import httpx
import logging
import os
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Author(BaseModel):
    """Author information."""

    id: Optional[str] = None
    display_name: Optional[str] = None
    orcid: Optional[str] = None


class Citation(BaseModel):
    """Citation/Paper information from OpenAlex."""

    id: str
    doi: Optional[str] = None
    title: Optional[str] = None
    publication_year: Optional[int] = None
    cited_by_count: int = 0
    authors: List[Author] = Field(default_factory=list)
    abstract: Optional[str] = None
    primary_location: Optional[Dict[str, Any]] = None
    open_access: Optional[Dict[str, Any]] = None
    topics: List[Dict[str, Any]] = Field(default_factory=list)
    cited_by_api_url: Optional[str] = None
    referenced_works: List[str] = Field(default_factory=list)


class OpenAlexClient:
    """Client for interacting with OpenAlex API (async version)."""

    BASE_URL = "https://api.openalex.org"

    def __init__(self, email: Optional[str] = None, max_retries: int = 5):
        """
        Initialize OpenAlex client.

        Args:
            email: Email for polite pool (10 req/sec vs 1 req/sec)
            max_retries: Maximum number of retry attempts
        """
        self.email = email
        self.max_retries = max_retries

    async def _make_request(
        self, endpoint: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Make a request to OpenAlex API with exponential backoff retry logic.

        Args:
            endpoint: API endpoint (e.g., '/works')
            params: Query parameters

        Returns:
            JSON response from API
        """
        # Add email to params for polite pool
        if self.email:
            params["mailto"] = self.email

        url = f"{self.BASE_URL}{endpoint}"

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"OpenAlex request: {url} with params {params}")
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, params=params, timeout=30.0)

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 403:
                    # Rate limited
                    wait_time = 2**attempt
                    logger.warning(
                        f"Rate limited, waiting {wait_time}s before retry {attempt + 1}/{self.max_retries}"
                    )
                    await asyncio.sleep(wait_time)
                elif response.status_code >= 500:
                    # Server error
                    wait_time = 2**attempt
                    logger.warning(
                        f"Server error {response.status_code}, waiting {wait_time}s before retry {attempt + 1}/{self.max_retries}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    # Other error, don't retry
                    response.raise_for_status()

            except httpx.TimeoutException:
                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        f"Request timeout, waiting {wait_time}s before retry {attempt + 1}/{self.max_retries}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise

        raise Exception(f"Failed after {self.max_retries} retries")

    def _parse_work(self, work_data: Dict[str, Any]) -> Citation:
        """Parse OpenAlex work data into Citation model."""
        authors = []
        if work_data.get("authorships"):
            for authorship in work_data["authorships"][
                :10
            ]:  # Limit to first 10 authors
                author_data = authorship.get("author", {})
                authors.append(
                    Author(
                        id=author_data.get("id"),
                        display_name=author_data.get("display_name"),
                        orcid=author_data.get("orcid"),
                    )
                )

        # Get abstract
        abstract = None
        if work_data.get("abstract_inverted_index"):
            # Convert inverted index to text
            inverted = work_data["abstract_inverted_index"]
            words = {}
            for word, positions in inverted.items():
                for pos in positions:
                    words[pos] = word
            abstract = " ".join(words[i] for i in sorted(words.keys()))

        return Citation(
            id=work_data["id"],
            doi=work_data.get("doi"),
            title=work_data.get("title"),
            publication_year=work_data.get("publication_year"),
            cited_by_count=work_data.get("cited_by_count", 0),
            authors=authors,
            abstract=abstract,
            primary_location=work_data.get("primary_location"),
            open_access=work_data.get("open_access"),
            topics=work_data.get("topics", []),
            cited_by_api_url=work_data.get("cited_by_api_url"),
            referenced_works=work_data.get("referenced_works", []),
        )

    async def search_papers(
        self,
        query: str,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        open_access_only: bool = False,
        limit: int = 25,
        sort: str = "cited_by_count:desc",
    ) -> List[Citation]:
        """
        Search for academic papers.

        Args:
            query: Search query (searches title, abstract, full text)
            year_from: Filter by publication year (from)
            year_to: Filter by publication year (to)
            open_access_only: Only return open access papers
            limit: Maximum number of results (max 200)
            sort: Sort order (e.g., "cited_by_count:desc", "publication_year:desc")

        Returns:
            List of Citation objects
        """
        params = {"search": query, "per-page": min(limit, 200), "sort": sort}

        # Build filter
        filters = []
        if year_from and year_to:
            filters.append(f"publication_year:{year_from}-{year_to}")
        elif year_from:
            filters.append(f"publication_year:>={year_from}")
        elif year_to:
            filters.append(f"publication_year:<={year_to}")

        if open_access_only:
            filters.append("is_oa:true")

        if filters:
            params["filter"] = ",".join(filters)

        data = await self._make_request("/works", params)
        results = data.get("results", [])

        logger.info(
            f"Found {data.get('meta', {}).get('count', 0)} total papers, returning {len(results)}"
        )
        return [self._parse_work(work) for work in results]

    async def get_paper_by_doi(self, doi: str) -> Optional[Citation]:
        """
        Get a paper by DOI.

        Args:
            doi: DOI of the paper

        Returns:
            Citation object or None if not found
        """
        # Ensure DOI is in URL format
        if not doi.startswith("http"):
            doi = f"https://doi.org/{doi}"

        try:
            data = await self._make_request(f"/works/{doi}", {})
            return self._parse_work(data)
        except Exception as e:
            logger.error(f"Error fetching paper by DOI {doi}: {e}")
            return None

    async def get_paper_by_id(self, openalex_id: str) -> Optional[Citation]:
        """
        Get a paper by OpenAlex ID.

        Args:
            openalex_id: OpenAlex ID (e.g., 'W2741809807' or full URL)

        Returns:
            Citation object or None if not found
        """
        # Handle both short and full IDs
        if openalex_id.startswith("http"):
            openalex_id = openalex_id.split("/")[-1]

        try:
            data = await self._make_request(f"/works/{openalex_id}", {})
            return self._parse_work(data)
        except Exception as e:
            logger.error(f"Error fetching paper by ID {openalex_id}: {e}")
            return None

    async def get_paper_citations(
        self,
        paper_id: str,
        limit: int = 50,
        year_from: Optional[int] = None,
        sort: str = "cited_by_count:desc",
    ) -> List[Citation]:
        """
        Get papers that cite a given paper (forward citations).

        Args:
            paper_id: OpenAlex ID or DOI of the paper
            limit: Maximum number of results
            year_from: Filter citations from this year onwards
            sort: Sort order

        Returns:
            List of Citation objects
        """
        # Handle DOI
        if paper_id.startswith("10."):
            paper_id = f"https://doi.org/{paper_id}"
        elif not paper_id.startswith("http") and not paper_id.startswith("W"):
            paper_id = f"W{paper_id}"

        params = {
            "filter": f"cites:{paper_id}",
            "per-page": min(limit, 200),
            "sort": sort,
        }

        if year_from:
            params["filter"] += f",publication_year:>={year_from}"

        data = await self._make_request("/works", params)
        results = data.get("results", [])

        logger.info(f"Found {len(results)} papers citing {paper_id}")
        return [self._parse_work(work) for work in results]

    async def get_referenced_works(
        self, paper_id: str, limit: int = 50
    ) -> List[Citation]:
        """
        Get papers referenced by a given paper (backward citations).

        Args:
            paper_id: OpenAlex ID or DOI of the paper
            limit: Maximum number of results

        Returns:
            List of Citation objects
        """
        # First get the paper to get its referenced_works
        paper = None
        if paper_id.startswith("10."):
            paper = await self.get_paper_by_doi(paper_id)
        else:
            paper = await self.get_paper_by_id(paper_id)

        if not paper or not paper.referenced_works:
            logger.info(f"No referenced works found for {paper_id}")
            return []

        # Batch fetch referenced works (up to 50 at a time)
        # Extract work IDs from full OpenAlex URLs (e.g., https://openalex.org/W12345 -> W12345)
        ref_ids = [ref.split("/")[-1] for ref in paper.referenced_works[:limit]]
        if not ref_ids:
            return []

        # Use pipe separator for batch lookup
        batch_ids = "|".join(ref_ids)
        params = {
            "filter": f"openalex_id:{batch_ids}",
            "per-page": min(len(ref_ids), 50),
        }

        data = await self._make_request("/works", params)
        results = data.get("results", [])

        logger.info(f"Found {len(results)} referenced works for {paper_id}")
        return [self._parse_work(work) for work in results]

    async def search_by_author(
        self,
        author_name: str,
        limit: int = 50,
        year_from: Optional[int] = None,
        sort: str = "cited_by_count:desc",
    ) -> List[Citation]:
        """
        Search for papers by author name (two-step lookup).

        Args:
            author_name: Author name to search for
            limit: Maximum number of papers to return
            year_from: Filter papers from this year onwards
            sort: Sort order

        Returns:
            List of Citation objects
        """
        # Step 1: Find author ID
        author_params = {"search": author_name, "per-page": 1}
        author_data = await self._make_request("/authors", author_params)

        if not author_data.get("results"):
            logger.warning(f"No author found matching '{author_name}'")
            return []

        author = author_data["results"][0]
        author_id = author["id"]
        logger.info(f"Found author: {author.get('display_name')} ({author_id})")

        # Step 2: Get papers by author
        params = {
            "filter": f"authorships.author.id:{author_id}",
            "per-page": min(limit, 200),
            "sort": sort,
        }

        if year_from:
            params["filter"] += f",publication_year:>={year_from}"

        data = await self._make_request("/works", params)
        results = data.get("results", [])

        logger.info(f"Found {len(results)} papers by {author.get('display_name')}")
        return [self._parse_work(work) for work in results]

    async def get_related_papers(
        self, paper_id: str, limit: int = 20, method: str = "both"
    ) -> Dict[str, List[Citation]]:
        """
        Get papers related to a given paper through citations.

        Args:
            paper_id: OpenAlex ID or DOI of the paper
            limit: Maximum number of results per direction
            method: "forward" (citing papers), "backward" (referenced papers), or "both"

        Returns:
            Dictionary with keys "forward" and/or "backward" containing Citation lists
        """
        results = {}

        if method in ["forward", "both"]:
            results["forward"] = await self.get_paper_citations(paper_id, limit=limit)

        if method in ["backward", "both"]:
            results["backward"] = await self.get_referenced_works(paper_id, limit=limit)

        return results


# Create a default client instance
# Users can override email by setting environment variable OPENALEX_EMAIL
_client = OpenAlexClient(email=os.getenv("OPENALEX_EMAIL"))


# Public API functions
async def search_papers(
    query: str,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    open_access_only: bool = False,
    limit: int = 25,
) -> List[Dict[str, Any]]:
    """
    Search for academic papers using OpenAlex.

    Args:
        query: Search query (searches title, abstract, full text)
        year_from: Filter by publication year (from)
        year_to: Filter by publication year (to)
        open_access_only: Only return open access papers
        limit: Maximum number of results (max 200)

    Returns:
        List of paper dictionaries
    """
    results = await _client.search_papers(
        query, year_from, year_to, open_access_only, limit
    )
    return [r.model_dump() for r in results]


async def get_paper_citations(
    paper_id: str, limit: int = 50, year_from: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Get papers that cite a given paper (forward citations).

    Args:
        paper_id: OpenAlex ID (e.g., 'W2741809807') or DOI
        limit: Maximum number of results
        year_from: Filter citations from this year onwards

    Returns:
        List of citing paper dictionaries
    """
    results = await _client.get_paper_citations(paper_id, limit, year_from)
    return [r.model_dump() for r in results]


async def get_referenced_works(paper_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get papers referenced by a given paper (backward citations).

    Args:
        paper_id: OpenAlex ID or DOI
        limit: Maximum number of results

    Returns:
        List of referenced paper dictionaries
    """
    results = await _client.get_referenced_works(paper_id, limit)
    return [r.model_dump() for r in results]


async def search_by_author(
    author_name: str, limit: int = 50, year_from: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Search for papers by author name.

    Args:
        author_name: Author name to search for
        limit: Maximum number of papers to return
        year_from: Filter papers from this year onwards

    Returns:
        List of paper dictionaries
    """
    results = await _client.search_by_author(author_name, limit, year_from)
    return [r.model_dump() for r in results]


async def get_paper_details(paper_id: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific paper.

    Args:
        paper_id: OpenAlex ID or DOI

    Returns:
        Paper dictionary or None if not found
    """
    if paper_id.startswith("10."):
        result = await _client.get_paper_by_doi(paper_id)
    else:
        result = await _client.get_paper_by_id(paper_id)

    return result.model_dump() if result else None
