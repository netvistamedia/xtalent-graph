"""xTalent Graph — open, LLM-native talent protocol.

Public surface:
    XTalentCV, ProfileRoot, Status, Availability — from :mod:`xtalent.core`
    TalentPublisher, IPFSClient, InMemoryIPFS      — from :mod:`xtalent.publish`
    TalentSearchIndex, Embedder, VectorIndex       — from :mod:`xtalent.search`
    generate_keypair, sign_profile_root,
    verify_profile_root, SignatureError             — from :mod:`xtalent.signing`
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
from xtalent.signing import (
    KeyPair,
    SignatureError,
    canonical_bytes,
    generate_keypair,
    is_signed,
    sign_profile_root,
    verify_profile_root,
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
    "KeyPair",
    "ProfileRoot",
    "PublishError",
    "PublishRecord",
    "SearchFilters",
    "SearchHit",
    "SignatureError",
    "Status",
    "TalentPublisher",
    "TalentSearchIndex",
    "VectorIndex",
    "XTalentCV",
    "canonical_bytes",
    "generate_keypair",
    "is_signed",
    "sign_profile_root",
    "verify_profile_root",
]

__version__ = "0.1.0"
