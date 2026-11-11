"""
AST Chunker — Fatiamento de código por sintaxe.

tree_sitter é opcional: sem a dep, usa fallback por linhas.
Sem instância global no import.
"""

from __future__ import annotations

import logging
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ASTChunker:
    """Fatiamento de código por AST (Árvore de Sintaxe Abstrata)."""

    def __init__(self, language: str = "python"):
        self.language = language
        self.parser = None
        self._tree_sitter_ready = False

        try:
            import tree_sitter_python as tspython
            from tree_sitter import Parser

            self.parser = Parser()
            if language == "python":
                self.parser.set_language(tspython.language())
                self._tree_sitter_ready = True
            else:
                logger.warning("Linguagem não suportada via tree-sitter: %s", language)
        except ImportError:
            logger.warning(
                "tree_sitter/tree_sitter_python ausentes — usando chunking por linhas."
            )

    def chunk(self, code: str, max_tokens: int = 512) -> list[dict[str, Any]]:
        logger.info("🔍 Fatiando código (%s chars)...", len(code))
        if self._tree_sitter_ready and self.parser is not None:
            return self._chunk_ast(code, max_tokens)
        return self._chunk_lines(code, max_tokens)

    def _chunk_ast(self, code: str, max_tokens: int) -> list[dict[str, Any]]:
        assert self.parser is not None
        tree = self.parser.parse(bytes(code, "utf8"))
        chunks: list[dict[str, Any]] = []

        for node in tree.root_node.children:
            if node.type in ["function_definition", "class_definition", "module"]:
                chunk_code = code[node.start_byte : node.end_byte]
                token_count = len(chunk_code.split())
                if token_count <= max_tokens:
                    chunks.append(
                        {
                            "type": node.type,
                            "code": chunk_code,
                            "start_line": node.start_point[0] + 1,
                            "end_line": node.end_point[0] + 1,
                            "token_count": token_count,
                        }
                    )
                else:
                    # divide por linhas internas se exceder
                    chunks.extend(self._chunk_lines(chunk_code, max_tokens))

        if not chunks:
            chunks = self._chunk_lines(code, max_tokens)
        return chunks

    def _chunk_lines(self, code: str, max_tokens: int) -> list[dict[str, Any]]:
        lines = code.splitlines(keepends=True)
        chunks: list[dict[str, Any]] = []
        buf: list[str] = []
        start_line = 1

        for idx, line in enumerate(lines, start=1):
            trial = "".join(buf + [line])
            if buf and len(trial.split()) > max_tokens:
                text = "".join(buf)
                chunks.append(
                    {
                        "type": "lines",
                        "code": text,
                        "start_line": start_line,
                        "end_line": idx - 1,
                        "token_count": len(text.split()),
                    }
                )
                buf = [line]
                start_line = idx
            else:
                buf.append(line)

        if buf:
            text = "".join(buf)
            chunks.append(
                {
                    "type": "lines",
                    "code": text,
                    "start_line": start_line,
                    "end_line": start_line + len(buf) - 1,
                    "token_count": len(text.split()),
                }
            )
        return chunks


def get_ast_chunker(language: str = "python") -> ASTChunker:
    """Factory lazy — evita side-effect no import do módulo."""
    return ASTChunker(language=language)
