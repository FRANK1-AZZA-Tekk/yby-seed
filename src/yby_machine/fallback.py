"""Fallback determinístico: YBYSpec mínima a partir de palavras-chave do prompt."""

from __future__ import annotations

from src.yby_machine.spec import (
    ActionSpec,
    BrFieldType,
    CalcRule,
    EntitySpec,
    FieldSpec,
    PaymentStatus,
    PixConfig,
    WhatsAppConfig,
    YBYSpec,
)

_DEFAULT_PIX = (
    "00020126580014BR.GOV.BCB.PIX0136123e4567-e12b-12d1-a456-426614174000"
    "52040000530398654040.005802BR5913YBY MICRO APP6009SAO PAULO62070503***6304ABCD"
)


def fallback_spec_from_prompt(prompt: str) -> YBYSpec:
    """Gera uma YBYSpec válida sem chamar modelo. Heurística por palavras-chave."""

    text = (prompt or "").casefold()
    # Estoque antes de oficina: "produtos" contém o sufixo "os " e quebraria a OS.
    if _matches(text, ("estoque", "inventário", "inventario", "sku")):
        return _estoque_spec()
    if _matches(text, ("oficina", "ordem de serviço", "ordem de servico", "mecânic", "mecanica")):
        return _oficina_spec()
    if _matches(text, ("produto", "produtos")):
        return _estoque_spec()
    # encomenda / pix / padrão BR comércio
    return _encomenda_spec()


def _matches(text: str, keywords: tuple[str, ...]) -> bool:
    return any(k in text for k in keywords)


def _encomenda_spec() -> YBYSpec:
    return YBYSpec(
        name="encomendas",
        title="Encomendas + Pix",
        description="Cadastro de encomendas com status de pagamento e Pix estático.",
        entities=[
            EntitySpec(
                name="encomenda",
                label="Encomenda",
                fields=[
                    FieldSpec(name="cliente", label="Cliente", type=BrFieldType.texto),
                    FieldSpec(name="cpf", label="CPF", type=BrFieldType.cpf, required=False),
                    FieldSpec(name="telefone", label="Telefone", type=BrFieldType.telefone_br),
                    FieldSpec(name="item", label="Item", type=BrFieldType.texto),
                    FieldSpec(name="valor", label="Valor (R$)", type=BrFieldType.moeda_brl),
                    FieldSpec(
                        name="cep",
                        label="CEP entrega",
                        type=BrFieldType.cep,
                        required=False,
                    ),
                ],
            )
        ],
        actions=[
            ActionSpec(name="nova", label="Nova encomenda", description="Cadastrar pedido"),
            ActionSpec(name="marcar_pago", label="Marcar pago", description="Status Pago"),
        ],
        calc_rules=[],
        payment_statuses=list(PaymentStatus),
        pix=PixConfig(enabled=True, payload=_DEFAULT_PIX, label="Copiar Pix"),
        whatsapp=WhatsAppConfig(enabled=True, summary_prefix="Encomenda YBY"),
    )


def _oficina_spec() -> YBYSpec:
    return YBYSpec(
        name="oficina_os",
        title="Oficina — Ordem de Serviço",
        description="OS de oficina com veículo, mão de obra e status de pagamento.",
        entities=[
            EntitySpec(
                name="os",
                label="Ordem de Serviço",
                fields=[
                    FieldSpec(name="cliente", label="Cliente", type=BrFieldType.texto),
                    FieldSpec(name="cpf", label="CPF", type=BrFieldType.cpf, required=False),
                    FieldSpec(name="telefone", label="Telefone", type=BrFieldType.telefone_br),
                    FieldSpec(name="veiculo", label="Veículo", type=BrFieldType.texto),
                    FieldSpec(name="problema", label="Problema", type=BrFieldType.texto),
                    FieldSpec(
                        name="mao_obra",
                        label="Mão de obra (R$)",
                        type=BrFieldType.moeda_brl,
                    ),
                    FieldSpec(
                        name="pecas",
                        label="Peças (R$)",
                        type=BrFieldType.moeda_brl,
                        required=False,
                    ),
                    FieldSpec(
                        name="total",
                        label="Total (R$)",
                        type=BrFieldType.moeda_brl,
                        required=False,
                    ),
                ],
            )
        ],
        actions=[
            ActionSpec(name="nova_os", label="Nova OS", description="Abrir ordem"),
            ActionSpec(name="fechar", label="Fechar OS", description="Concluir serviço"),
        ],
        calc_rules=[
            CalcRule(
                name="total_os",
                expression="mao_obra + pecas",
                result_field="total",
            )
        ],
        payment_statuses=list(PaymentStatus),
        pix=PixConfig(enabled=True, payload=_DEFAULT_PIX, label="Pix da oficina"),
        whatsapp=WhatsAppConfig(enabled=True, summary_prefix="OS Oficina"),
    )


def _estoque_spec() -> YBYSpec:
    return YBYSpec(
        name="estoque_simples",
        title="Estoque simples",
        description="Controle básico de produtos e quantidades.",
        entities=[
            EntitySpec(
                name="produto",
                label="Produto",
                fields=[
                    FieldSpec(name="nome", label="Nome", type=BrFieldType.texto),
                    FieldSpec(name="sku", label="SKU", type=BrFieldType.texto, required=False),
                    FieldSpec(name="qtd", label="Quantidade", type=BrFieldType.numero),
                    FieldSpec(name="preco", label="Preço (R$)", type=BrFieldType.moeda_brl),
                    FieldSpec(
                        name="fornecedor_cnpj",
                        label="CNPJ fornecedor",
                        type=BrFieldType.cnpj,
                        required=False,
                    ),
                    FieldSpec(
                        name="total",
                        label="Total (R$)",
                        type=BrFieldType.moeda_brl,
                        required=False,
                    ),
                ],
            )
        ],
        actions=[
            ActionSpec(name="entrada", label="Entrada", description="Somar estoque"),
            ActionSpec(name="saida", label="Saída", description="Baixar estoque"),
        ],
        calc_rules=[
            CalcRule(
                name="valor_estoque",
                expression="qtd * preco",
                result_field="total",
            )
        ],
        payment_statuses=list(PaymentStatus),
        pix=PixConfig(enabled=False),
        whatsapp=WhatsAppConfig(enabled=True, summary_prefix="Estoque YBY"),
    )
