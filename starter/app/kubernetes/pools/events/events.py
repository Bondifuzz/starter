from enum import Enum

from pydantic import BaseModel


class PoolEventType(str, Enum):
    creating = "bondifuzz.pools.creating"
    created = "bondifuzz.pools.created"
    updating = "bondifuzz.pools.updating"
    updated = "bondifuzz.pools.updated"
    deleting = "bondifuzz.pools.deleting"
    deleted = "bondifuzz.pools.deleted"
    node_added = "bondifuzz.pools.node-added"
    node_removed = "bondifuzz.pools.node-removed"


class PoolEvent(BaseModel):
    pool_id: str
    type: str


class PoolCreatingEvent(PoolEvent):
    type: str = "bondifuzz.pools.creating"


class PoolCreatedEvent(PoolEvent):
    type: str = "bondifuzz.pools.created"


class PoolUpdatingEvent(PoolEvent):
    type: str = "bondifuzz.pools.updating"


class PoolUpdatedEvent(PoolEvent):
    type: str = "bondifuzz.pools.updated"


class PoolDeletingEvent(PoolEvent):
    type: str = "bondifuzz.pools.deleting"


class PoolDeletedEvent(PoolEvent):
    type: str = "bondifuzz.pools.deleted"


class PoolNodeAddedEvent(PoolEvent):
    type: str = "bondifuzz.pools.node-added"
    node_name: str
    cpu: int
    ram: int


class PoolNodeRemovedEvent(PoolEvent):
    type: str = "bondifuzz.pools.node-removed"
    node_name: str
