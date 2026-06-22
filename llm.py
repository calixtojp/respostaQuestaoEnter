"""Cliente LLM (Gemini) como black box fina.

Expõe uma única função útil — `gerar_json` — que recebe um prompt + um schema
(subset OpenAPI/JSON Schema) e devolve a saída JÁ estruturada (dict/list),
usando o modo de saída estruturada do Gemini. O resto do sistema não conhece o
SDK; troca-se o provedor mexendo só aqui.

Imports do SDK são lazy (igual encoder_tokens_transformers): quem não usa LLM
não precisa do pacote instalado nem da chave configurada.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

MODELO = "gemini-2.5-flash"

# Black box: (prompt, schema) -> JSON estruturado. Permite injetar um stub
# offline nos testes, sem tocar na rede.
GeradorJSON = Callable[[str, dict], Any]


@lru_cache(maxsize=1)
def _cliente():
    """Cria (uma vez) o cliente Gemini, lendo GOOGLE_API_KEY do .env."""
    import os  # noqa: PLC0415

    from dotenv import load_dotenv  # noqa: PLC0415
    from google import genai  # noqa: PLC0415

    load_dotenv(Path(__file__).resolve().parent / ".env")
    chave = os.environ.get("GOOGLE_API_KEY")
    if not chave:
        raise RuntimeError("GOOGLE_API_KEY não encontrada no ambiente/.env")
    return genai.Client(api_key=chave)


def gerar_json(prompt: str, schema: dict, modelo: str = MODELO) -> Any:
    """Gera conteúdo com saída estruturada e devolve o JSON desserializado."""
    from google.genai import types  # noqa: PLC0415

    cliente = _cliente()
    resposta = cliente.models.generate_content(
        model=modelo,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )
    return json.loads(resposta.text)
