"""CLI da Camada 0 do YBY SEED."""

from __future__ import annotations

import click

from .config import Config
from .core.auditoria import Auditoria
from .core.roteador import Roteador
from .db import Banco
from .memoria.sqlite_memoria import MemoriaSQLite
from .messages import PEDIDO_VAZIO, RESPOSTA_GERADA
from .models import Evento, Pedido


@click.group()
def cli() -> None:
    """YBY SEED — assistente local de programação em linguagem natural."""


@cli.command()
@click.argument("texto", nargs=-1, required=True)
def ask(texto: tuple[str, ...]) -> None:
    """Envia um pedido em linguagem natural ao YBY SEED."""

    pedido_texto = " ".join(texto).strip()

    if not pedido_texto:
        click.echo(PEDIDO_VAZIO)
        raise SystemExit(1)

    config = Config.carregar()
    config.garantir_diretorios()

    banco = Banco(config.db_path)
    auditoria = Auditoria(banco)
    roteador = Roteador(config)

    pedido = Pedido(texto=pedido_texto)
    pedido.id = banco.criar_pedido(pedido.texto, pedido.criado_em)

    auditoria.registrar(
        Evento(
            pedido_id=pedido.id,
            tipo="pedido_recebido",
            motivo="Entrada do usuário pela CLI",
            payload=pedido.texto,
        )
    )

    try:
        provedor = roteador.resolver_provedor()
        resposta = provedor.gerar(pedido.texto)
        roteador.validar_custo(resposta)
    except Exception as erro:
        auditoria.registrar(
            Evento(
                pedido_id=pedido.id,
                tipo="erro",
                motivo=str(erro),
                payload=pedido.texto,
            )
        )
        raise

    auditoria.registrar(
        Evento(
            pedido_id=pedido.id,
            tipo="resposta_gerada",
            provedor=resposta.provedor,
            modelo=resposta.modelo,
            motivo="Provedor padrão da Camada 0",
            custo_usd=resposta.custo_usd,
            payload=resposta.texto,
        )
    )

    click.echo(resposta.texto)
    click.echo(
        RESPOSTA_GERADA.format(modelo=resposta.modelo, provedor=resposta.provedor)
    )

    banco.fechar()


@cli.command()
def memoria() -> None:
    """Lista os eventos mais recentes da auditoria."""

    config = Config.carregar()
    banco = Banco(config.db_path)

    for evento in banco.listar_eventos():
        click.echo(
            f"#{evento['id']} [{evento['tipo']}] "
            f"{evento['provedor'] or '-'} / {evento['modelo'] or '-'} "
            f"US${evento['custo_usd']:.4f}"
        )

    banco.fechar()


if __name__ == "__main__":
    cli()
