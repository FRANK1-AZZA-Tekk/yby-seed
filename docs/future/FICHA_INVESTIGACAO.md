# Ficha de investigação (wearable / rede / firmware)

> Template para registrar achados com rigor. **Fora do v1** — usar em spikes nos repositórios [YBY](https://github.com/FRANK1-AZZA-Tekk/YBY) / [FRANK_ZER0](https://github.com/FRANK1-AZZA-Tekk/FRANK_ZER0). Não confundir variantes de placa.

## Campos obrigatórios

| Campo | Conteúdo |
|---|---|
| **ID** | `YBY-INV-YYYYMMDD-###` |
| **Título** | Uma linha |
| **Tema** | Hardware / Firmware / UI / Rede / IA / Android / Segurança |
| **Componente** | Ex.: `T-Watch S3 Plus`, `yby hub`, `gateway` |
| **Fonte** | Nome da fonte |
| **Tipo de fonte** | Oficial / issue GitHub / fórum / artigo / medição própria |
| **URL** | Link completo |
| **Data da fonte** | ISO |
| **Produto** | Ex.: LilyGO T-Watch |
| **Variante** | **S3** ou **S3 Plus** (obrigatório) |
| **Revisão PCB** | Conhecida ou `desconhecida` |
| **Versão de firmware / IDF** | Ex.: `IDF 5.2.x` |
| **Problema** | Enunciado neutro |
| **Sintoma** | Observável |
| **Condição de reprodução** | Passos mínimos |
| **Causa alegada** | O que a fonte afirma |
| **Causa confirmada?** | `sim` / `não` / `parcial` |
| **Evidência** | Log, link, screenshot, medição |
| **Impacto no YBY** | PC Hub / mobile / wearable / nenhum |
| **Probabilidade** | baixa / média / alta |
| **Severidade** | baixa / média / alta / crítica |
| **Hipótese ou fato** | **Obrigatório** classificar |
| **Correção sugerida** | Ação |
| **Correção validada?** | `sim` / `não` / `não testado` |
| **Risco residual** | Texto curto |
| **Teste necessário** | Como reprovar/confirmar |
| **Documento YBY afetado** | Caminho no repo |
| **Status** | aberto / mitigado / descartado |

## Regra de variante

Nunca promover automaticamente para **S3 Plus** informação marcada apenas como **T-Watch S3**, **T-Watch 2020**, **T-Display S3** ou DevKit genérico. Se a fonte não nomear a variante → classificar como **evidência comunitária** ou **alerta**, não como fato.

## Modelo (copiar)

```markdown
### YBY-INV-20261114-001
- Título:
- Tema:
- Componente:
- Fonte / tipo / URL / data:
- Produto / variante / revisão / firmware:
- Problema / sintoma / reprodução:
- Causa alegada / confirmada?: / evidência:
- Impacto YBY / prob. / sev. / hipótese ou fato:
- Correção / validada? / risco residual / teste / doc / status:
```