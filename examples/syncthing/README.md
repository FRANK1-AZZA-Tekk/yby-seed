# Syncthing — vault Obsidian (exemplo)

O YBY **não** embute o Syncthing. Ele só lê/grava `YBY_VAULT_PATH`. O Syncthing sincroniza essa pasta entre o notebook e o PC Hub.

## Passos (sem segredos)

1. Instale o Syncthing no hub e no notebook (`syncthing` no Ubuntu).
2. Crie a pasta do vault no hub, por exemplo `~/Vaults/yby`.
3. No Syncthing do hub: **Add Folder** → path `~/Vaults/yby` → Folder ID `yby-vault` (ou outro id estável).
4. Compartilhe com o device do notebook (GUI do Syncthing → Share).
5. No notebook: aceite a pasta e aponte para o mesmo path local do Obsidian.
6. No `.env` do hub (não versionado):

```bash
YBY_VAULT_PATH=/home/SEU_USUARIO/Vaults/yby
```

## Exemplo de pasta

Veja `folder-config.example.xml` — é um **esqueleto** de `<folder>` do Syncthing. Não copie API keys, TLS keys nem `device id` reais para o git. Gere os IDs na UI do Syncthing.

## O que não fazer

- Não coloque `.stfolder` com dados privados no repositório.
- Não versione o `config.xml` completo do Syncthing (tem chaves).
- O hub keepalive (`yby hub` / systemd) **não** inicia o Syncthing; rode o Syncthing como serviço separado (`systemctl --user enable syncthing`).
