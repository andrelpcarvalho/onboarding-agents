"""Detecção e mascaramento de dados pessoais (PII) com Microsoft Presidio.

Mascara antes de qualquer coisa ser enviada ao modelo ou gravada (sessão,
memória, lacunas, escalonamentos). Entidades:

- CPF e CNPJ (reconhecedores próprios, com validação de dígito verificador)
- telefone BR, e-mail, cartão de crédito (reconhecedores do Presidio)
- nomes de pessoas (NER do spaCy pt), só se PII_MASK_PERSON=1: em português o
  NER pequeno erra bastante e mascararia termos técnicos.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import (
    CreditCardRecognizer,
    EmailRecognizer,
    PhoneRecognizer,
    SpacyRecognizer,
)
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

LANG = "pt"
SPACY_MODEL = "pt_core_news_sm"

PLACEHOLDERS = {
    "BR_CPF": "<CPF>",
    "BR_CNPJ": "<CNPJ>",
    "PHONE_NUMBER": "<TELEFONE>",
    "EMAIL_ADDRESS": "<EMAIL>",
    "CREDIT_CARD": "<CARTAO>",
    "PERSON": "<PESSOA>",
}


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def cpf_is_valid(value: str) -> bool:
    d = _digits(value)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        total = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (total * 10 % 11) % 10 != int(d[n]):
            return False
    return True


def cnpj_is_valid(value: str) -> bool:
    d = _digits(value)
    if len(d) != 14 or d == d[0] * 14:
        return False
    for n, weights in ((12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]),
                       (13, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])):
        r = sum(int(d[i]) * w for i, w in enumerate(weights)) % 11
        if (0 if r < 2 else 11 - r) != int(d[n]):
            return False
    return True


class CpfRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity="BR_CPF",
            supported_language=LANG,
            patterns=[Pattern("cpf", r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", 0.5)],
            context=["cpf"],
        )

    def validate_result(self, pattern_text: str) -> bool:
        return cpf_is_valid(pattern_text)


class CnpjRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity="BR_CNPJ",
            supported_language=LANG,
            patterns=[Pattern("cnpj", r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b", 0.5)],
            context=["cnpj"],
        )

    def validate_result(self, pattern_text: str) -> bool:
        return cnpj_is_valid(pattern_text)


def _mask_person() -> bool:
    return os.getenv("PII_MASK_PERSON", "0") == "1"


@lru_cache
def _engines() -> tuple[AnalyzerEngine, AnonymizerEngine]:
    nlp = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": LANG, "model_name": SPACY_MODEL}],
        "ner_model_configuration": {"model_to_presidio_entity_mapping": {"PER": "PERSON"}},
    }).create_engine()
    registry = RecognizerRegistry(supported_languages=[LANG])
    for rec in (
        CpfRecognizer(),
        CnpjRecognizer(),
        PhoneRecognizer(supported_language=LANG, supported_regions=("BR",), context=["telefone", "celular", "whatsapp"]),
        EmailRecognizer(supported_language=LANG),
        CreditCardRecognizer(supported_language=LANG),
    ):
        registry.add_recognizer(rec)
    if _mask_person():
        registry.add_recognizer(
            SpacyRecognizer(supported_language=LANG, supported_entities=["PERSON"])
        )
    analyzer = AnalyzerEngine(nlp_engine=nlp, registry=registry, supported_languages=[LANG])
    return analyzer, AnonymizerEngine()


# Identificadores que nunca deveriam aparecer numa resposta do Tutor. E-mail,
# telefone e CNPJ ficam de fora porque a base oficial pode citar contatos da
# empresa (ex.: e-mail do time de segurança) e isso é conteúdo legítimo.
PERSONAL_IDS = ("BR_CPF", "CREDIT_CARD")


def redact(text: str, entities: tuple[str, ...] | None = None) -> tuple[str, list[str]]:
    """Retorna (texto mascarado, tipos de entidade encontrados).

    `entities` restringe os tipos procurados (None = todos).
    """
    if not text or not text.strip():
        return text, []
    analyzer, anonymizer = _engines()
    results = analyzer.analyze(
        text=text, language=LANG, score_threshold=0.4,
        entities=list(entities) if entities else None,
    )
    # CPFs da massa de homologação (data/homolog_data.yaml) são dados de teste, não PII.
    from .missions import homolog_cpfs

    allowed = set(homolog_cpfs())
    if allowed:
        results = [
            r for r in results
            if not (r.entity_type == "BR_CPF" and _digits(text[r.start:r.end]) in allowed)
        ]
    if not results:
        return text, []
    operators = {
        ent: OperatorConfig("replace", {"new_value": ph}) for ent, ph in PLACEHOLDERS.items()
    }
    out = anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)
    return out.text, sorted({r.entity_type for r in results})


def redact_text(text: str) -> str:
    return redact(text)[0]
