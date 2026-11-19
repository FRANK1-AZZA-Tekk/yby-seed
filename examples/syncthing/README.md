# Syncthing — vault Obsidian (exemplo)

O YBY **não** embute o Syncthing. Ele só lê/grava `YBY_VAULT_PATH`. O Syncthing sincroniza essa pasta entre o notebook e o PC Hub.

**Decisão P #6 (fechada / A):** Syncthing como **serviço de usuário** (`systemctl --user`), na **mesma conta** que roda o YBY / `yby-hub`. Não instalar Syncthing de sistema neste guia.

## Passos (sem segredos)

1. Instale o Syncthing no hub e no notebook (`syncthing` no Ubuntu). **Não** rode instalação neste repositório/CI — só no hardware do Hub.
2. Crie a pasta do vault no hub, por exemplo `~/Vaults/yby`.
3. No Syncthing do hub: **Add Folder** → path `~/Vaults/yby` → Folder ID `yby-vault` (ou outro id estável).
4. Na pasta do vault, copie [`.stignore.example`](.stignore.example) para `.stignore` (ignora `.yby/`, caches e temporários).
5. Compartilhe com o device do notebook (GUI do Syncthing → Share).
6. No notebook: aceite a pasta e aponte para o mesmo path local do Obsidian.
7. No `.env` do hub (não versionado):

```bash
YBY_VAULT_PATH=/home/SEU_USUARIO/Vaults/yby
```

## Serviço de usuário (Hub)

```bash
# Após instalar o pacote syncthing (fora deste repo):
systemctl --user enable --now syncthing
# Login sem GUI (mesma regra do yby-hub):
loginctl enable-linger $USER
```

O hub keepalive (`yby hub` / systemd) **não** inicia o Syncthing; rode-o separado.

## Exemplo de pasta

- [`.stignore.example`](.stignore.example) — ignore mínimo (`.yby/`, caches, temps).
- [`folder-config.example.xml`](folder-config.example.xml) — esqueleto de `<folder>` (só vault).
- YAML espelho: [`docs/syncthing/vault-folder.example.yaml`](../../docs/syncthing/vault-folder.example.yaml).

Não copie API keys, TLS keys nem `device id` reais para o git. Gere os IDs na UI do Syncthing.

## O que não fazer

- Não coloque `.stfolder` com dados privados no repositório.
- Não versione o `config.xml` completo do Syncthing (tem chaves).
- Não sincronize o repositório `yby-seed` inteiro — **só** a pasta do vault.
- Não coloque `.env` / segredos dentro do vault sincronizado.
