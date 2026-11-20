"""CLI: yby painel — sobe uvicorn em 127.0.0.1."""

from __future__ import annotations

import click


@click.command("painel")
@click.option("--host", default="127.0.0.1", show_default=True, help="Só loopback.")
@click.option("--port", default=8765, show_default=True, type=int)
@click.option(
    "--reload",
    is_flag=True,
    default=False,
    help="Recarrega ao editar (dev).",
)
def painel_cmd(host: str, port: int, reload: bool) -> None:
    """Painel local de consulta (somente leitura). Exige YBY_PAINEL_TOKEN."""

    from src.painel.app import assert_loopback_host, create_app
    from src.painel.auth import painel_token_from_env

    bind = assert_loopback_host(host)
    if not painel_token_from_env():
        raise click.ClickException(
            "Defina YBY_PAINEL_TOKEN no ambiente (.env) antes de subir o painel."
        )

    import uvicorn

    # create_app lido por string path quando reload; app object quando não
    if reload:
        uvicorn.run(
            "src.painel.app:create_app",
            factory=True,
            host=bind,
            port=port,
            reload=True,
        )
    else:
        uvicorn.run(create_app(), host=bind, port=port)
