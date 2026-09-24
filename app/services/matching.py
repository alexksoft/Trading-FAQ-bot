# app/services/matching.py
# Rule-based FAQ matching engine.
# NO NLP or AI is used here — pure string matching only.

import re
import logging
from app.models.faq import FaqConfig, FaqEntry
from app.models.message import MatchResult

logger = logging.getLogger(__name__)


def normalize(text: str) -> str:
    """
    Prepare text for matching:
    - lowercase
    - strip whitespace
    - collapse multiple spaces
    - remove surrounding punctuation
    """
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)          # "hello   world" -> "hello world"
    text = text.strip(".,!?;:'\"")             # remove leading/trailing punctuation
    return text


class MatchingEngine:
    """
    Matches an incoming message against all FAQ entries.
    Returns the best matching entry or None.
    """

    def __init__(self, config: FaqConfig):
        self.config = config
        logger.info(f"MatchingEngine ready with {len(config.entries)} entries")

    def match(self, text: str) -> MatchResult:
        """
        Try to find a matching FAQ entry for the given text.
        Returns a MatchResult with the best match, or matched=False if none found.
        """
        normalized_text = normalize(text)
        logger.debug(f"Matching: '{normalized_text}'")

        # Collect all entries that match
        candidates = []
        for entry in self.config.entries:
            if self._entry_matches(entry, normalized_text):
                candidates.append(entry)

        if not candidates:
            logger.debug("No match found")
            return MatchResult(entry_id=None, matched=False, response=None)

        # Pick the best candidate using tie-break rules:
        # 1. Highest priority number wins
        # 2. If tied, longest trigger wins (more specific)
        # 3. If still tied, first in declaration order wins
        best = self._pick_best(candidates, normalized_text)
        logger.debug(f"Matched entry: {best.id}")

        return MatchResult(entry_id=best.id, matched=True, response=best.response)

    def _entry_matches(self, entry: FaqEntry, normalized_text: str) -> bool:
        """Check if any trigger in this entry matches the text."""
        for trigger in entry.normalized_triggers:
            if entry.match_type == "exact":
                # The whole message must equal the trigger exactly
                if normalized_text == trigger:
                    return True
            else:
                # "contains": the trigger must appear as a substring
                # We check for word boundaries to avoid "rsi" matching "crisis"
                if _contains_phrase(normalized_text, trigger):
                    return True
        return False

    def _pick_best(self, candidates: list[FaqEntry], normalized_text: str) -> FaqEntry:
        """
        From a list of matching entries, pick the best one.
        Tie-break: priority (desc) → longest matching trigger (desc) → order (asc)
        """
        def sort_key(entry: FaqEntry):
            # Find the longest trigger that matched
            longest = max(
                (len(t) for t in entry.normalized_triggers
                 if _contains_phrase(normalized_text, t) or normalized_text == t),
                default=0
            )
            # Negate priority and longest so higher values sort first
            return (-entry.priority, -longest)

        candidates.sort(key=sort_key)
        return candidates[0]


def _contains_phrase(text: str, phrase: str) -> bool:
    """
    Check if 'phrase' appears in 'text' as a whole word/phrase.
    This prevents "rsi" from matching inside "crisis".
    """
    # Escape special regex characters in the phrase
    escaped = re.escape(phrase)
    # \b is a word boundary — works for single words
    # For multi-word phrases, check that the phrase is surrounded by
    # non-alphanumeric characters or is at the start/end
    pattern = r"(?<![a-z0-9])" + escaped + r"(?![a-z0-9])"
    return bool(re.search(pattern, text))
