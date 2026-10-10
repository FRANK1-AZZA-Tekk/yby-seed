# 04 — Multimodalidade e RAG

## Multimodalidade

OpenRouter encaminha modalidades compatíveis com modelos/endpoints: texto, imagem, áudio, arquivo/PDF e vídeo, além de saídas como fala ou mídia em endpoints específicos. Verificar capacidade no catálogo para cada modelo e tarefa. Formato aceito, limite de tamanho, custo e streaming podem variar.

Para YBY, não transmitir continuamente áudio/vídeo do wearable por padrão. Fazer seleção local, reduzir/redigir dados, solicitar consentimento adequado e enviar apenas o segmento necessário. Firmware continua seguro sem rede.

## RAG

Arquitetura preferencial para memória privada:

1. Ingestão e armazenamento locais.
2. Recuperação local híbrida (vetorial + lexical/ID).
3. Deduplicação e filtro de acesso.
4. Rerank remoto somente para corpus permitido e se benchmark comprovar vantagem.
5. Geração local ou remota conforme política, com contexto mínimo e referências.

Embeddings e rerank via API unificada podem facilitar experimentos entre provedores. Não migrar memória sensível para nuvem por conveniência. Verificar modelo, dimensão do embedding, compatibilidade do índice, preço, retenção e efeitos de mudança de modelo.

## Testes

- Imagem: acurácia de extração, resolução, custo/imagem e latência.
- PDF: fidelidade a páginas/trechos, extração de tabelas e limites de arquivo.
- Áudio: qualidade de transcrição, idioma, ruído, latência e consentimento.
- Vídeo: seleção de frames, limites e custo por duração.
- RAG: recall@k, precisão de rerank, groundedness, citações, tokens e custo por tarefa.

## Fontes

- [Multimodal overview](https://openrouter.ai/docs/guides/overview/multimodal/overview)
- [RAG com embeddings e rerank](https://openrouter.ai/docs/cookbook/evaluate-and-optimize/rag)
- [Image generation](https://openrouter.ai/docs/guides/overview/multimodal/image-generation)
- [Video generation](https://openrouter.ai/docs/guides/overview/multimodal/video-generation)
