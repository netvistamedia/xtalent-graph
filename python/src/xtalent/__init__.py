"""xTalent Graph — open, LLM-native talent protocol.

Public surface:
    XTalentCV, ProfileRoot, Status, Availability — from :mod:`xtalent.core`
    TalentPublisher, IPFSClient, InMemoryIPFS      — from :mod:`xtalent.publish`
    TalentSearchIndex, Embedder, VectorIndex       — from :mod:`xtalent.search`
"""

from xtalent.core import (
    CV_SCHEMA_ID,
    PROFILE_ROOT_SCHEMA_ID,
    Availability,
    ProfileRoot,
    Status,
    XTalentCV,
)
from xtalent.publish import (
    InMemoryIPFS,
    IPFSClient,
    PublishError,
    PublishRecord,
    TalentPublisher,
)
from xtalent.search import (
    DeterministicEmbedder,
    Embedder,
    GrokEmbedder,
    InMemoryVectorIndex,
    SearchFilters,
    SearchHit,
    TalentSearchIndex,
    VectorIndex,
)

__all__ = [
    "CV_SCHEMA_ID",
    "PROFILE_ROOT_SCHEMA_ID",
    "Availability",
    "DeterministicEmbedder",
    "Embedder",
    "GrokEmbedder",
    "IPFSClient",
    "InMemoryIPFS",
    "InMemoryVectorIndex",
    "ProfileRoot",
    "PublishError",
    "PublishRecord",
    "SearchFilters",
    "SearchHit",
    "Status",
    "TalentPublisher",
    "TalentSearchIndex",
    "VectorIndex",
    "XTalentCV",
]

__version__ = "0.1.0"
