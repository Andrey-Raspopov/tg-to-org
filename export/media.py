from dataclasses import dataclass
from typing import Any


@dataclass
class Media:
    """Class for media row in db"""

    name: str
    mime_type: str
    size: int
    thumbnail_id: int
    local_id: int
    volume_id: int
    secret: str
    file_reference: bytes
    access_hash: int
    id: int
    type: str
    extra: Any

    def __init__(
        self,
        name=None,
        mime_type=None,
        size=None,
        thumbnail_id=None,
        local_id=None,
        volume_id=None,
        secret=None,
        file_reference=None,
        access_hash=None,
        id=None,
        type=None,
        extra=None,
    ):
        self.name = name
        self.mime_type = mime_type
        self.size = size
        self.thumbnail_id = thumbnail_id
        self.local_id = local_id
        self.volume_id = volume_id
        self.secret = secret
        self.file_reference = file_reference
        self.access_hash = access_hash
        self.id = id
        self.type = type
        self.extra = extra
