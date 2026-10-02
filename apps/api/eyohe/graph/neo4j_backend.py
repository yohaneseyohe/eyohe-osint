"""Optional Neo4j mirror of the case graph (GRAPH_BACKEND=neo4j). PostgreSQL remains the system of
record; this adapter syncs entities/relationships for Cypher exploration and is never required."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.core.config import get_settings
from eyohe.core.errors import ConfigurationError
from eyohe.models.entities import Entity, Relationship


class Neo4jGraphBackend:
    def __init__(self) -> None:
        try:
            from neo4j import AsyncGraphDatabase
        except ImportError as exc:
            raise ConfigurationError("neo4j driver not installed (uv sync --extra neo4j)") from exc
        s = get_settings()
        if not s.neo4j_password:
            raise ConfigurationError("NEO4J_PASSWORD is not set")
        self._driver = AsyncGraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))

    async def ping(self) -> bool:
        async with self._driver.session() as sess:
            rec = await (await sess.run("RETURN 1 AS ok")).single()
            return bool(rec and rec["ok"] == 1)

    async def sync_case(self, db: AsyncSession, case_id: uuid.UUID) -> dict[str, Any]:
        ents = list((await db.execute(select(Entity).where(Entity.case_id == case_id))).scalars())
        rels = list((await db.execute(select(Relationship).where(Relationship.case_id == case_id))).scalars())
        async with self._driver.session() as sess:
            await sess.run("CREATE CONSTRAINT eyohe_entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE")
            for e in ents:
                await sess.run(
                    "MERGE (n:Entity {id: $id}) SET n.display_id=$d, n.type=$t, n.value=$v, n.label=$l, "
                    "n.confidence=$c, n.case=$case",
                    id=str(e.id),
                    d=e.display_id,
                    t=e.type,
                    v=e.value,
                    l=e.label,
                    c=e.confidence,
                    case=str(case_id),
                )
            for r in rels:
                await sess.run(
                    "MATCH (a:Entity {id: $a}), (b:Entity {id: $b}) MERGE (a)-[x:REL {id: $id}]->(b) "
                    "SET x.type=$t, x.confidence=$c, x.display_id=$d, x.review=$rv",
                    a=str(r.source_entity_id),
                    b=str(r.target_entity_id),
                    id=str(r.id),
                    t=r.type,
                    c=r.confidence,
                    d=r.display_id,
                    rv=r.review_state,
                )
        return {"entities": len(ents), "relationships": len(rels)}

    async def close(self) -> None:
        await self._driver.close()
