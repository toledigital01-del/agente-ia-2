#!/usr/bin/env python3
"""
agent_template.py — Agente WhatsApp completo (v1.0)

Responsabilidades:
1. Detectar trigger phrase em mensagens
2. Carregar/gerenciar sessão de conversa
3. Chamar IA para resposta
4. Detectar intenção de compra e enviar checkout
5. Salvar conversa em SQLite

Use como: python3 agent.py --test
          python3 agent.py --chat PHONE
          Importar em watcher.py
"""

import sys
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# Carregar templates compartilhados
sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))
from agent_core_template import call_ai, is_purchase_intent, is_handoff_request, is_toldo_request, format_checkout_message, SYSTEM_PROMPT, CHECKOUT_LINK, SESSION_TTL
import client_config
from sessions_template import init_db, load_session, save_session, create_lead, add_message, mark_checkout_sent, save_metadata, get_metadata, get_lead_history

# Inicializar o banco de dados automaticamente ao importar o módulo
init_db()

import re

def extract_dimensions(text: str):
    """Extrai largura e altura de textos como '1.50 x 2.00', '150x200', '1.5 por 2'."""
    pattern = r"(\d+(?:[.,]\d+)?)\s*(?:x|por)\s*(\d+(?:[.,]\d+)?)"
    match = re.search(pattern, text.lower())
    if match:
        try:
            w_str, h_str = match.group(1), match.group(2)
            w = float(w_str.replace(",", "."))
            h = float(h_str.replace(",", "."))
            if w > 10:
                w = w / 100.0
            if h > 10:
                h = h / 100.0
            return round(w, 2), round(h, 2)
        except Exception:
            pass
    return None

def extract_cep(text: str) -> str:
    """Extrai CEP de 8 dígitos de um texto."""
    match = re.search(r"\b(\d{5})-?(\d{3})\b", text)
    if match:
        return f"{match.group(1)}{match.group(2)}"
    return None

def get_shipping_quote(recipient_cep: str, width_m: float, height_m: float, quantity: int = 1) -> dict:
    """Consulta frete na API da Frenet."""
    url = "https://api.frenet.com.br/shipping/quote"
    token = client_config.get("frenet_token", "")
    
    recipient_cep = "".join(filter(str.isdigit, recipient_cep))
    if len(recipient_cep) != 8:
        return {"error": "CEP inválido"}

    length_cm = int(width_m * 100)
    height_cm = 10
    width_cm = 10
    area = width_m * height_m
    weight_kg = max(1.0, area * 2.0)

    data = {
        "SellerCEP": "36015000",
        "RecipientCEP": recipient_cep,
        "ShipmentInvoiceValue": float(max(150.00, area * 150.00)),
        "RecipientCountry": "BR",
        "ShippingItemArray": [
            {
                "Height": height_cm,
                "Length": length_cm,
                "Width": width_cm,
                "Weight": weight_kg,
                "Quantity": int(quantity)
            }
        ]
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json", "token": token},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read().decode())
            services = res.get("ShippingSevicesArray", [])
            quotes = []
            for s in services:
                if s.get("Error") == False or str(s.get("Error")).lower() == "false":
                    quotes.append({
                        "carrier": s.get("Carrier"),
                        "description": s.get("ServiceDescription"),
                        "price": float(s.get("ShippingPrice")),
                        "days": int(s.get("DeliveryTime"))
                    })
            return {"quotes": quotes}
    except Exception as e:
        return {"error": str(e)}

# Configurações de trigger ({{placeholders}} preenchidos durante setup)
CHECKOUT_LINK = client_config.get("checkout_link", "")
TRIGGER_EXACT = client_config.get("lead_trigger_phrase", "")
TRIGGER_KEYWORDS = [
    client_config.get("product_name", ""),
    "dúvida",
    "informação",
    "saiba mais",
    "orçamento",
    "orcamento",
    "cortina",
    "persiana",
    "toldo",
    "tela",
    "mosqueteira",
    "blackout",
    "double vision",
    "valor",
    "preço",
    "preco",
    "quanto custa",
    "comprar",
    "encomendar",
    "oi",
    "olá",
    "ola",
    "bom dia",
    "boa tarde",
    "boa noite"
]

DB_PATH = str(client_config.DB_PATH)

# ── Tabela de preços de referência (coletada da Fácil Persianas em 2026-07-29) ─
# Pontos reais (área em m², preço em R$), largura fixa em 100cm (variando a
# altura), direto do site oficial. Confirmado que o preço de mercado NÃO é uma
# reta simples de R$/m² (tag "autopriced-by-table-pricing" no próprio site) —
# a taxa por m² adicional varia de trecho pra trecho (de ~R$26 a ~R$72/m² só
# na faixa de 1,2 a 1,8m² do Blackout, por exemplo). Por isso interpolamos
# entre pontos reais em vez de multiplicar por uma taxa fixa.
# Fonte completa (mais categorias e larguras): docs/tabela_precos_referencia.json
PRECO_ROLO_BLACKOUT = [
    (0.36, 147.39), (1.20, 264.91), (1.43, 267.78), (1.50, 272.83), (1.58, 278.56),
    (1.66, 284.34), (1.74, 290.07), (1.80, 294.39), (1.90, 301.58), (2.00, 281.75),
    (2.10, 288.32), (2.20, 294.88), (2.30, 301.45), (2.40, 308.00), (2.50, 314.57),
    (2.65, 406.76), (2.70, 410.23), (2.90, 424.09),
]
PRECO_ROLO_TELA_SOLAR = [
    (0.36, 117.33), (1.20, 342.22), (1.43, 346.38), (1.50, 353.68), (1.58, 362.00),
    (1.66, 370.34), (1.74, 378.71), (1.80, 384.94), (1.90, 395.36), (2.00, 472.11),
    (2.10, 484.24), (2.20, 496.38), (2.30, 508.46), (2.40, 520.61), (2.50, 532.74),
    (2.65, 731.80), (2.70, 738.69), (2.90, 766.21),
]
PRECO_DOUBLE_VISION = [
    (0.36, 302.98), (1.20, 529.84), (1.43, 529.84), (1.50, 597.01), (1.90, 611.69),
    (2.00, 767.31), (2.10, 814.78), (2.20, 833.58), (2.30, 852.40), (2.40, 871.19),
    (2.50, 890.00), (2.65, 918.19), (2.70, 927.61),
]


def interpolar_preco(area_m2: float, pontos: list) -> float:
    """Preço pra uma área, usando pontos reais (área, preço) coletados de mercado.

    IMPORTANTE: a Fácil Persianas NÃO interpola suavemente entre tamanhos —
    testamos ao vivo no site deles (trocando largura/altura no seletor real)
    e confirmamos que o preço "arredonda pra cima" pro próximo tamanho real
    (ex: 1,00m x 1,00m cobra o mesmo que 1,00m x 1,20m, porque não existe
    corte menor que 1,20m de altura pra essa largura — validamos ponto a
    ponto: 1x1m cobra R$264,91 de verdade, não um valor interpolado menor
    como R$236,93). Por isso usamos o preço do próximo ponto real >= área
    pedida (degrau), em vez de uma média entre dois pontos — a média dava
    um valor mais barato do que a Fácil realmente cobra."""
    pontos = sorted(pontos)
    for a, p in pontos:
        if area_m2 <= a:
            return p
    # Área maior que o maior ponto coletado: aí sim extrapola pela inclinação
    # do último trecho, já que não há um próximo degrau real pra usar.
    (a0, p0), (a1, p1) = pontos[-2], pontos[-1]
    taxa = (p1 - p0) / (a1 - a0)
    return p1 + (area_m2 - a1) * taxa


# ── Consulta de preço AO VIVO na Fácil Persianas (com fallback pra tabela estática) ──
# A cor muda o preço de verdade no site deles (ex: Blackout Branca R$147,39 vs
# Preta R$160,76 na mesma peça) — por isso buscamos o produto certo por cor,
# não só por categoria. Se a busca ao vivo falhar por qualquer motivo (site
# fora do ar, timeout, produto não encontrado), cai pra tabela estática
# (PRECO_ROLO_BLACKOUT etc.) como rede de segurança.
FACIL_PERSIANAS_BASE = "https://www.facilpersianas.com.br"

CORES_CONHECIDAS = ["branco", "branca", "bege", "cinza", "preto", "preta", "marfim"]

HANDLES_ROLO_BLACKOUT = {
    "branco": "persiana-rolo-blackout-branca", "branca": "persiana-rolo-blackout-branca",
    "bege": "persiana-rolo-blackout-bege",
    "cinza": "persiana-rolo-blackout-cinza",
    "preto": "persiana-rolo-blackout-preta", "preta": "persiana-rolo-blackout-preta",
}
HANDLES_ROLO_TELA_SOLAR = {
    "branco": "persiana-rolo-tela-solar-3-branca", "branca": "persiana-rolo-tela-solar-3-branca",
    "bege": "persiana-rolo-tela-solar-3-bege",
    "cinza": "persiana-rolo-tela-solar-3-cinza",
    "preto": "persiana-rolo-tela-solar-3-preta", "preta": "persiana-rolo-tela-solar-3-preta",
}
HANDLES_DOUBLE_VISION = {
    "branco": "persiana-double-vision-semi-blackout-branca-acinzentada",
    "branca": "persiana-double-vision-semi-blackout-branca-acinzentada",
    "cinza": "persiana-double-vision-semi-blackout-cinza",
    "preto": "persiana-double-vision-semi-blackout-preta", "preta": "persiana-double-vision-semi-blackout-preta",
}


def extract_color(text: str) -> str:
    """Extrai o nome de cor conhecida de um texto (ex: 'branco', 'cinza')."""
    text_lower = text.lower()
    for cor in CORES_CONHECIDAS:
        if cor in text_lower:
            return cor
    return None


def buscar_preco_ao_vivo(handle: str, area_m2: float, timeout: int = 5) -> float:
    """Busca o preço real no site da Fácil Persianas pra essa área (m²), via
    interpolação entre as variantes (largura-altura) reais mais próximas.
    Retorna None em qualquer falha — quem chamar precisa ter um fallback."""
    if not handle:
        return None
    try:
        url = f"{FACIL_PERSIANAS_BASE}/products/{handle}.json"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        pontos = []
        for v in data.get("product", {}).get("variants", []):
            m = re.match(r"^(\d+)-(\d+)$", v.get("title", ""))
            if not m:
                continue
            w_cm, h_cm = int(m.group(1)), int(m.group(2))
            area = (w_cm / 100.0) * (h_cm / 100.0)
            pontos.append((area, float(v["price"])))
        if not pontos:
            return None
        return interpolar_preco(area_m2, pontos)
    except Exception as e:
        print(f"⚠️  Falha ao buscar preço ao vivo ({handle}): {e}")
        return None


def calcular_preco_modelo(handles_map: dict, tabela_fallback: list, charged_area: float, cor: str = None) -> float:
    """Preço do modelo pra uma área/cor: tenta ao vivo primeiro, cai pra tabela
    estática de referência se a busca ao vivo falhar."""
    cor_norm = (cor or "branca").lower()
    handle = handles_map.get(cor_norm) or handles_map.get("branca")
    preco = buscar_preco_ao_vivo(handle, charged_area)
    if preco is not None:
        return preco
    return interpolar_preco(charged_area, tabela_fallback)


def is_trigger(text: str) -> bool:
    """Verifica se mensagem contém trigger phrase (Sempre ativa para responder a absolutamente qualquer mensagem)."""
    return True


def handle_message(phone: str, sender_name: str, text: str) -> str:
    """
    Processa mensagem e retorna resposta do agente com cálculos físicos e cotação de frete.

    Args:
        phone: Número do lead (ex: "5585987654321")
        sender_name: Nome do lead
        text: Conteúdo da mensagem

    Returns:
        Resposta do agente (ou None se não é trigger)
    """

    # 1. Verificar trigger
    if not is_trigger(text):
        return None

    # 2. Criar/carregar lead
    lead_id = create_lead(phone, name=sender_name)

    # Tentar extrair dimensões e CEP da mensagem atual
    dims = extract_dimensions(text)
    if dims:
        w, h = dims
        save_metadata(lead_id, "width", str(w))
        save_metadata(lead_id, "height", str(h))

    cep = extract_cep(text)
    if cep:
        save_metadata(lead_id, "cep", cep)

    cor = extract_color(text)
    if cor:
        save_metadata(lead_id, "cor", cor)

    # 3. Carregar sessão ativa (cache "quente", expira em SESSION_TTL) ou,
    # se ela já expirou, reconstruir o contexto a partir do histórico
    # permanente salvo no banco — assim um lead que some e volta dias depois
    # não recomeça do zero, e a IA consegue retomar de onde parou.
    messages = load_session(lead_id)
    resuming_after_gap = False
    gap_seconds = 0
    if messages is None:
        history = get_lead_history(lead_id, limit=40)
        if history:
            # get_lead_history retorna do mais recente pro mais antigo — inverter
            messages = [{"role": h["role"], "content": h["content"]} for h in reversed(history)]
            gap_seconds = int(time.time()) - history[0]["ts"]
            resuming_after_gap = gap_seconds > SESSION_TTL
        else:
            messages = []

    # 4. Adicionar mensagem do usuário

    user_message = {"role": "user", "content": text}
    messages.append(user_message)
    add_message(lead_id, "user", text)

    # Carregar metadados salvos acumulados para realizar os cálculos estruturados
    saved_w = get_metadata(lead_id, "width")
    saved_h = get_metadata(lead_id, "height")
    saved_cep = get_metadata(lead_id, "cep")
    saved_cor = get_metadata(lead_id, "cor")

    prompt_injection = []

    if resuming_after_gap:
        if gap_seconds >= 86400:
            gap_desc = f"{gap_seconds / 86400:.0f} dia(s)"
        else:
            gap_desc = f"{gap_seconds / 3600:.0f} hora(s)"
        prompt_injection.append(
            f"[SISTEMA: Este lead está retomando o contato depois de cerca de {gap_desc} sem falar com a gente. "
            "Use o histórico da conversa acima como contexto real (ele lembra de tudo que já foi dito). "
            "Cumprimente reconhecendo a retomada de forma breve e natural (ex: 'Que bom que voltou!'), "
            "SEM repetir a introdução/apresentação do zero, e continue o atendimento exatamente de onde a "
            "conversa parou — nunca finja que é a primeira mensagem dele.]"
        )

    if saved_w and saved_h:
        w_float = float(saved_w)
        h_float = float(saved_h)
        area = w_float * h_float
        charged_area = max(1.80, area) # Área mínima cobrada de 1.80m² igual à Fácil Persianas!

        # Preços buscados AO VIVO na Fácil Persianas pra essa área+cor (com
        # fallback pra tabela estática de referência se a busca falhar).
        p_blackout = calcular_preco_modelo(HANDLES_ROLO_BLACKOUT, PRECO_ROLO_BLACKOUT, charged_area, saved_cor)
        p_solar = calcular_preco_modelo(HANDLES_ROLO_TELA_SOLAR, PRECO_ROLO_TELA_SOLAR, charged_area, saved_cor)
        p_double = calcular_preco_modelo(HANDLES_DOUBLE_VISION, PRECO_DOUBLE_VISION, charged_area, saved_cor)

        calc_info = f"[SISTEMA: Para as medidas de {w_float:.2f}m x {h_float:.2f}m (Área real: {area:.2f}m², Área cobrada/mínima: {charged_area:.2f}m²):\n"
        calc_info += f"- Rolô Blackout: R$ {p_blackout:.2f}\n"
        calc_info += f"- Rolô Tela Solar: R$ {p_solar:.2f}\n"
        calc_info += f"- Double Vision: R$ {p_double:.2f}\n"
        calc_info += "USE ESTES VALORES EXATOS NO SEU ORÇAMENTO! NUNCA INVENTE OUTROS PREÇOS!]"
        prompt_injection.append(calc_info)

    if saved_cep and saved_w and saved_h:
        w_float = float(saved_w)
        h_float = float(saved_h)
        quote_res = get_shipping_quote(saved_cep, w_float, h_float)
        if "quotes" in quote_res and quote_res["quotes"]:
            best_quote = quote_res["quotes"][0]
            carrier = best_quote["carrier"]
            desc = best_quote["description"]
            price = best_quote["price"]
            days = best_quote["days"]
            
            shipping_info = f"[SISTEMA: Cotação de Frete via Frenet para CEP {saved_cep}: {carrier} ({desc}) por R$ {price:.2f} - entrega em {days} dias úteis. Informe e cobre junto no fechamento!]"
            prompt_injection.append(shipping_info)
        elif "error" in quote_res:
            prompt_injection.append(f"[SISTEMA: Ocorreu um erro no cálculo de frete Frenet para o CEP {saved_cep}: {quote_res.get('error')}. Diga ao cliente que vai calcular com o setor de logística e já retorna.]")

    # Injetar instruções calculadas dinamicamente no final do histórico enviado à IA
    ai_messages = messages.copy()
    if prompt_injection:
        system_instruction = "\n".join(prompt_injection)
        ai_messages.append({"role": "system", "content": system_instruction})

    # 5. Chamar IA
    response = call_ai(ai_messages)

    # 6. Adicionar resposta do agente
    messages.append({"role": "assistant", "content": response})
    add_message(lead_id, "assistant", response)

    # 7. Salvar sessão
    save_session(lead_id, messages)

    # 8. Verificar intenção de compra
    if is_purchase_intent(text, messages) and len(messages) >= 4:
        # Calcular preço dinâmico com base nas medidas e CEP salvos do lead
        saved_w = get_metadata(lead_id, "width")
        saved_h = get_metadata(lead_id, "height")
        saved_cep = get_metadata(lead_id, "cep")
        saved_cor = get_metadata(lead_id, "cor")

        total_price = 0.0
        if saved_w and saved_h:
            try:
                w_float = float(saved_w)
                h_float = float(saved_h)
                area = w_float * h_float
                charged_area = max(1.80, area)

                # Preço padrão (Rolô Blackout como padrão se não soubermos o exato modelo)
                total_price = calcular_preco_modelo(HANDLES_ROLO_BLACKOUT, PRECO_ROLO_BLACKOUT, charged_area, saved_cor)
                
                # Somar frete se disponível
                if saved_cep:
                    quote_res = get_shipping_quote(saved_cep, w_float, h_float)
                    if "quotes" in quote_res and quote_res["quotes"]:
                        total_price += quote_res["quotes"][0]["price"]
            except Exception:
                pass

        # Link padrão de contingência
        checkout_url = CHECKOUT_LINK
        
        # Se temos um preço válido, gera o link na Asaas
        if total_price > 20.0:
            try:
                from pathlib import Path
                p_conf = Path.home() / ".meu-agente" / "config.json"
                if p_conf.exists():
                    config_data = json.loads(p_conf.read_text(encoding="utf-8"))
                    asaas_token = config_data.get("asaas_api_key", "")
                    
                    if asaas_token:
                        asaas_url = "https://api.asaas.com/v3/paymentLinks"
                        payload = {
                            "name": f"Pedido Customizado - Ágil Persianas",
                            "description": f"Persiana sob medida de {saved_w}m x {saved_h}m com envio incluso para o CEP {saved_cep}",
                            "value": round(total_price, 2),
                            "billingType": "UNDEFINED",
                            "chargeType": "DETACHED",
                            "dueDateLimitDays": 3
                        }
                        req = urllib.request.Request(
                            asaas_url,
                            data=json.dumps(payload).encode("utf-8"),
                            headers={
                                "Content-Type": "application/json",
                                "access_token": asaas_token
                            },
                            method="POST"
                        )
                        with urllib.request.urlopen(req, timeout=12) as r:
                            res = json.loads(r.read().decode("utf-8"))
                            if "url" in res:
                                checkout_url = res["url"]
                                checkout_id = res.get("id", "")
                                # Salvar metadados de checkout para lembrete automático
                                save_metadata(lead_id, "checkout_id", checkout_id)
                                save_metadata(lead_id, "asaas_checkout_url", checkout_url)
                                save_metadata(lead_id, "checkout_sent_at", str(int(datetime.now().timestamp())))
                                save_metadata(lead_id, "followup_status", "0")
            except Exception:
                pass # Em caso de erro, usa o fallback CHECKOUT_LINK

        response += f"\n\n{format_checkout_message(checkout_url)}"
        mark_checkout_sent(lead_id)

    return response


def test_trigger():
    """Teste de trigger (para setup/test_agent.py)."""
    test_messages = [
        TRIGGER_EXACT,
        "Oi, tenho uma dúvida sobre o produto",
        "Não é trigger"
    ]

    print("Testando triggers:\n")
    for msg in test_messages:
        result = "✅ Detectado" if is_trigger(msg) else "❌ Ignorado"
        print(f"  \"{msg}\" → {result}")

    return True


def main():
    """Interface CLI para teste."""
    import argparse

    parser = argparse.ArgumentParser(description="Agente WhatsApp v1.0")
    parser.add_argument("--test", action="store_true", help="Testa triggers")
    parser.add_argument("--chat", type=str, help="Chat interativo com phone")

    args = parser.parse_args()

    # Inicializar DB
    init_db()

    if args.test:
        test_trigger()
    elif args.chat:
        # Chat interativo
        print(f"\n💬 Chat com {args.chat}")
        print("(Digite 'sair' para encerrar)\n")

        while True:
            msg = input("Você: ").strip()
            if msg.lower() == "sair":
                break

            response = handle_message(
                phone=args.chat,
                sender_name="Teste",
                text=msg
            )

            if response:
                print(f"Agente: {response}\n")
            else:
                print("(Mensagem ignorada — não contém trigger)\n")
    else:
        print("Use: python3 agent.py --test")
        print("     python3 agent.py --chat PHONE")


if __name__ == "__main__":
    main()
