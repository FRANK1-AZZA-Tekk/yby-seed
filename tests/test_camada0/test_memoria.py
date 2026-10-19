"""Testes da memória local SQLite + FTS5."""

from src.yby.memoria.sqlite_memoria import MemoriaSQLite


def test_salva_e_busca_fato(banco) -> None:
    memoria = MemoriaSQLite(banco)
    memoria.salvar("O usuário prefere soluções locais e de baixo custo.")

    resultados = memoria.buscar("baixo custo")

    assert len(resultados) == 1
    assert "baixo custo" in resultados[0]
