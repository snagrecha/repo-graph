from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from repo_lens.graph.schema import Edge, Node


class NodeResponse(BaseModel):
    id: str
    type: str
    name: str
    file_path: str
    start_line: int | None
    end_line: int | None
    language: str | None
    metadata: dict[str, Any]


class EdgeResponse(BaseModel):
    source_id: str
    target_id: str
    type: str
    metadata: dict[str, Any]


class GraphResponse(BaseModel):
    nodes: list[NodeResponse]
    edges: list[EdgeResponse]
    node_count: int
    edge_count: int


class NodeDetailResponse(BaseModel):
    node: NodeResponse
    incoming: list[EdgeResponse]
    outgoing: list[EdgeResponse]


class BlastRadiusResponse(BaseModel):
    node_id: str
    upstream: list[NodeResponse]
    downstream: list[NodeResponse]


def serialize_node(node: Node) -> NodeResponse:
    return NodeResponse(
        id=node.id,
        type=node.type.value,
        name=node.name,
        file_path=node.file_path,
        start_line=node.start_line,
        end_line=node.end_line,
        language=node.language,
        metadata=node.metadata,
    )


def serialize_edge(edge: Edge) -> EdgeResponse:
    return EdgeResponse(
        source_id=edge.source_id,
        target_id=edge.target_id,
        type=edge.type.value,
        metadata=edge.metadata,
    )
