# Enhanced Search System

This document describes the enhanced search capabilities added to ZotMCP, including fuzzy metadata matching and hybrid search functionality.

## Overview

The search system has been significantly enhanced with:
- **Fuzzy string matching** for metadata fields (handles typos and variations)
- **Hybrid search** combining semantic embeddings with fuzzy text matching
- **Advanced filtering** by date ranges, item types, and multiple fields
- **Improved author search** with fuzzy name matching and no item limits
- **Exact match tools** for DOI and citation key lookups

## New MCP Tools

### 1. `advanced_search` - Most Powerful Search Tool

The primary search tool that combines all capabilities with flexible modes and filters.

**Parameters:**
- `query` (str): Main search query
- `n_results` (int): Number of results (default: 20, max: 100)
- `search_mode` (str): Search strategy - "hybrid" (recommended), "semantic", or "metadata"
- `author` (str, optional): Filter by author name (fuzzy matching)
- `title` (str, optional): Search by title (fuzzy matching)
- `date_from` (int, optional): Earliest publication year
- `date_to` (int, optional): Latest publication year
- `item_type` (str, optional): Filter by type (e.g., 'journalArticle', 'book')
- `fuzzy_threshold` (int): Minimum fuzzy match score 0-100 (default: 60)
- `semantic_weight` (float): Weight for semantic vs fuzzy in hybrid mode (default: 0.6)

**Examples:**
```python
# Hybrid search with date filter
advanced_search("machine learning ethics", date_from=2020, search_mode="hybrid")

# Search by author with fuzzy matching
advanced_search("privacy", author="Smith", date_from=2020)

# Pure metadata search for title
advanced_search("", title="Artificial Intelligence", search_mode="metadata")

# Adjust scoring weights in hybrid mode
advanced_search("AI governance", semantic_weight=0.7)  # Favor semantic over fuzzy
```

### 2. `search_by_fuzzy_author` - Improved Author Search

Enhanced author search with fuzzy matching to handle name variations and typos.

**Improvements over old `search_zotero_by_author`:**
- Fuzzy matching handles typos ("Suzor" matches "Suzor, Nicolas")
- No 1000-item limit
- Relevance ranking by match quality
- Optional date and type filtering

**Parameters:**
- `author_name` (str): Author name (can be partial)
- `n_results` (int): Number of results (default: 20)
- `fuzzy_threshold` (int): Minimum match score 0-100 (default: 70)
- `date_from` (int, optional): Earliest publication year
- `date_to` (int, optional): Latest publication year
- `item_type` (str, optional): Filter by type

**Examples:**
```python
# Find all papers by Suzor
search_by_fuzzy_author("Suzor")

# Find recent papers by John Smith
search_by_fuzzy_author("John Smith", date_from=2020)

# Find journal articles only
search_by_fuzzy_author("Doe", item_type="journalArticle")
```

### 3. `search_by_doi` - DOI Lookup

Exact match search for papers by DOI.

**Parameters:**
- `doi` (str): DOI to search for (with or without prefix/URL)

**Examples:**
```python
search_by_doi("10.1038/nature12373")
search_by_doi("https://doi.org/10.1038/nature12373")  # URL format works too
```

### 4. `search_by_citation_key` - Citation Key Lookup

Exact match search for papers by BetterBibTeX citation key.

**Parameters:**
- `citation_key` (str): BetterBibTeX citation key

**Example:**
```python
search_by_citation_key("smith2020machine")
```

## Search Modes Explained

### Semantic Search (Embeddings Only)

Uses vector embeddings to find conceptually similar papers regardless of exact wording.

**Best for:**
- Exploratory research
- Finding papers on similar topics
- When you don't know exact terminology

**Example:**
```python
advanced_search("protecting user data online", search_mode="semantic")
# Finds papers about privacy, data protection, security, etc.
```

### Metadata Search (Fuzzy Text Only)

Uses fuzzy string matching on metadata fields (title, author, abstract, etc.).

**Best for:**
- Finding papers by partial title
- Author name searches with typos
- Exact terminology matching

**Example:**
```python
advanced_search("Machine Learning", search_mode="metadata", fuzzy_threshold=80)
# Finds papers with "Machine Learning" in title/abstract
```

### Hybrid Search (Recommended)

Combines both semantic and fuzzy matching with weighted scoring.

**Best for:**
- Most searches (recommended default)
- Balancing conceptual relevance with exact matches
- Finding papers that are both topically relevant AND match your keywords

**Example:**
```python
advanced_search("AI ethics", search_mode="hybrid", semantic_weight=0.6)
# Finds papers conceptually about AI ethics AND containing related keywords
```

**Adjusting weights:**
- `semantic_weight=0.8` → Favor conceptual similarity
- `semantic_weight=0.4` → Favor exact keyword matches
- Default `semantic_weight=0.6` provides good balance

## Fuzzy Matching Details

### How Fuzzy Matching Works

Uses RapidFuzz library with multiple matching strategies:
1. **Token Sort Ratio**: Handles word order differences
   - "John Smith" ↔ "Smith, John" = high score
2. **Partial Ratio**: Handles partial matches
   - "Suzor" matches "Nicolas Suzor"
3. **Simple Ratio**: Handles typos
   - "Jon Smith" matches "John Smith"

### Fuzzy Threshold

Controls how strict matching should be (0-100 scale):
- **70-90**: Strict matching (fewer false positives)
- **60-69**: Moderate matching (default)
- **50-59**: Lenient matching (more results, some false positives)

### Author Name Variations Handled

The fuzzy author search handles:
- Name order: "Smith, John" ↔ "John Smith"
- Initials: "Smith, J." ↔ "Smith, John"
- Nicknames: "Nick Suzor" ↔ "Nicolas Suzor"
- Typos: "Jon Smith" ↔ "John Smith"
- Partial names: "Suzor" matches "Nicolas Suzor"

## Date Filtering

Date filtering works across all search modes:
- Extracts year from various formats (ISO dates, "Jan 2024", etc.)
- Supports range queries: `date_from=2020, date_to=2024`
- Items without dates are excluded from date-filtered searches

**Examples:**
```python
# Papers from 2020 onwards
advanced_search("AI governance", date_from=2020)

# Papers in specific range
advanced_search("privacy law", date_from=2018, date_to=2023)

# Recent papers only
advanced_search("machine learning", date_from=2023)
```

## Output Format Enhancements

Search results now include additional scoring information:

```python
{
    "citation": "Full citation string",
    "excerpt": "Text excerpt from document",
    "semantic_score": 0.85,      # NEW: Semantic similarity (0-1)
    "fuzzy_score": 72.5,         # NEW: Fuzzy match score (0-100)
    "combined_score": 78.3,      # NEW: Hybrid score (0-100)
    "matched_field": "title",    # NEW: Which field matched in fuzzy search
    "doi_or_url": "...",
    "zotero_key": "...",
    "citation_key": "...",
    # ... other fields
}
```

## Migration Guide

### From `search_zotero_by_author`

Old code:
```python
search_zotero_by_author("Smith")
```

New recommended approach:
```python
search_by_fuzzy_author("Smith", fuzzy_threshold=70)
```

The old `search_zotero_by_author` still works but now uses fuzzy matching internally for better results.

### From basic `search`

Old code:
```python
search("machine learning ethics", n_results=10, filter_type="journalArticle")
```

Enhanced version with more control:
```python
advanced_search(
    "machine learning ethics",
    n_results=10,
    item_type="journalArticle",
    search_mode="hybrid",
    date_from=2020
)
```

## Technical Implementation

### New Modules

1. **`src/search_utils.py`**: Core fuzzy matching utilities
   - Author name normalization
   - Fuzzy matching algorithms
   - Date parsing and filtering
   - Score combination functions

2. **`src/enhanced_search.py`**: High-level search engine
   - `fuzzy_metadata_search()`: Pure metadata search
   - `fuzzy_author_search()`: Enhanced author search
   - `hybrid_search()`: Combined semantic + fuzzy
   - `advanced_search()`: Unified search with all options

### Dependencies

- **rapidfuzz (>=3.0.0)**: Fast fuzzy string matching
  - Much faster than FuzzyWuzzy/TheFuzz
  - C++ implementation with Python bindings
  - Handles Unicode correctly

### Performance Considerations

**Metadata Search Limitations:**
- ChromaDB doesn't support full-text metadata search
- Must fetch items and filter in Python
- Default limit: 5000 items scanned
- For very large libraries, consider semantic search first

**Optimization Tips:**
1. Use semantic search when possible (much faster)
2. Combine filters to reduce items scanned
3. Adjust `max_items_to_scan` if needed
4. Use exact match tools (DOI, citation key) when possible

## Testing

Run the test suite to verify fuzzy matching:

```bash
uv run python test_fuzzy_search.py
```

Tests cover:
- Author name normalization
- Fuzzy author matching (including typos)
- Fuzzy title matching
- Date parsing
- Date range filtering

## Future Enhancements

Potential improvements:
1. **Secondary text index**: Add SQLite FTS or Elasticsearch for faster metadata search
2. **Caching**: Cache frequent fuzzy matches
3. **Batch operations**: Optimize for multiple sequential searches
4. **Custom scoring**: Allow user-defined score combination functions
5. **Multi-field boolean queries**: Support complex AND/OR queries

## Examples & Use Cases

### Finding Papers by Topic with Date Constraints

```python
# Recent AI ethics papers
advanced_search(
    "artificial intelligence ethics",
    search_mode="hybrid",
    date_from=2020,
    item_type="journalArticle",
    n_results=25
)
```

### Finding Papers by Partial Author Name

```python
# All papers by anyone named "Smith" from last 5 years
search_by_fuzzy_author(
    "Smith",
    date_from=2019,
    n_results=50
)
```

### Finding Papers with Title Keywords

```python
# Papers with "privacy" and "surveillance" in title
advanced_search(
    "privacy surveillance",
    search_mode="metadata",
    fuzzy_threshold=70,
    title="privacy surveillance"
)
```

### Combining Multiple Filters

```python
# Recent journal articles by specific author on specific topic
advanced_search(
    "platform regulation",
    author="Suzor",
    date_from=2020,
    item_type="journalArticle",
    search_mode="hybrid"
)
```

## Troubleshooting

### Not Finding Expected Results?

1. **Lower fuzzy threshold**: Try `fuzzy_threshold=50` for more lenient matching
2. **Try different search modes**:
   - Use "metadata" for exact terminology
   - Use "semantic" for conceptual searches
3. **Check date filters**: Remove date filters if papers might be older
4. **Check item type**: Remove `item_type` filter to include all types

### Too Many Irrelevant Results?

1. **Raise fuzzy threshold**: Try `fuzzy_threshold=80` for stricter matching
2. **Add more filters**: Combine author, date, and type filters
3. **Adjust hybrid weights**: Increase `semantic_weight` to favor relevance

### Slow Searches?

1. **Use semantic mode**: Much faster than metadata scanning
2. **Add filters early**: Reduce items scanned with date/type filters
3. **Reduce n_results**: Request fewer results
4. **Use exact match tools**: DOI/citation key lookups are instant
