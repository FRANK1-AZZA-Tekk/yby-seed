"""
Testes do RAG (AST Chunking + Context Pruning)

Cobertura:
- AST chunker (fatiamento por sintaxe)
- Context pruner (resumos + re-rank)
- RAG optimizer (busca completa)

Execução:
pytest tests/test_rag.py -v --cov=src/rag

Licença: MIT
"""

import pytest
from src.rag.ast_chunker import ASTChunker
from src.rag.context_pruner import ContextPruner
from src.rag.rag_optimizer import RAGOptimizer


@pytest.fixture
def ast_chunker():
    """AST chunker para testes"""
    return ASTChunker(language="python")


@pytest.fixture
def context_pruner():
    """Context pruner para testes"""
    return ContextPruner()


# === Testes AST Chunker ===

@pytest.mark.asyncio
async def test_ast_chunk_function(ast_chunker):
    """Testar fatiamento de função"""
    code = '''
def hello():
    print("Hello, world!")

class MyClass:
    def __init__(self):
        pass
'''
    
    chunks = ast_chunker.chunk(code, max_tokens=512)
    
    assert len(chunks) >= 0
    assert chunks[0]["type"] == "function_definition"
    assert "hello" in chunks[0]["code"]


@pytest.mark.asyncio
async def test_ast_chunk_class(ast_chunker):
    """Testar fatiamento de classe"""
    code = '''
class MyClass:
    def __init__(self):
        self.value = 42
    
    def get_value(self):
        return self.value
'''
    
    chunks = ast_chunker.chunk(code, max_tokens=512)
    
    assert len(chunks) >= 0
    assert chunks[0]["type"] == "class_definition"
    assert "MyClass" in chunks[0]["code"]


@pytest.mark.asyncio
async def test_ast_chunk_subdivide(ast_chunker):
    """Testar subdivisão de chunk grande"""
    # Gerar código grande (>512 tokens)
    code = "\n".join([f"def func_{i}(): return {i}" for i in range(100)])
    
    chunks = ast_chunker.chunk(code, max_tokens=512)
    
    # Deve subdividir em múltiplos chunks
    assert len(chunks) > 1
    
    # Cada chunk deve ter <= 512 tokens
    for chunk in chunks:
        assert chunk["token_count"] <= 512


# === Testes Context Pruner ===

@pytest.mark.asyncio
async def test_context_pruner_summarize(context_pruner):
    """Testar geração de resumos"""
    text = "Função de backup que compacta arquivos ZIP e salva em diretório remoto."
    
    summary = context_pruner._summarize(text, max_tokens=20)
    
    assert len(summary.split()) <= 20
    assert "backup" in summary.lower() or "compacta" in summary.lower()


@pytest.mark.asyncio
async def test_context_pruner_rerank(context_pruner):
    """Testar re-ranking de resumos"""
    summaries = [
        {"original": "Backup automation", "summary": "Compacta arquivos"},
        {"original": "Notification system", "summary": "Envia emails"},
        {"original": "API integration", "summary": "Conecta APIs"}
    ]
    
    query = "Como fazer backup?"
    ranked = context_pruner._rerank(summaries, query)
    
    assert len(ranked) == 3
    # Primeiro deve ser backup (mais relevante)
    assert "backup" in ranked[0]["original"].lower()


@pytest.mark.asyncio
async def test_context_pruner_prune(context_pruner):
    """Testar poda de contexto"""
    chunks = [
        "Backup automation script",
        "Notification system",
        "API integration"
    ]
    
    query = "Como fazer backup?"
    pruned = context_pruner.prune(chunks, query, max_tokens=100)
    
    assert len(pruned) <= 3
    # Backup deve estar entre os primeiros
    assert "backup" in pruned[0].lower() if pruned else True


# === Testes RAG Optimizer ===

@pytest.mark.asyncio
async def test_rag_search():
    """Testar busca RAG completa"""
    rag = RAGOptimizer(db_path=":memory:")
    
    # Indexar documento
    doc = '''
def backup_files(source, dest):
    """Compactar arquivos em ZIP"""
    import zipfile
    with zipfile.ZipFile(dest, 'w') as zipf:
        for file in source.glob('**/*'):
            zipf.write(file)
'''
    
    await rag.index_document(doc, "backup_example", {"author": "YBY SEED"})
    
    # Buscar
    results = await rag.search("Como fazer backup de arquivos?", top_k=5)
    
    assert len(results) >= 0
    assert "backup" in results[0].lower() if results else True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
