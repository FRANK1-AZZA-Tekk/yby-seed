"""Testes da memória local SQLite + FTS5."""

from src.yby.memoria.sqlite_memoria import MemoriaSQLite


def test_salva_e_busca_fato(banco) -> None:
    memoria = MemoriaSQLite(banco)
    memoria.salvar("O usuário prefere soluções locais e de baixo custo.")

    resultados = memoria.buscar("baixo custo")

    assert len(resultados) == 1
    assert "baixo custo" in resultados[0]


def test_busca_apos_exclusao_nao_retorna_fato(banco) -> None:
    memoria = MemoriaSQLite(banco)
    memoria_id = memoria.salvar("preferência por baixo custo")

    banco.conexao.execute("DELETE FROM memorias WHERE id = ?", (memoria_id,))
    banco.conexao.commit()

    assert memoria.buscar("baixo custo") == []


def test_busca_apos_atualizacao_usa_texto_novo(banco) -> None:
    memoria = MemoriaSQLite(banco)
    memoria_id = memoria.salvar("usa modelos na nuvem")

    banco.conexao.execute(
        "UPDATE memorias SET conteudo = ? WHERE id = ?",
        ("usa modelos locais", memoria_id),
    )
    banco.conexao.commit()

    assert memoria.buscar("nuvem") == []
    assert len(memoria.buscar("locais")) == 1


def test_reindexar_repara_memorias_antigas(banco) -> None:
    banco.conexao.execute("DROP TRIGGER memorias_ai")
    banco.conexao.execute(
        "INSERT INTO memorias (conteudo, criado_em) VALUES (?, ?)",
        ("fato legado sem indice", "2026-10-19T00:00:00+00:00"),
    )
    banco.conexao.commit()

    memoria = MemoriaSQLite(banco)
    assert memoria.buscar("legado") == []

    banco.reindexar_memorias()
    banco.conexao.commit()

    assert len(memoria.buscar("legado")) == 1
