# Citation Corruption Report

**Date**: 2024-12-04
**Corpus**: 5,343 unique items from 194,829 chunks
**Corrupted items**: 52 (0.97%)

## Issue Categories

### Category A: Severely Corrupted (>10,000 chars) - RECOMMEND DELETE & RE-VECTORIZE
These citations contain massive amounts of garbage data (likely PDF extraction artifacts). The original source material is fine; only the ChromaDB metadata is corrupt.

| # | Key | Title | Length | Decision |
|---|-----|-------|--------|----------|
| 1 | 5SQ494NX | Rule By Example: Harnessing Logical Rules for Explainable Hate Speech Detection | 39,473 | DELETE |
| 2 | IMRA7UHU | A robust framework for real-time data analysis, predictive modeling... | 34,527 | DELETE |
| 3 | TNR3LL68 | 'The personal is political': sexual misconduct allegations... | 30,607 | DELETE |
| 4 | PKF2V7F4 | The Islamic State | 30,595 | DELETE |
| 5 | BP7SDJEX | Google Australia Pty Ltd Digital Platforms Inquiry Submission... | 29,360 | DELETE |
| 6 | JSERJQ4F | No Vengeance for 'Revenge Porn' Victims... | 24,470 | DELETE |
| 7 | 3F52NBK5 | Words of Wisdom: Representational Harms in Learning From AI Communication | 21,269 | DELETE |
| 8 | 6NI9B8G2 | Media representations of violence against women and their children | 20,391 | DELETE |
| 9 | R2USMLM3 | Analyzing Hate Speech with Incel-Hunters' Critiques | 14,687 | DELETE |
| 10 | 3FAKWIMY | 'HOTTEST 100 WOMEN' Cross-platform Discursive Activism... | 14,084 | DELETE |
| 11 | 9GK788C7 | ACCC Digital Platforms Inquiry: Response to the ACCC's Preliminary Report | 13,599 | DELETE |
| 12 | HRGYY7F9 | Making Sense of Facebook's Content Moderation | 12,181 | DELETE |
| 13 | IRZE2UEG | On Frogs, Monkeys, and Execution Memes | 11,918 | DELETE |
| 14 | ASWUMN3H | Power/Knowledge: Selected Interviews and Other Writings | 10,980 | DELETE |
| 15 | YNMAD9RF | LLM-Mod: Can Large Language Models Assist Content Moderation? | 10,784 | DELETE |
| 16 | LKZNNZJ4 | Examining Report Content and Social Categorization... | 10,192 | DELETE |

### Category B: Moderately Corrupted (500-10,000 chars) - RECOMMEND DELETE & RE-VECTORIZE
Still too long for a citation but less severe.

| # | Key | Title | Length | Decision |
|---|-----|-------|--------|----------|
| 17 | YTUC5MQH | Goffman | 9,274 | DELETE |
| 18 | HSBD2CDR | Meta-Fair: AI-Assisted Fairness Testing of Large Language Models | 7,871 | DELETE |
| 19 | 34GP77T8 | Free Speech and Hate Speech | 7,698 | DELETE |
| 20 | LY25H8KD | Australia | 7,518 | DELETE |
| 21 | 9UGURHJ8 | Who's in and who's out? A case study of multimodal CLIP-filtering | 6,906 | DELETE |
| 22 | CLIPI88Q | Doing and denying sexism: online responses to a NZ feminist campaign | 6,713 | DELETE |
| 23 | T5YGIJFI | Let's Meet Halfway: Sharing New Responsibilities in a Digital Age | 5,122 | DELETE |
| 24 | VKRG8G6W | To predict and serve? | 4,704 | DELETE |
| 25 | A3ALUFSW | Correcting JSON String Quoting | 2,844 | DELETE |
| 26 | W3Q7ZDW2 | Social Media and the Decision to Participate in Political Protest | 595 | DELETE |
| 27 | 2Y7IAAUU | Corrigendum to the Artificial Intelligence Act Position | 537 | DELETE |
| 28 | KSM54KKU | "So what if ChatGPT wrote it?" Multidisciplinary perspectives... | 529 | DELETE |

### Category C: Whitespace Only (normal length) - RECOMMEND RE-VECTORIZE
These have excessive whitespace but citation length is normal. The LLM likely added spurious newlines.

| # | Key | Title | Issue | Decision |
|---|-----|-------|-------|----------|
| 29 | 6LHWJ9CH | Class-based Prediction Errors to Detect Hate Speech | whitespace | RE-VECTORIZE |
| 30 | HA7HKFI7 | 'He never hit me #WhyIStayed': countering the U.S. domestic violence | whitespace | RE-VECTORIZE |
| 31 | ZUNJRYZL | Framing Deadly Domestic Violence | whitespace | RE-VECTORIZE |
| 32 | 9HMHEZBF | Public survivors: The burdens and possibilities of speaking | whitespace | RE-VECTORIZE |
| 33 | 6VJ4L6WB | Is ChatGPT better than Human Annotators? | whitespace | RE-VECTORIZE |
| 34 | UN8K2JLN | Reporting Hate Comments | whitespace | RE-VECTORIZE |
| 35 | ZVB49WZD | The "Arbiters of What Our Voters See" | whitespace | RE-VECTORIZE |
| 36 | KHKVRV6S | Networked Misogyny on TikTok | whitespace | RE-VECTORIZE |
| 37 | MUWPD3RN | Evidencing domestic violence | whitespace | RE-VECTORIZE |
| 38 | 75CA3UU3 | 'But I've never sent them any personal details...' | whitespace | RE-VECTORIZE |
| 39 | JLAJ49HW | Racial categories in machine learning | whitespace | RE-VECTORIZE |
| 40 | RTD26DMC | News Media Representation of Intimate Partner Violence | whitespace | RE-VECTORIZE |
| 41 | ISU8R5TH | The civilizing process in London's Old Bailey | whitespace | RE-VECTORIZE |
| 42 | 9K2B2XZM | The right to privacy in the digital age | whitespace | RE-VECTORIZE |
| 43 | LE8ZBHCM | The Heteronormative Male Gaze | whitespace | RE-VECTORIZE |
| 44 | JKUHKERA | From Scalability to Subsidiarity in Addressing Online Harm | whitespace | RE-VECTORIZE |
| 45 | GZZL84RS | Recovering the feminine other | whitespace | RE-VECTORIZE |
| 46 | TRP9T72A | Videotape and Vibrators: An Industry History | whitespace | RE-VECTORIZE |
| 47 | EXNSNNQG | John Stuart Mill's Harm Principle and Free Speech | whitespace | RE-VECTORIZE |
| 48 | CWGTE9GP | The Ideal of Impartiality and the Civic Public | whitespace | RE-VECTORIZE |
| 49 | YFLHJKV4 | Canada's Proposed Artificial Intelligence and Data Act (AIDA) | whitespace | RE-VECTORIZE |
| 50 | S3BEDXNL | Classification—Content Regulation and Convergent Media | whitespace | RE-VECTORIZE |
| 51 | 6GFVFA69 | Amazon's Antitrust Paradox | whitespace | RE-VECTORIZE |
| 52 | LDVK66MM | Of Systems Thinking and Straw Men | whitespace | RE-VECTORIZE |

## Summary

| Category | Count | Recommendation |
|----------|-------|----------------|
| Severely corrupted (>10k chars) | 16 | Delete from ChromaDB, re-vectorize |
| Moderately corrupted (500-10k) | 12 | Delete from ChromaDB, re-vectorize |
| Whitespace only | 24 | Re-vectorize (or clean in-place) |
| **Total** | **52** | |

## Root Cause Analysis

The corruption appears to come from two sources:

1. **PDF extraction artifacts**: Some PDFs contain hidden text, repeated headers/footers, or other garbage that gets included in the text sent to the LLM for citation generation.

2. **LLM hallucination/elaboration**: The LLM sometimes elaborates beyond generating a citation, adding commentary, metadata explanations, or repeated content.

## Recommended Actions

1. **Immediate**: Delete all 52 items from ChromaDB and trigger re-vectorization
2. **Pipeline fix**: Add citation validation BEFORE accepting LLM-generated citations:
   - Reject citations > 500 characters
   - Reject citations with 10+ consecutive whitespace characters
   - Log rejections for manual review
