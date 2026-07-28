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
# Configurações do cliente — carregadas em tempo de execução (multi-cliente).
# Antes ficavam "coladas" aqui via {{placeholders}}; agora vêm do config.json
# da pasta do cliente, então o mesmo código atende vários clientes.
import client_config

AI_PROVIDER = client_config.require("ai_provider")   # "openai" | "gemini" | "anthropic"
AI_MODEL = client_config.require("ai_model")
AI_API_KEY = client_config.require("ai_api_key")

CHECKOUT_LINK = client_config.get("checkout_link", "")
SYSTEM_PROMPT = client_config.require("system_prompt")  # Prompt BANT gerado automaticamente

# Constantes
SESSION_TTL = 1800  # 30 minutos


def call_ai(messages: list, max_tokens: int = 4096) -> str:
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
    """Chama Anthropic Claude (formato próprio).

    A API da Anthropic só aceita roles "user"/"assistant" na lista de mensagens
    (diferente de OpenAI/Gemini) — instruções injetadas com role "system" no meio
    da conversa precisam ser incorporadas ao parâmetro "system" separado.
    """
    url = "https://api.anthropic.com/v1/messages"

    system_parts = [SYSTEM_PROMPT]
    clean_messages = []
    for m in messages:
        if m.get("role") == "system":
            system_parts.append(m.get("content", ""))
        else:
            clean_messages.append(m)

    data = {
        "model": AI_MODEL,
        "max_tokens": max_tokens,
        "system": "\n\n".join(system_parts),
        "messages": clean_messages
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
        detail = e.read().decode("utf-8", errors="replace")
        print(f"[ERRO Anthropic] {e.code} {e.reason}: {detail}")
        return "Desculpe, tive um probleminha técnico agora. Pode repetir sua última mensagem, por favor? 🙏"


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


def is_handoff_request(message: str) -> bool:
    """
    Detecta se o lead está pedindo explicitamente para falar com um atendente humano
    (em vez de continuar com a IA). Usado para pausar as respostas automáticas do
    agente e notificar o dono do negócio pra assumir a conversa manualmente.
    """
    if not message:
        return False

    message_lower = message.lower()

    handoff_phrases = [
        "falar com atendente", "falar com um atendente", "falar com uma pessoa",
        "falar com humano", "falar com um humano", "quero um atendente",
        "atendente humano", "atendimento humano", "não quero falar com robô",
        "nao quero falar com robo", "não quero falar com um robô",
        "quero falar com alguém de verdade", "quero falar com alguem de verdade",
        "me transfere pra um atendente", "me transfere para um atendente",
        "quero um vendedor", "falar com vendedor", "falar com um vendedor",
        "isso é um robô", "isso e um robo", "você é um robô", "voce e um robo",
        "quero suporte humano", "falar com gerente", "falar com o responsável",
        "falar com o responsavel", "chama o dono", "quero falar com o dono"
    ]

    return any(kw in message_lower for kw in handoff_phrases)


def format_checkout_message(url: str = CHECKOUT_LINK) -> str:
    """Formata mensagem com link de checkout."""
    return f"""Perfeito! Passei tudo aqui. Deixa eu enviar nosso checkout pra você:

{url}

Qualquer dúvida depois da compra, eu fico por aqui! 💪"""
