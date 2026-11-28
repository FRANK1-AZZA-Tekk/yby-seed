---
name: "yby-firmware-safe"
description: "Guia a escrita e atualização de firmware restrita a dispositivos previamente cadastrados e validados pelo usuário (regra S3 da constituição 1.1.0), respeitando a trava do MVP (Princípio V)."
compatibility: "YBY SEED — Constituição 1.1.0 (.specify/memory/constitution.md, Princípio V e S1–S4)"
metadata:
  author: "yby-seed"
  constitution_version: "1.1.0"
  spec: "specs/001-os-checklist-offline/spec.md"
  layer: "camada-6"
---

## Objetivo

Definir o fluxo obrigatório de segurança para qualquer operação de escrita, flash ou atualização de firmware em hardware no ecossistema YBY SEED, assegurando conformidade estrita com a regra **S3** (firmware somente em dispositivo cadastrado), em conjunto com **S1**, **S2**, **S4** e os Princípios **I**, **III** e **V** da constituição `1.1.0` em `.specify/memory/constitution.md`.

## Contexto

**Trava de escopo do MVP (Princípio V e `FR-013`)**: esta skill **não habilita firmware no MVP**. Conforme `.specify/memory/constitution.md` (`1.1.0`) e `specs/001-os-checklist-offline/spec.md` (`FR-013`), firmware e wearables permanecem fora do escopo atual até a validação completa do MVP em dispositivos reais (`A-Chrome` e `I-Safari`) e aprovação explícita de abertura de escopo pelo mantenedor. A regra `S3` funciona como pré-condição obrigatória para quando firmware existir.

Use esta skill quando:

- Revisar ou projetar contratos, scripts ou ferramentas futuras (pós-MVP) que façam gravação, flash ou atualização de firmware em hardware.
- Auditar se uma proposta envolvendo dispositivos físicos cumpre `S3`, `S1`, `S2` e `S4`.
- Executar, após liberação formal do escopo pós-MVP, uma gravação de firmware em dispositivo previamente cadastrado.

Não use esta skill para:

- Adicionar código de firmware, drivers de gravação ou dependências de hardware em camadas do MVP `001-os-checklist-offline`.
- Cadastrar dispositivos automaticamente por detecção de porta serial, USB, Bluetooth ou inferência do agente.

## Passos

1. **Verificar a trava de escopo do MVP (Princípio `V`, `FR-013`)**
   - Confirmar se a operação está autorizada fora da trava do MVP atual.
   - Se o escopo vigente ainda for o MVP de ordens de serviço offline, **recusar imediatamente** qualquer escrita ou habilitação de firmware e registrar a recusa na auditoria.

2. **Validar cadastro prévio e identidade do dispositivo (`S3`)**
   - Consultar o registro local de dispositivos previamente cadastrados e validados pelo usuário.
   - Comparar o identificador físico lido do dispositivo conectado (por exemplo, número de série ou identificador de hardware) com o identificador cadastrado.
   - Se o dispositivo estiver fora do cadastro, não estiver marcado como validado pelo usuário ou apresentar identificador divergente, **recusar imediatamente**.
   - Nunca cadastrar um dispositivo automaticamente por inferência; o cadastro prévio é uma ação separada e explícita do usuário.

3. **Verificar integridade do artefato e versões (`S3`, `S4`)**
   - Calcular localmente o hash criptográfico (`sha256`) do artefato de firmware antes de qualquer gravação.
   - Ler a versão atual instalada no dispositivo e conferir a versão de destino do artefato.
   - Garantir que o artefato, os argumentos de comando e os logs não contenham nem exponham segredos, credenciais ou chaves privadas (`S4`).

4. **Obter confirmação humana explícita para cada gravação (`S1`, `S3`)**
   - Mesmo para um dispositivo já cadastrado e validado, solicitar confirmação explícita do mantenedor **na sessão atual** para esta gravação específica.
   - O pedido de confirmação deve exibir claramente:
     - Identificador cadastrado do dispositivo.
     - Versão atual instalada.
     - Versão de destino.
     - Caminho do artefato e hash `sha256`.
   - Silêncio, aprovação de outra gravação ou instrução genérica não autorizam a escrita. Em caso de recusa, nada é gravado.

5. **Gravar auditoria local antes de escrever no hardware (`S2`, `S3`, `S4`)**
   - Apensar 1 linha em UTC no arquivo local somente de acréscimo de auditoria **antes** de executar a gravação, contendo: identificador do dispositivo, versão antes, versão de destino, hash `sha256` do artefato, confirmação recebida (`sim` ou `não`) e resultado (`sucesso`, `falha` ou `recusa`).
   - Se o registro de auditoria não puder ser gravado, **bloquear** a operação de firmware (fail-closed, `S2`).
   - Garantir ausência absoluta de valores de segredo no registro (`S4`).

6. **Executar gravação e confirmar versão pós-escrita (`Princípio III`, `S2`, `S3`)**
   - Executar a gravação somente após confirmação explícita e registro de auditoria persistido.
   - Ao término, reler a versão diretamente do dispositivo para confirmar a persistência real (sem confirmação otimista) e apensar o resultado final na auditoria local com a versão efetiva após a gravação.

## Critérios de aceite

- Nenhuma operação de firmware é habilitada ou executada enquanto vigorar a trava de escopo do MVP (Princípio `V` e `FR-013`).
- Nenhum dispositivo fora do cadastro, não validado ou com identificador divergente recebe gravação (`S3`).
- Nenhum cadastro de dispositivo ocorre automaticamente por inferência (`S3`).
- Toda gravação em dispositivo cadastrado é precedida por confirmação humana explícita na sessão atual mostrando identificador cadastrado, versão atual, versão de destino e hash do artefato (`S1`, `S3`).
- Toda tentativa (sucesso, falha ou recusa) gera registro local append-only em UTC com identificador do dispositivo, versões antes/depois, hash do artefato, confirmação e resultado; falha ao gravar o log impede a escrita (`S2`, `S3`).
- Nenhum segredo ou credencial é armazenado no repositório, enviado à nuvem ou exposto nos registros de auditoria (`S4`).

## Exemplos

### Exemplo 1: Recusa automática de dispositivo não cadastrado (`S3`)

**Cenário**: em uma fase pós-MVP autorizada, o agente recebe pedido para atualizar firmware na porta `/dev/ttyUSB0`, cujo hardware reporta `dev-serial-9981`, ausente do cadastro local validado.

1. A checagem de cadastro verifica que `dev-serial-9981` não consta na lista de dispositivos validados pelo usuário.
2. O agente **recusa** a gravação, não realiza cadastro automático por inferência e não executa nenhum comando de flash.
3. A auditoria local append-only em UTC registra a recusa:
   `{"ts":"2026-11-28T14:00:00Z","action":"firmware.flash","device_id":"dev-serial-9981","version_before":"unknown","version_after":"1.2.0","artifact_sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","confirmed":false,"result":"refused","reason":"device_not_registered"}`
4. O agente informa o bloqueio de `S3` e orienta o usuário a cadastrar e validar o dispositivo manualmente antes de nova tentativa.

### Exemplo 2: Fluxo pós-MVP aprovado em dispositivo cadastrado (`S1`, `S2`, `S3`, `S4`)

**Cenário**: após encerramento formal do MVP e validação manual do dispositivo `twatch-lab-01`, o mantenedor solicita atualizar o firmware de `1.1.0` para `1.2.0`.

1. **Verificação de cadastro**: `twatch-lab-01` existe no cadastro local, está marcado como validado pelo usuário e o identificador lido no hardware confere exatamente.
2. **Integridade**: o artefato local `firmware-1.2.0.bin` tem hash `sha256` calculado (`9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08`) e nenhum segredo nos parâmetros.
3. **Pedido de confirmação humana (`S1` + `S3`)**:
   - Dispositivo cadastrado: `twatch-lab-01`
   - Versão atual: `1.1.0`
   - Versão de destino: `1.2.0`
   - Artefato e hash: `firmware-1.2.0.bin` (`sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08`)
4. **Auditoria prévia (`S2`) e gravação**: somente após resposta afirmativa explícita na sessão atual, a tentativa confirmada é gravada em auditoria UTC; o flash é executado; a versão é relida do hardware (`1.2.0`) e o desfecho `result:"success"` é apensado na auditoria local.
