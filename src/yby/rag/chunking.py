"""Chunking LlamaIndex com preservação básica de estrutura."""

from __future__ import annotations

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import BaseNode

from src.yby.rag.config import RagConfig


def _splitter(config: RagConfig) -> SentenceSplitter:
    return SentenceSplitter(
        chunk_size=config.chunk_size_tokens,
        chunk_overlap=config.chunk_overlap_tokens,
        paragraph_separator="\n\n",
    )


def build_nodes(
    text: str,
    *,
    doc_type: str,
    config: RagConfig,
    base_metadata: dict,
) -> list[BaseNode]:
    document = Document(text=text, metadata=dict(base_metadata))
    splitter = _splitter(config)

    if doc_type == "md":
        header_nodes = MarkdownNodeParser().get_nodes_from_documents([document])
        refined: list[BaseNode] = []
        for node in header_nodes:
            content = node.get_content(metadata_mode="none")
            meta = dict(node.metadata or base_metadata)
            refined.extend(
                splitter.get_nodes_from_documents([Document(text=content, metadata=meta)])
            )
        if refined:
            return refined

    return splitter.get_nodes_from_documents([document])


def attach_chunk_positions(
    nodes: list[BaseNode],
    *,
    content_hash: str,
) -> list[BaseNode]:
    total = len(nodes)
    for index, node in enumerate(nodes):
        node.metadata["chunk_index"] = index
        node.metadata["chunk_total"] = total
        node.metadata["content_hash"] = content_hash
        if isinstance(node.metadata.get("tags"), list):
            from src.yby.rag.loaders import tags_to_chroma

            node.metadata["tags"] = tags_to_chroma(node.metadata["tags"])
    return nodes