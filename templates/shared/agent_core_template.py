"""
agent_core_template.py — Núcleo da lógica de IA (reutilizável para todos os módulos)

Use este template como base para criar:
  - ~/meu-agente/agent.py (módulo WhatsApp)
  - FastAPI handler /chat (módulo Widget, v1.1+)

Substitua {{placeholders}} com dados do usuário durante setup.
"""

import json
import urllib.request
import urllib.error

# Configurações ({{placeholders}} preenchidos durante setup)
AI_PROVIDER = "{{AI_PROVIDER}}"          # "openai" | "gemini" | "anthropic"
AI_MODEL = "{{AI_MODEL}}"                # gpt-5.4-mini | gemini-2.5-flash | claude-opus-4-6
AI_API_KEY = "{{AI_API_KEY}}"            # Sua chave de API

CHECKOUT_LINK = "{{CHECKOUT_LINK}}"      # Link de compra
SYSTEM_PROMPT = """{{SYSTEM_PROMPT}}"""  # Prompt BANT gerado automaticamente

# Constantes
SESSION_TTL = 1800  # 30 minutos


def call_ai(messages: list, max_tokens: int = 512) -> str:
    """
    Chama IA baseado no provider configurado.

    Args:
        messages: Lista de mensagens [{"role": "user", "content": "..."}, ...]
        max_tokens: Máximo de tokens na resposta

    Returns:
        String com resposta da IA
    """

    if AI_PROVIDER == "openai":
        return call_openai(messages, max_tokens)
    elif AI_PROVIDER == "gemini":
        return call_gemini(messages, max_tokens)
    elif AI_PROVIDER == "anthropic":
        return call_anthropic(messages, max_tokens)
    else:
        raise ValueError(f"Provider desconhecido: {AI_PROVIDER}")


def call_openai(messages: list, max_tokens: int) -> str:
    """Chama OpenAI API (gpt-5.4-mini)."""
    url = "https://api.openai.com/v1/chat/completions"

    data = {
        "model": AI_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "max_completion_tokens": max_tokens,  # NÃO usar max_tokens com gpt-5.4-mini!
        "temperature": 0.7
    }

    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read())
            return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        return f"Erro OpenAI: {e.reason}"


def call_gemini(messages: list, max_tokens: int) -> str:
    """Chama Google Gemini (endpoint OpenAI-compatible)."""
    url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

    data = {
        "model": AI_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "max_tokens": max_tokens,
        "temperature": 0.7
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AI_API_KEY}"
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read())
            return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        return f"Erro Gemini: {e.reason}"


def call_anthropic(messages: list, max_tokens: int) -> str:
    """Chama Anthropic Claude (formato próprio)."""
    url = "https://api.anthropic.com/v1/messages"

    data = {
        "model": AI_MODEL,
        "max_tokens": max_tokens,
        "system": SYSTEM_PROMPT,
        "messages": messages
    }

    headers = {
        "x-api-key": AI_API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            result = json.loads(response.read())
            return result["content"][0]["text"]
    except urllib.error.HTTPError as e:
        return f"Erro Anthropic: {e.reason}"


def is_purchase_intent(message: str, conversation: list = None) -> bool:
    """
    Detecta se o lead tem intenção real de fechamento/compra (para envio de link).
    """
    if not message:
        return False

    message_lower = message.lower()
    
    # Palavras-chave de alto interesse de fechamento (solicitação explícita de link ou pagamento)
    closing_keywords = [
        "manda o link", "me manda o link", "enviar o link", "envia o link", 
        "passa o link", "link de pagamento", "link para pagar", "como faço para comprar",
        "quero comprar", "quero fechar", "gerar o link", "onde eu pago", "link de compra",
        "link do checkout", "passa o pix", "me manda o pix", "chave pix", "pagar no pix",
        "comprar agora", "fechar pedido", "fechar o pedido", "fazer o pagamento"
    ]

    # Verificar se o cliente solicitou diretamente o link ou fechamento
    if any(kw in message_lower for kw in closing_keywords):
        return True

    return False


def format_checkout_message() -> str:
    """Formata mensagem com link de checkout."""
    return f"""Perfeito! Passei tudo aqui. Deixa eu enviar nosso checkout pra você:

{CHECKOUT_LINK}

Qualquer dúvida depois da compra, eu fico por aqui! 💪"""
