"""Wiki domain types and enums."""

from enum import StrEnum


class WikiFolder(StrEnum):
    RAW = "raw"
    INBOX = "inbox"
    ENTITIES = "entities"
    CONCEPTS = "concepts"
    SUMMARIES = "summaries"
    META = "meta"


class WikiPageStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"


VALID_FOLDERS = frozenset(f.value for f in WikiFolder)
