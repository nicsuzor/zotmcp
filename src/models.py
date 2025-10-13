"""Pydantic models for Zotero library items and research results."""

from typing import Optional
from pydantic import BaseModel, Field


class ZoteroReference(BaseModel):
    """A reference to a Zotero library item with academic citation."""

    citation: str = Field(
        ...,
        description="Complete academic citation (author, year, title, journal/publisher)"
    )
    summary: str = Field(
        ...,
        description="Brief summary of the relevant finding from this source"
    )
    citation_key: Optional[str] = Field(
        None,
        description="BetterBibTeX citation key for use in plain text citations"
    )
    doi: Optional[str] = Field(
        None,
        description="DOI of the reference if available"
    )
    uri: Optional[str] = Field(
        None,
        description="URI or URL of the reference if available"
    )
    item_key: Optional[str] = Field(
        None,
        description="Zotero item key for this reference"
    )

    def as_markdown(self) -> str:
        """Format reference as markdown."""
        parts = [f"**{self.citation}**"]

        if self.doi:
            parts.append(f"DOI: [{self.doi}](https://doi.org/{self.doi})")
        elif self.uri:
            parts.append(f"URL: {self.uri}")

        parts.append(f"\n{self.summary}")

        return "\n".join(parts)


class ResearchResult(BaseModel):
    """Result from a research query with literature references."""

    response: str = Field(
        ...,
        description="Synthesized response to the research question based on the literature"
    )
    summary: str = Field(
        ...,
        description="2-3 sentence summary of the main findings"
    )
    literature: list[ZoteroReference] = Field(
        default_factory=list,
        description="List of academic references supporting the response"
    )
    search_queries: Optional[list[str]] = Field(
        default=None,
        description="List of search queries used to find the literature"
    )

    def as_markdown(self) -> str:
        """Format research result as markdown."""
        parts = [
            "## Summary",
            self.summary,
            "",
            "## Response",
            self.response,
            "",
            "## References"
        ]

        if self.literature:
            for i, ref in enumerate(self.literature, 1):
                parts.append(f"\n### {i}. {ref.citation}")
                parts.append(ref.summary)
                if ref.doi:
                    parts.append(f"DOI: [{ref.doi}](https://doi.org/{ref.doi})")
                elif ref.uri:
                    parts.append(f"URL: {ref.uri}")
        else:
            parts.append("*No references found for this query.*")

        return "\n".join(parts)
