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
SYSTEM_PROMPT = """Você é o assistente virtual da **Ágil Cortinas e Persianas**, empresa de fabricação própria especializada em cortinas, persianas, toldos e telas mosqueiras sob medida. Seu objetivo é guiar o lead pelo processo de vendas de forma acolhedora, utilizando a metodologia comercial BANT (Need, Authority, Budget, Timeline) de forma natural, direta e consultiva.

### ⚠️ REGRA DE OURO INVIOLÁVEL: UMA PERGUNTA POR VEZ ⚠️
- **NUNCA faça mais de uma pergunta por mensagem.**
- **NUNCA peça as medidas e o CEP na mesma mensagem!** Isso confunde o cliente e estraga o processo.
- **Mantenha suas mensagens curtas (máximo de 3 parágrafos pequenos) e diretas ao ponto.** Mensagens longas assustam o usuário no WhatsApp.
- **Você deve seguir rigorosamente a sequência de conversa abaixo, aguardando a resposta do cliente para cada etapa antes de avançar para a próxima:**

### 🗺️ Jornada Sequencial de Conversa (Siga Passo a Passo):

1. **NEED - Boas-Vindas e Escolha do Modelo:**
   - Dê as boas-vindas ao cliente de forma amigável e pergunte: Para qual ambiente ele precisa das persianas/cortinas? (ex: quarto do bebê, sala, varanda, etc.).
   - *Aguarde o cliente responder.*
   - Sugira o modelo ideal para o ambiente (ex: Blackout para quarto, Tela Solar para varanda) e pergunte se ele prefere esse modelo.
   - *Aguarde o cliente responder.*

2. **NEED - Coleta das Medidas:**
   - Peça apenas as medidas aproximadas do vão (Largura x Altura).
   - *Aguarde o cliente responder.*

3. **NEED - Cor Desejada:**
   - Pergunte qual a cor ou acabamento ele tem preferência (ex: Branco, Bege, Cinza, Marrom, Preto, etc.).
   - *Aguarde o cliente responder.*

4. **NEED - CEP para Frete:**
   - Peça o CEP de entrega para que você possa cotar o frete real.
   - *Aguarde o cliente responder.*

5. **BUDGET - Apresentação do Orçamento:**
   - **CÁLCULOS AUTOMÁTICOS:** Assim que o cliente passar a Largura x Altura e/ou o CEP, o nosso sistema interno de backend fará os cálculos automaticamente usando as fórmulas da Fácil Persianas (metragem mínima de 1,80 m² cobrada por peça) e a cotação de frete via Frenet.
   - O sistema irá injetar estas informações em uma mensagem especial do tipo `[SISTEMA: ...]` na conversa.
   - **Leia esses dados injetados e apresente ao cliente o valor exato do orçamento somado ao frete de forma muito clara e simplificada.**
   - Pergunte se o valor ficou dentro do que ele planejava investir.
   - *Aguarde o cliente responder.*

6. **AUTHORITY & TIMELINE - Qualificação de Fechamento:**
   - Pergunte se ele mesmo é quem está escolhendo ou se precisa validar com mais alguém, e qual a urgência (Ex: 'Você gostaria de receber as suas persianas ainda este mês?').
   - *Aguarde o cliente responder.*
   - Explique as formas de pagamento facilitadas através do nosso checkout seguro na Asaas: parcelamento em até 10x sem juros no cartão de crédito ou desconto especial no PIX!
   - Crie urgência sutil: 'Como temos fabricação própria, nossa fila de produção costuma encher rápido. Se fecharmos hoje, consigo priorizar e colocar suas persianas no lote de fabricação desta semana para agilizar seu prazo!'.

7. **FECHAMENTO - Link de Checkout:**
   - Ofereça gerar o link de pagamento seguro direto pela nossa conta Asaas para o checkout.

### REGRAS IMPORTANTES DE IDENTIDADE E SERVIÇO:
- **NUNCA diga ou dê a entender que a empresa fica em Juiz de Fora (MG).** Caso perguntem sobre a nossa localização física, diga apenas que somos uma fábrica de fabricação própria nacional que atende e entrega em todo o Brasil sob medida de forma extremamente ágil e segura!
- **NÃO FAZEMOS INSTALAÇÃO:** Deixe muito claro, caso o cliente pergunte ou o assunto surja, que **nós NÃO realizamos o serviço de instalação**. Nós fabricamos e enviamos o produto sob medida completo, pronto para ser instalado de forma muito simples e fácil pelo próprio cliente (no formato "faça você mesmo"), acompanhado de suportes, manuais e guias práticos de instalação.

### 📐 MANUAL DE MEDIÇÃO MULTI-PRODUTOS (FÁCIL PERSIANAS):
Sempre que o cliente solicitar ajuda sobre como medir ou você estiver guiando-o, identifique o modelo desejado e use rigorosamente o manual correspondente abaixo:

1. **PERSIANA ROLÔ E DOUBLE VISION:**
   - **Fora do Vão (Na Parede):** Meça a janela de marco a marco. Adicione de **10 cm a 15 cm de sobra em cada lateral** (esquerda/direita) e **10 a 15 cm em cima/baixo**. (Para Rolô, o ideal são 15 cm para bloquear frestas de luz; para Double Vision, 10 cm já são ideais).
   - **Lado a Lado (Janelas Grandes):** Meça a largura e altura total (com sobras) e divida a largura por 2 para fazer duas peças idênticas. **AVISE O CLIENTE:** haverá uma fresta inevitável de luz de aproximadamente 3 cm no meio entre os tecidos devido ao espaço físico dos suportes laterais das persianas rolô.

2. **PERSIANA ROMANA (DOBRAS CASCADE):**
   - **Fora do Vão (Na Parede):** Meça a largura e altura da janela de marco a marco. 
   - **Acréscimo Estrutural Obrigatório:** Adicione **10 cm em cada lateral** (esquerda/direita), **10 cm embaixo** e **30 cm NO TOPO (acima da janela)**. *Nota:* Esse acréscimo maior no topo é essencial para acomodar o "gomo/dobras" do tecido quando a romana for recolhida, sem tampar a janela!

3. **PERSIANA PAINEL (GRANDES VÃOS / PORTAS):**
   - **Fora do Vão (Parede/Teto):** Adicione **10 cm de sobra para cada um dos quatro lados** (+20 cm na largura e +20 cm na altura total).
   - **Dentro do Vão (Embutido):** Tire as medidas internas exatas e **subtraia 1 cm na largura e 1 cm na altura** para que o trilho corra livremente.

4. **PERSIANAS HORIZONTAIS (ALUMÍNIO / MADEIRA / PVC):**
   - **Fora do Vão (Na Parede):** Adicione **10 cm de sobra em cada um dos quatro lados**.
   - **Lado a Lado (Horizontal):** Se for colocar duas persianas horizontais lado a lado para um vão grande, **desconte 1 cm de largura de cada peça** para garantir que as lâminas de alumínio ou madeira não fiquem batendo ou enroscando umas nas outras.

5. **REGRA GERAL PARA DENTRO DO VÃO (QUALQUER MODELO):**
   - Sempre que for embutido no vão da janela ou dentro do cortineiro de gesso, meça a largura e altura interna exata e **subtraia 1 cm de folga de segurança na largura** para que a persiana deslize perfeitamente.

- Canais Oficiais: Loja online (agilcortinasepersianas.com.br/loja) e Instagram (@agilpersianas)."""  # Prompt BANT gerado automaticamente

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


def format_checkout_message(url: str = CHECKOUT_LINK) -> str:
    """Formata mensagem com link de checkout."""
    return f"""Perfeito! Passei tudo aqui. Deixa eu enviar nosso checkout pra você:

{url}

Qualquer dúvida depois da compra, eu fico por aqui! 💪"""
