#!/usr/bin/env python3
"""
watcher.py — Monitora WhatsApp via Evolution API e ativa agente de vendas

Poll a cada 3s na Evolution API local buscando mensagens novas.
Filtra grupos, mensagens próprias e formato LID.
Chama agent.handle_message() e envia resposta via Evolution API.

Execução:
  python3 watcher.py                    ← roda indefinidamente
  launchctl load ~/Library/LaunchAgents/com.meuagente.watcher.plist  ← auto-start macOS
"""

import json
import time
import logging
import sys
import traceback
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path.home() / "meu-agente" / "watcher.log")
    ]
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))
from agent import handle_message, is_trigger

# ── Configuração (preenchida pelo setup) ──────────────────────────────────────
EVOLUTION_URL = "http://localhost:8080"
EVOLUTION_API_KEY = "{{EVOLUTION_API_KEY}}"
INSTANCE_NAME = "meu-agente"
POLL_INTERVAL = 3  # segundos

STATE_FILE = Path.home() / "meu-agente" / "watcher_state.json"
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


# ── Evolution API ─────────────────────────────────────────────────────────────

def evolution_request(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    url = f"{EVOLUTION_URL}{endpoint}"
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data else None,
        headers=headers,
        method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        logger.error(f"Evolution API erro: {e}")
        return {}


def fetch_messages(count: int = 20) -> list:
    """Busca últimas mensagens da instância."""
    result = evolution_request(
        f"/chat/findMessages/{INSTANCE_NAME}",
        method="POST",
        data={"count": count}
    )
    # Evolution API v2: {"messages": {"records": [...], "total": N}}
    if isinstance(result, list):
        return result
    if isinstance(result, dict) and "messages" in result:
        messages_data = result["messages"]
        if isinstance(messages_data, dict):
            return messages_data.get("records", [])
        if isinstance(messages_data, list):
            return messages_data
    return []


def send_whatsapp(phone: str, message: str) -> bool:
    """Envia mensagem via Evolution API."""
    result = evolution_request(
        f"/message/sendText/{INSTANCE_NAME}",
        method="POST",
        data={"number": phone, "text": message}
    )
    success = bool(result.get("key") or result.get("id"))
    if success:
        logger.info(f"📤 Enviado para {phone}")
    else:
        logger.error(f"❌ Falha ao enviar para {phone}: {result}")
    return success


# ── Funções de Escrita Numérica por Extenso (Tratamento para ElevenLabs) ──────

def number_to_words(n: int) -> str:
    """Converte um número inteiro de até 999.999 em palavras em português."""
    if n == 0:
        return "zero"
        
    units = ["", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove"]
    teens = ["dez", "onze", "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
    tens = ["", "dez", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
    hundreds = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos", "oitocentos", "novecentos"]
    
    if n == 100:
        return "cem"
        
    words = []
    
    # Milhares
    thousands = n // 1000
    if thousands > 0:
        if thousands == 1:
            words.append("mil")
        else:
            words.append(number_to_words(thousands) + " mil")
        n = n % 1000
        if n > 0:
            if n < 100 or n % 100 == 0:
                words.append("e")
                
    # Centenas
    if n > 0:
        h = n // 100
        if h > 0:
            words.append(hundreds[h])
            n = n % 100
            if n > 0:
                words.append("e")
                
    # Dezenas e Unidades
    if n > 0:
        if 10 <= n < 20:
            words.append(teens[n - 10])
        else:
            t = n // 10
            u = n % 10
            if t > 0:
                words.append(tens[t])
                if u > 0:
                    words.append("e")
            if u > 0:
                words.append(units[u])
                
    return " ".join(words)


def price_to_words(price_str: str) -> str:
    """Converte uma string contendo valor monetário (R$ ou BRL) em reais escritos por extenso."""
    price_str = price_str.replace("R$", "").replace("BRL", "").replace("Brl", "").replace("brl", "").replace(" ", "")
    
    if "," in price_str:
        parts = price_str.split(",")
        reais_str = "".join(filter(str.isdigit, parts[0]))
        cents_str = "".join(filter(str.isdigit, parts[1]))[:2]
    elif "." in price_str and len(price_str.split(".")[-1]) == 2:
        parts = price_str.split(".")
        reais_str = "".join(filter(str.isdigit, parts[0]))
        cents_str = "".join(filter(str.isdigit, parts[1]))
    else:
        reais_str = "".join(filter(str.isdigit, price_str))
        cents_str = "0"
        
    try:
        reais = int(reais_str) if reais_str else 0
        cents = int(cents_str) if cents_str else 0
        if len(cents_str) == 1 and cents_str != "0":
            cents = cents * 10
    except Exception:
        return price_str
        
    reais_word = "real" if reais == 1 else "reais"
    cents_word = "centavo" if cents == 1 else "centavos"
    
    result = []
    if reais > 0:
        result.append(f"{number_to_words(reais)} {reais_word}")
    if cents > 0:
        if reais > 0:
            result.append("e")
        result.append(f"{number_to_words(cents)} {cents_word}")
        
    if not result:
        return "zero reais"
        
    return " ".join(result)


def preprocess_text_for_tts(text: str) -> str:
    """Prepara o texto para ser falado de forma perfeita, pausada e sem erros de números ou símbolos."""
    import re
    
    # Substituir símbolos indesejados comuns no chat de medidas
    text = text.replace("+", " e ").replace(" x ", " por ").replace(" X ", " por ")
    
    # 1. Substituir preços por extenso em português (formatos R$ 147,39 ou 147,39 BRL)
    pattern_price_rs = r"R\$\s*(\d+(?:[\.,]\d+)*)"
    text = re.sub(pattern_price_rs, lambda m: price_to_words(m.group(0)), text)
    
    pattern_price_brl = r"(\d+(?:[\.,]\d+)*)\s*(?:BRL|Brl|brl)\b"
    text = re.sub(pattern_price_brl, lambda m: price_to_words(m.group(0)), text)
    
    # 2. Substituir decimais de tamanho soltos por extenso (ex: 1.50 ou 1,50 ou 2.25)
    def decimal_replacer(match):
        reais_part = int(match.group(1))
        cents_part = int(match.group(2))
        return f"{number_to_words(reais_part)} e {number_to_words(cents_part)}"
        
    text = re.sub(r"\b(\d+)[.,](\d{2})\b", decimal_replacer, text)
    
    # 3. Adicionar reticências (...) para forçar pausas de respiração naturais do modelo nas pontuações
    text = text.replace(", ", ", ... ")
    text = text.replace(". ", ". ... ")
    text = text.replace("! ", "! ... ")
    text = text.replace("? ", "? ... ")
    
    return text


def send_whatsapp_audio_elevenlabs(phone: str, message: str) -> bool:
    """Converte texto para áudio usando ElevenLabs API (retorna False se não houver chave ou se falhar)."""
    import base64
    import tempfile
    import os
    
    try:
        # 1. Carregar chave e voz do config.json
        p_conf = Path.home() / ".meu-agente" / "config.json"
        if not p_conf.exists():
            return False
            
        config_data = json.loads(p_conf.read_text(encoding="utf-8"))
        eleven_key = config_data.get("elevenlabs_api_key", "")
        # Usar voz padrão "Rachel" (21m00Tcm4TlvDq8ikWAM) se não houver outra configurada
        voice_id = config_data.get("elevenlabs_voice_id", "21m00Tcm4TlvDq8ikWAM")
        
        if not eleven_key:
            return False  # Sem chave, força fallback para gTTS sem erro
            
        # Pré-processar o texto para expandir preços por extenso e adicionar pausas de respiração!
        message_clean = preprocess_text_for_tts(message)
            
        # 2. Chamar ElevenLabs API
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        payload = {
            "text": message_clean,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.85,
                "similarity_boost": 0.85
            }
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "xi-api-key": eleven_key,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            method="POST"
        )
        
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            temp_path = f.name
            
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                with open(temp_path, "wb") as f_out:
                    f_out.write(r.read())
                    
            # 3. Converter para base64 e enviar via sendMedia
            with open(temp_path, "rb") as audio_file:
                audio_base64 = base64.b64encode(audio_file.read()).decode("utf-8")
                
            result = evolution_request(
                f"/message/sendMedia/{INSTANCE_NAME}",
                method="POST",
                data={
                    "number": phone,
                    "mediatype": "audio",
                    "media": audio_base64,
                    "fileName": "audio.mp3"
                }
            )
            success = bool(result.get("key") or result.get("id"))
            if success:
                logger.info(f"📤 Áudio ElevenLabs enviado com sucesso para {phone}")
                return True
            else:
                logger.error(f"❌ Falha ao enviar áudio ElevenLabs para {phone}: {result}")
                return False
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    except Exception as e:
        logger.error(f"Erro ao gerar/enviar áudio ElevenLabs para {phone}: {e}")
        return False


def send_whatsapp_audio(phone: str, message: str) -> bool:
    """Converte texto para áudio e envia como áudio do WhatsApp, utilizando EXCLUSIVAMENTE a ElevenLabs."""
    # Tentar com ElevenLabs. Se falhar ou não houver chave, retorna False para forçar o envio em texto!
    return send_whatsapp_audio_elevenlabs(phone, message)


# ── Extração de mensagens ─────────────────────────────────────────────────────

def extract_message_data(msg) -> dict:
    """Extrai phone, nome e texto de uma mensagem da Evolution API."""
    if not isinstance(msg, dict):
        return {}

    key = msg.get("key", {})
    if not isinstance(key, dict):
        return {}

    # Ignorar mensagens enviadas por nós
    if key.get("fromMe", False):
        return {}

    remote_jid = key.get("remoteJid", "")

    # Ignorar grupos
    if "@g.us" in remote_jid:
        return {}

    # LID format (novo endereçamento WhatsApp): usar remoteJidAlt com número real
    if key.get("addressingMode") == "lid" and key.get("remoteJidAlt"):
        phone = key["remoteJidAlt"].replace("@s.whatsapp.net", "")
    else:
        phone = remote_jid.replace("@s.whatsapp.net", "").replace("@lid", "")

    push_name = msg.get("pushName", "Lead")

    # Extrair texto de diferentes formatos de mensagem
    message_content = msg.get("message", {})
    if not isinstance(message_content, dict):
        return {}

    is_audio = "audioMessage" in message_content

    text = (
        message_content.get("conversation") or
        (message_content.get("extendedTextMessage") or {}).get("text") or
        ""
    )

    return {
        "id": key.get("id", ""),
        "phone": phone,
        "name": push_name,
        "text": text.strip(),
        "is_audio": is_audio,
    }


# ── State ─────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"seen_ids": [], "last_run": None}


def save_state(state: dict):
    state["last_run"] = datetime.now().isoformat()
    # Manter apenas os últimos 500 IDs para não crescer indefinidamente
    if len(state["seen_ids"]) > 500:
        state["seen_ids"] = state["seen_ids"][-500:]
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ── Lembretes de Pagamento / Cobrança Ativa (Asaas) ──────────────────────────

def check_asaas_payment_status(payment_link_id: str) -> str:
    """
    Verifica se o link de pagamento Asaas foi pago.
    Retorna: 'PAID' (pago), 'PENDING' (pendente), ou 'NONE' (nenhuma tentativa/pago).
    """
    try:
        p_conf = Path.home() / ".meu-agente" / "config.json"
        if not p_conf.exists():
            return "NONE"
            
        config_data = json.loads(p_conf.read_text(encoding="utf-8"))
        asaas_token = config_data.get("asaas_api_key", "")
        if not asaas_token:
            return "NONE"
            
        url = f"https://api.asaas.com/v3/payments?paymentLink={payment_link_id}"
        req = urllib.request.Request(
            url,
            headers={
                "Content-Type": "application/json",
                "access_token": asaas_token
            },
            method="GET"
        )
        
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read().decode("utf-8"))
            payments = res.get("data", [])
            if not payments:
                return "NONE"
                
            for p in payments:
                status = p.get("status", "")
                if status in ["RECEIVED", "CONFIRMED"]:
                    return "PAID"
                    
            return "PENDING"
    except Exception as e:
        logger.error(f"Erro ao verificar pagamento Asaas para o link {payment_link_id}: {e}")
        return "NONE"


def process_payment_followups():
    """Varre leads e processa lembretes de cobrança ativa de forma assíncrona/periódica."""
    try:
        import sessions
        conn = sessions._db()
        cursor = conn.cursor()
        
        # Buscar leads que receberam checkout
        cursor.execute("SELECT id, phone, name FROM leads WHERE sent_checkout = 1")
        leads_rows = cursor.fetchall()
        conn.close()
        
        now_ts = int(time.time())
        
        for lead in leads_rows:
            lead_id = lead["id"]
            phone = lead["phone"]
            name = lead["name"]
            
            checkout_id = sessions.get_metadata(lead_id, "checkout_id")
            checkout_sent_at_str = sessions.get_metadata(lead_id, "checkout_sent_at")
            followup_status = sessions.get_metadata(lead_id, "followup_status", "0")
            
            if not checkout_id or not checkout_sent_at_str or followup_status == "PAID":
                continue
                
            # 1. Verificar se já foi pago na Asaas
            payment_status = check_asaas_payment_status(checkout_id)
            if payment_status == "PAID":
                sessions.save_metadata(lead_id, "followup_status", "PAID")
                logger.info(f"🎉 Pagamento confirmado para o lead {name} ({phone})!")
                send_whatsapp(phone, f"Oba, {name}! 🎉 Confirmamos o recebimento do seu pagamento. O seu pedido de cortinas/persianas sob medida já foi encaminhado para o nosso setor de fabricação! Em breve te enviaremos o código de rastreamento por aqui. Qualquer dúvida, estou à disposição! 💪")
                continue
                
            # 2. Se não foi pago, calcular o tempo decorrido e enviar lembrete correspondente
            checkout_sent_at = int(checkout_sent_at_str)
            elapsed = now_ts - checkout_sent_at
            
            # Lembrete de Distração (Após 2 Horas / 7200 segundos)
            if elapsed >= 7200 and followup_status == "0":
                sessions.save_metadata(lead_id, "followup_status", "1")
                logger.info(f"⏳ Enviando lembrete de cobrança (2 horas) para {name} ({phone})")
                msg_2h = f"Olá, {name}! Vi que o seu link de checkout seguro para as persianas já está pronto, mas o pagamento ainda não foi confirmado. Ficou alguma dúvida ou precisa de ajuda para finalizar? 😊"
                send_whatsapp(phone, msg_2h)
                
            # Lembrete de Escassez / Fila da Fábrica (Após 24 Horas / 86400 segundos)
            elif elapsed >= 86400 and followup_status == "1":
                sessions.save_metadata(lead_id, "followup_status", "2")
                logger.info(f"⏳ Enviando lembrete de cobrança (24 horas) para {name} ({phone})")
                checkout_url = sessions.get_metadata(lead_id, "asaas_checkout_url", "agilcortinasepersianas.com.br/loja")
                msg_24h = f"Olá, {name}! Passando para lembrar que o lote de produção da nossa fábrica fecha hoje. Se você quiser garantir que as suas persianas entrem na fabricação desta semana para chegarem o quanto antes, basta finalizar o pagamento pelo link seguro: {checkout_url} 🚀"
                send_whatsapp(phone, msg_24h)
                
    except Exception as e:
        logger.error(f"Erro no processamento de followups de cobrança: {e}\n{traceback.format_exc()}")


# ── Transcrição de Áudio (Whisper) ───────────────────────────────────────────

def transcribe_audio_base64(base64_str: str) -> str:
    """Transcreve um áudio em base64 usando o Groq ou OpenAI Whisper API."""
    import base64
    import tempfile
    import os
    
    try:
        # Carregar chaves do ~/.config/watch/.env se disponíveis
        watch_env_path = Path.home() / ".config" / "watch" / ".env"
        groq_key = ""
        openai_key = ""
        
        if watch_env_path.exists():
            for line in watch_env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("GROQ_API_KEY="):
                    groq_key = line.split("=", 1)[1].strip()
                elif line.startswith("OPENAI_API_KEY="):
                    openai_key = line.split("=", 1)[1].strip()
                    
        # Configurar endpoints e modelo
        if groq_key:
            api_url = "https://api.groq.com/openai/v1/audio/transcriptions"
            api_key = groq_key
            model = "whisper-large-v3"
        elif openai_key:
            api_url = "https://api.openai.com/v1/audio/transcriptions"
            api_key = openai_key
            model = "whisper-1"
        else:
            # Se não houver no watch, tenta usar a ai_api_key do config.json como fallback
            p_conf = Path.home() / ".meu-agente" / "config.json"
            if p_conf.exists():
                config_data = json.loads(p_conf.read_text(encoding="utf-8"))
                # Pega a chave OpenAI se houver (mas de forma genérica)
                openai_key = config_data.get("ai_api_key", "")
                if openai_key and len(openai_key) > 30: # Evitar chaves curtas
                    api_url = "https://api.openai.com/v1/audio/transcriptions"
                    api_key = openai_key
                    model = "whisper-1"
                else:
                    logger.warning("Nenhuma chave de Whisper (Groq/OpenAI) disponível.")
                    return ""
            else:
                logger.warning("Nenhuma chave de Whisper encontrada.")
                return ""
            
        audio_data = base64.b64decode(base64_str)
        
        # Fazer a requisição multipart POST manual com urllib
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        parts = []
        
        parts.append(f"--{boundary}")
        parts.append('Content-Disposition: form-data; name="model"')
        parts.append("")
        parts.append(model)
        
        parts.append(f"--{boundary}")
        parts.append('Content-Disposition: form-data; name="file"; filename="audio.mp3"')
        parts.append("Content-Type: audio/mpeg")
        parts.append("")
        
        body_bytes = b""
        for part in parts:
            body_bytes += part.encode("utf-8") + b"\r\n"
            
        body_bytes += audio_data + b"\r\n"
        body_bytes += f"--{boundary}--\r\n".encode("utf-8")
        
        req = urllib.request.Request(
            api_url,
            data=body_bytes,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.loads(r.read().decode("utf-8"))
            return res.get("text", "")
    except Exception as e:
        logger.error(f"Erro ao transcrever áudio Whisper: {e}")
        return ""


# ── Loop principal ────────────────────────────────────────────────────────────

def watch():
    logger.info("🔍 Watcher iniciado")
    state = load_state()
    iteration_counter = 0
    first_run = True

    while True:
        try:
            # Processar lembretes de pagamento a cada 200 iterações (aproximadamente a cada 10 minutos)
            if iteration_counter % 200 == 0:
                process_payment_followups()
            iteration_counter += 1

            messages = fetch_messages(count=20)

            # Ignorar mensagens históricas na primeira execução para evitar flood/travamento da API do Gemini
            if first_run:
                for msg in messages:
                    msg_data = extract_message_data(msg)
                    if msg_data and msg_data.get("id"):
                        if msg_data["id"] not in state["seen_ids"]:
                            state["seen_ids"].append(msg_data["id"])
                save_state(state)
                first_run = False
                logger.info("✅ Mensagens do histórico ignoradas com sucesso na inicialização.")
                time.sleep(POLL_INTERVAL)
                continue

            for msg in messages:
                msg_data = extract_message_data(msg)
                if not msg_data or not msg_data.get("phone"):
                    continue

                msg_id = msg_data["id"]
                if msg_id in state["seen_ids"]:
                    continue

                state["seen_ids"].append(msg_id)
                phone = msg_data["phone"]
                name = msg_data["name"]
                text = msg_data["text"]
                is_audio = msg_data.get("is_audio", False)

                # Se for mensagem de áudio, baixar e transcrever
                if is_audio:
                    logger.info(f"🎤 {name} ({phone}) enviou um áudio. Baixando e transcrevendo...")
                    media_res = evolution_request(
                        f"/chat/getBase64FromMediaMessage/{INSTANCE_NAME}",
                        method="POST",
                        data={
                            "message": {
                                "key": {
                                    "id": msg_id
                                }
                            },
                            "convertToMp3": True
                        }
                    )
                    base64_audio = media_res.get("base64")
                    if base64_audio:
                        transcribed_text = transcribe_audio_base64(base64_audio)
                        if transcribed_text:
                            text = transcribed_text
                            logger.info(f"🎤 Áudio Transcrito: {text}")
                        else:
                            logger.warning("❌ Falha ao transcrever o áudio.")
                            send_whatsapp(phone, "Desculpe, não consegui compreender o seu áudio. Você poderia digitar ou enviar novamente? 😊")
                            continue
                    else:
                        logger.error("❌ Falha ao obter base64 do áudio da Evolution API.")
                        continue

                # Se após processamento de áudio o texto estiver vazio, ignora
                if not text.strip():
                    continue

                logger.info(f"📩 {name} ({phone}): {text[:60]}")

                try:
                    response = handle_message(phone, name, text)
                    if response:
                        if is_audio:
                            logger.info(f"📤 Gerando e enviando resposta em áudio para {phone}...")
                            audio_success = send_whatsapp_audio(phone, response)
                            if not audio_success:
                                # Fallback para texto se falhar
                                send_whatsapp(phone, response)
                        else:
                            send_whatsapp(phone, response)
                    else:
                        logger.debug("⏭️  Não é trigger — ignorado")
                except Exception as e:
                    logger.error(f"Erro ao processar mensagem: {e}\n{traceback.format_exc()}")

            save_state(state)
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            logger.info("⏹️  Watcher encerrado")
            break
        except Exception as e:
            logger.error(f"Erro no loop: {e}\n{traceback.format_exc()}")
            time.sleep(5)


if __name__ == "__main__":
    watch()
