---
name: agente-vendas-whatsapp
description: Manage, configure, update, test, and debug the WhatsApp Sales Agent for Ágil Cortinas e Persianas. Use this skill whenever the user mentions adjusting the WhatsApp bot, changing pricing, modifying the System Prompt, fixing Evolution API, updating Frenet shipping or Asaas checkouts, restarting the watcher, or managing conversational sales logic.
---

# WhatsApp Sales Agent - Management Skill

This skill provides comprehensive instructions on how to manage, configure, update, test, and debug the WhatsApp Sales Agent for **Ágil Cortinas e Persianas**.

## 🗺️ Repository and System Architecture

### ⚠️ PRODUCTION RUNS ON A HOSTINGER VPS (since 2026-07-28) — NOT on the user's Windows machine
The live 24/7 agent runs on **VPS `179.198.100.135`** (Ubuntu 24.04, user `root`), NOT on the Windows box. The Windows copy in `C:\Users\fmtol\meu-agente\` is now only a **staging/dev mirror** — editing it does nothing to production. Always deploy to the VPS (see section 8).

- **Production files:** `/root/meu-agente/` (`agent.py`, `agent_core.py`, `sessions.py`, `watcher.py`, `.env`)
- **Production config:** `/root/.meu-agente/config.json`
- **Process manager:** systemd unit `meu-agente-watcher.service` (`enabled`, `Restart=always`, survives reboot). Logs to `/root/meu-agente/watcher.log` and `/root/meu-agente/watcher_service.log`.
- **Evolution API:** Docker Compose stack at `/docker/evolution-api-9ic2/` (containers `evolution-api-9ic2-api-1`, `-postgres-1`, `-redis-1`, plus a Traefik reverse proxy).
  - **Always address it by the stable public URL `https://evolution-api-9ic2.srv1861235.hstgr.cloud`** — NOT `localhost:PORT`. Docker reassigns the ephemeral host port (it went 32768 → 32769 after a single `docker compose up -d api`), which silently breaks the agent with `Connection refused`. The Traefik-routed domain never changes.
  - Instance name: **`agente-agil`** (WhatsApp number `554831999811`). API key lives in `/docker/evolution-api-9ic2/.env` as `API_KEY=`, injected into the container as `AUTHENTICATION_API_KEY`.
- **Local dev mirror (Windows):** `C:\Users\fmtol\meu-agente\` + `~/.meu-agente/config.json`. Useful for regenerating files via `setup/generate_meu_agente.py`, but **must then be pushed to the VPS**.

### Local Staging Folder (Windows dev mirror)
Files in `C:\Users\fmtol\meu-agente\`:
- `agent.py`: Handles message processing, dimension extraction, Fácil Persianas pricing calculations, CEP extraction, Frenet shipping queries, and triggers Asaas API checkout links.
- `agent_core.py`: Stores the core `SYSTEM_PROMPT` containing the uncurated BANT sales flow and product manual.
- `sessions.py`: Manages SQL schema, lead tracking, and `session_metadata` (width, height, cep, checkout_id, followup_status).
- `watcher.py`: Continuous poller of the Evolution API. Translates incoming voice messages via Whisper and generates voice replies via gTTS. Runs background payment reminders.
- `.env`: System credentials.

### Template and Repository Folder
The repository is located at `C:\users\fmtol\agente-ia-vendas\agente-ia-vendas\`.
Templates are compiled using placeholder replacements (`{{AI_API_KEY}}`, etc.) and copied to the local production folder:
- `templates/shared/agent_core_template.py` -> `meu-agente/agent_core.py`
- `templates/shared/sessions_template.py` -> `meu-agente/sessions.py`
- `templates/whatsapp/agent_template.py` -> `meu-agente/agent.py`
- `templates/whatsapp/watcher_template.py` -> `meu-agente/watcher.py`

---

## 🛠️ Operational Workflows

### 1. Updating the System Prompt or Pricing
The canonical source of the prompt is the `SYSTEM_PROMPT = """..."""` block in `templates/shared/agent_core_template.py`. `config.json`'s `"system_prompt"` is a *copy* consumed by the generator — keep them in sync or the next regeneration silently reverts your edit.
1. Edit `SYSTEM_PROMPT` in `templates/shared/agent_core_template.py`.
2. Sync it into `~/.meu-agente/config.json` (regex-extract the triple-quoted block and write it to `cfg["system_prompt"]`).
3. Run `python setup/generate_meu_agente.py` to rebuild the Windows staging copy.
4. **Deploy to the VPS (section 8)** — steps 1–3 alone do NOT touch production.
5. Restart the systemd service (section 6).

### 2. BANT Prompt Constraints & Rules
When modifying the prompt, ALWAYS enforce:
- **NO COMPETITOR MENTION:** NEVER mention "Fácil Persianas". Use "nossa fábrica" or "Ágil Persianas".
- **NO REGIONAL MENTION:** NEVER say the factory is in Juiz de Fora (MG). Delivery is nationwide.
- **ONE QUESTION AT A TIME:** The agent must ask exactly one question per message and wait for the response (cadenced flow).
- **5% PIX DISCOUNT:** Always offer 5% discount on PIX payments and show the calculated discounted price.
- **⚠️ ONLY RECOMMEND PRODUCTS THE STORE ACTUALLY SELLS — VERIFY AGAINST `agilcortinasepersianas.com.br/loja` BEFORE ADDING ANY PRODUCT ADVICE:** The catalog is **exclusively blinds/persianas**: Rolô, Romana, Double Vision, Painel, Horizontal (Alumínio/PVC/Madeira Sintética), Tela Mosquiteira, Toldos — each with the 🧵 variations listed in the prompt. **They do NOT sell fabric curtains** — no voil, linho, microfibra, or veludo. This bit once already: on 2026-07-28 the client pasted a well-researched "Guia de Decisão por Ambiente" (sourced from Westwing, Uniflex, Portal Loft, etc.) whose top recommendation for a social living room was *"cortina de voil, linho ou microfibra"* and for thermal insulation *"veludo"* — all products that would have been recommended to real leads and could not be fulfilled. It was caught by fetching the live store before shipping. **Mapping used when adapting generic interior-design advice to this catalog:** light/luminous/decorative fabric → **Rolô or Romana Translúcida**; heavy thermal fabric (veludo) → **Blackout Vedação Total**; large spans / sliding doors → **Painel**. The prompt also carries an explicit rule telling the agent what to say if a lead asks for voil/linho/veludo by name (offer Translúcida as the closest in-catalog equivalent).
- **MEASUREMENT MANUALS:** Understand and explain standard wall installation (+10-15cm on all sides), sanca/plaster installation (-1cm width, +10-15cm height), and side-by-side split (width / 2 with a 3cm gap warning).
- **PRICING IS INTENTIONALLY "FÁCIL PERSIANAS" PRICING — DO NOT "FIX" IT:** `agent.py`'s hardcoded per-m² prices (R$ 147.39 for Rolô Blackout/Double Vision, R$ 186.44 for Rolô Tela Solar, comment literally says `# Preços Fácil Persianas`) look at first glance like a copy-paste bug from a competitor's project, especially since the real prices listed on `agilcortinasepersianas.com.br/loja` are 2-4x higher (e.g. Rolô Blackout Texturizado is R$336.71/m² on the live site, not R$147.39). **This is confirmed intentional** — the client explicitly said (2026-07-25) "nossos preços são os mesmos deles" (our prices are the same as theirs) and that this stays the source of truth **until they send an explicit price table**. A model-detection rewrite (mapping each of the new 🧵 tecido variants to real site prices) was built, tested, and then explicitly reverted at the client's request — do not reintroduce it without a fresh, explicit go-ahead. If the client ever does send a price table, update the two hardcoded multipliers (and mirror in `templates/whatsapp/agent_template.py`) rather than scraping the live site again.

### 3. Database & SQL Integrity
- The `leads` table uses exactly **11 bindings** in the `create_lead` SQL insert query inside `sessions.py`. Ensure `now` is supplied for both `created_at` and `updated_at`.
- Use the `session_metadata` table to persist: `width`, `height`, `cep`, `checkout_id`, `asaas_checkout_url`, `checkout_sent_at`, and `followup_status` ("0", "1", "2", "PAID").

### 4. Audio Transcription and TTS Replies
- **Whisper Transcription:** Audio messages are fetched in Base64 via `POST /chat/getBase64FromMediaMessage/{instance}` and transcribed with Whisper (Groq's `whisper-large-v3` preferred, `OPENAI_API_KEY`/`whisper-1` as second choice). You MUST include `"User-Agent": "Mozilla/5.0 ..."` in headers of urllib requests to Groq (`api.groq.com`) to bypass Cloudflare Error 403.
  - **Key lookup order (fixed 2026-07-28):** `~/.config/watch/.env` first, then `groq_api_key`/`openai_api_key` in `~/.meu-agente/config.json`. The `.env` belongs to an unrelated tool and **does not exist on the VPS**, so for months on the server every customer voice note silently produced "Desculpe, não consegui compreender o seu áudio" — the config.json fallback is what makes transcription work in production. When deploying to a new host, put the Groq key in `config.json`, not in the stray `.env`.
  - **ElevenLabs is NOT a substitute** — it only does text→speech. Transcription (speech→text) requires Groq or OpenAI Whisper. Clients conflate the two; state the difference plainly.
  - **Fixed bug (2026-07-25):** the last-resort fallback used to reuse `config.json`'s `ai_api_key` as if it were always an OpenAI key whenever it was >30 chars — but that key is whatever `AI_PROVIDER` is currently set to (Anthropic/Gemini/OpenAI). Since the client runs Anthropic, this silently sent an `sk-ant-...` key as a Bearer token to `api.openai.com`, which 401s every time (audio replies would then just fail with "não consegui compreender seu áudio"). Now gated on `config_data.get("ai_provider") == "openai"` before reusing that key — in `watcher.py` and `templates/whatsapp/watcher_template.py`.
- **Voice Response Synthesis:** Despite this file's older text and the `send_whatsapp_audio` docstring history mentioning `gTTS`, the **live code as of 2026-07-25 uses ElevenLabs exclusively** (`send_whatsapp_audio()` → `send_whatsapp_audio_elevenlabs()`, no gTTS fallback path exists anymore). Reads `elevenlabs_api_key`/`elevenlabs_voice_id` from `config.json` (default voice `21m00Tcm4TlvDq8ikWAM` "Rachel"), preprocesses text via `preprocess_text_for_tts()` (spells out `R$`/decimal values by extenso in Portuguese, adds `...` pauses after punctuation) before calling `POST /v1/text-to-speech/{voice_id}`, then sends the MP3 as base64 via `POST /message/sendMedia/{instance}` with `"mediatype": "audio"`. If `elevenlabs_api_key` is missing, it returns `False` and the caller falls back to a plain text WhatsApp reply — there's no automatic TTS provider fallback anymore.

### 5. Automatic Payment Reminders (Cobrança Ativa)
- The background task `process_payment_followups()` runs periodically in `watcher.py` (every 200 iterations / 10 minutes, including once immediately on startup since `iteration_counter` starts at 0).
- It checks Asaas payment status using `GET /v3/payments?paymentLink={checkout_id}`.
- If unpaid, it sends a 2-hour friendly distraction reminder and a 24-hour scarcity/urgency reminder. If paid, it updates `followup_status` to `"PAID"` and sends a beautiful confirmation.
- Leads currently flagged `human_handoff == "1"` are skipped entirely (see section 9) — no automated nagging while a human is handling the conversation.
- **Fixed bug (2026-07-27):** `followup_status` used to be written **before** `send_whatsapp()`, so a transient Evolution API failure (timeout / HTTP 400) marked the reminder as sent when it never left — that lead then never got a 2h reminder *and* never advanced to the 24h one. Observed live in the log on 2026-07-27 08:39 for lead Fernando. Now `sessions.save_metadata(...)` only runs inside `if send_whatsapp(...):`, so a failure simply retries on the next 10-minute cycle. Keep this shape when editing.
- **Known quirk (not yet fixed, low severity):** the 2h/24h checks are `if elapsed >= 7200 and status == "0"` then `elif elapsed >= 86400 and status == "1"`. If the watcher is down/restarted across the entire 2h–24h window (so the 2h reminder never fired), the next run sees `elapsed >= 86400` but `status` still `"0"`, takes the **first** branch, and sends the "2 hour, need help?" wording ~24h+ late instead of the urgency one — it self-corrects and sends the correct 24h message ~10 minutes later on the following run. Cosmetic (wrong tone once), not a functional loss — mention if a client asks why a lead got two reminder messages close together.

### 6. Restarting the Watcher Service (VPS / systemd)
Whenever production code (`agent.py`, `watcher.py`, etc.) is updated on the VPS, restart the service:
```
systemctl restart meu-agente-watcher
systemctl is-active meu-agente-watcher
tail -n 20 /root/meu-agente/watcher.log
```
Systemd guarantees a single instance, so the old Windows concern about duplicate pollers double-replying no longer applies — but never *also* launch `python3 watcher.py` by hand alongside the service, which recreates exactly that problem.

**⚠️ Restarting can silently swallow an unanswered lead message.** `watch()` loads `watcher_state.json` once at start, then on its very first poll iteration marks every message currently in the last-20-messages window as "seen" **without replying** (anti-flood-on-boot logic) before switching to normal mode. If a customer's message arrives in the window between "last processed" and "watcher back up", it gets marked seen and never answered — and you won't see an error, just silence. Editing `seen_ids` in `watcher_state.json` on disk does **not** fix an already-running process (state is loaded once into memory, and any `save_state()` call overwrites your edit with the in-memory copy). If you suspect a message got swallowed, check `POST /chat/findMessages/{instance}` on the Evolution API directly for the timestamp, and just ask the user to resend — don't restart again to "retry", it repeats the same swallow.

### 7. Windows-Specific Gotchas (encoding, config drift, provider bugs)
- **UTF-8 console/log encoding:** Every `setup/*.py` script and `watcher.py` must reconfigure stdout/stderr to UTF-8 on Windows (`if sys.platform == "win32": sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")`, placed right after the imports) and `logging.FileHandler(...)` must be given `encoding="utf-8"` explicitly. Without this, any print/log containing emoji (✅, 🔍, etc.) crashes with `UnicodeEncodeError` on the default `cp1252` codepage. This fix now lives in all `setup/*.py` files and in both `watcher.py` and `templates/whatsapp/watcher_template.py` — keep it when regenerating.
- **`connect_whatsapp.py` QR display:** Evolution API's `/instance/connect/{instance}` response has two QR fields: `code` (raw pairing string — feed this to the `qrcode` library for ASCII terminal rendering) and `base64` (a ready-made PNG data URL — only useful for `show_qr_image`/opening as a file). The old code tried to `base64.b64decode(...).decode("utf-8")` the PNG bytes as if they were the raw pairing text, which always throws `UnicodeDecodeError` (PNG magic byte `0x89` isn't valid UTF-8). Fixed: `show_qr_terminal` now takes the raw `code` string directly; `display_qr(qr_code_raw, qr_base64)` picks whichever is available. If a user says the ASCII QR "doesn't scan" in their terminal, fall back to `show_qr_image(qr_base64)` directly (opens as a Windows image file, much easier to scan than tiny terminal glyphs).
- **Config drift between `config.json` and the generated agent:** `AI_PROVIDER` / `AI_MODEL` / `AI_API_KEY` are baked as hardcoded constants at the top of `meu-agente/agent_core.py` (and mirrored in `meu-agente/.env`, though `.env` is NOT read at runtime by `agent_core.py`). Updating `~/.meu-agente/config.json` alone (e.g. via `config_manager.save()`) does **nothing** to the live agent — you must edit `agent_core.py`'s `AI_PROVIDER`/`AI_MODEL`/`AI_API_KEY` constants directly (or regenerate from `agent_core_template.py`), update `.env` for consistency, and then restart the watcher (section 6). Always verify by grepping `agent_core.py` for these constants before assuming a provider/key swap took effect — this exact drift once left an agent running on a stale Gemini key for a day after the user had switched to Anthropic in the setup conversation.
- **Anthropic 400 Bad Request from `[SISTEMA: ...]` price/shipping injections:** `agent.py`'s `handle_message()` injects dynamic pricing/shipping instructions as `{"role": "system", "content": ...}` **inside** the `messages` list (see step 4 in section 1, `prompt_injection`). OpenAI and Gemini's OpenAI-compatible endpoint both accept a `system`-role message anywhere in the array, but **Anthropic's `/v1/messages` only accepts `user`/`assistant` roles in `messages`** — a `system` entry there causes an HTTP 400. Because `call_anthropic()` used to swallow `HTTPError` into `f"Erro Anthropic: {e.reason}"` and return it as the chat reply, this bug shipped the literal string **"Erro Anthropic: Bad Request" straight to the customer on WhatsApp** whenever a lead had already given measurements (which is exactly when the price injection fires). Fixed in `agent_core.py`/`agent_core_template.py`: `call_anthropic()` now strips any `role: "system"` entries out of `messages` and folds their content into the top-level `system` parameter instead, and on any remaining API error it logs `e.code`/`e.reason`/the response body via `print()` and returns a graceful Portuguese fallback ("Desculpe, tive um probleminha técnico...") instead of leaking the raw error to the lead. When debugging "the agent sent a weird/technical message to a customer," always suspect this pattern first — reproduce with `handle_message(phone, name, text)` directly against the customer's real phone number (their saved session/metadata is often what triggers provider-specific edge cases that a fresh test number won't hit).
- **Verified working model string:** `claude-opus-4-6` (tested live against the real Anthropic API on 2026-07-25) — use this unless the user asks for a different Claude model.

### 8. Deploying to the VPS
There is no git-based deploy — files are pushed over SFTP with `paramiko` (install with `python -m pip install paramiko`; there is no `sshpass`/`plink` on the Windows box).

Deploy shape that works (a reusable script lives in the session scratchpad as `deploy_handoff_to_vps.py`):
1. Read each template, substitute placeholders from `~/.meu-agente/config.json` (`{{AI_PROVIDER}}`, `{{AI_MODEL}}`, `{{AI_API_KEY}}`, `{{CHECKOUT_LINK}}`, `{{SYSTEM_PROMPT}}`, `{{TRIGGER_EXACT}}`, `{{PRODUCT_NAME}}`, `{{EVOLUTION_API_KEY}}`, `{{OWNER_PHONE}}`) plus the VPS-specific `EVOLUTION_URL`/`INSTANCE_NAME` line rewrites.
2. Rewrite `agent.py`'s shared-template imports to local module names (`agent_core_template` → `agent_core`, `sessions_template` → `sessions`).
3. SFTP-write to `/root/meu-agente/` and `/root/.meu-agente/config.json`.
4. `systemctl restart meu-agente-watcher`, then verify with `systemctl is-active` + `tail watcher.log`.

**Gotchas:**
- Always run deploy/diagnostic scripts with `PYTHONIOENCODING=utf-8` — printing `✅`/emoji from a Python script on this Windows box otherwise dies with `UnicodeEncodeError: 'charmap' codec`.
- Keep `templates/`, the Windows mirror, **and** `/root/meu-agente/` in sync. A fix applied to only one of the three is the single most common way work here gets silently lost.

### 9. Human Handoff (added 2026-07-28)
When a lead asks for a human, the agent steps aside instead of talking over the operator.
- **Detection:** `is_handoff_request(text)` in `agent_core_template.py` — keyword list ("falar com atendente", "quero um vendedor", "isso é um robô", etc.).
- **Behavior:** `check_human_handoff()` in `watcher_template.py` runs **before** `handle_message()` in the poll loop. On a new request it sets metadata `human_handoff="1"` (+ `human_handoff_at`), replies to the lead ("já vou te conectar com um de nossos atendentes"), and notifies `OWNER_PHONE`. While flagged, every further message from that lead is logged and skipped — the AI stays silent, and payment follow-ups skip them too.
- **⚠️ No automatic timeout — this is deliberate.** A 24h auto-resume existed briefly and the client explicitly asked for it to be removed on 2026-07-28 ("retirar esse recurso de espera por enquanto"). A flagged lead stays paused until someone clears it manually. Do not reintroduce a timeout without a fresh explicit request.
- **Clearing the flag manually** (on the VPS, from `/root/meu-agente`):
  ```
  python3 -c "import sessions; sessions.save_metadata('whatsapp_<PHONE>', 'human_handoff', '0')"
  ```
  Lead IDs follow the pattern `whatsapp_<phone>`. Expect confusion reports like "the bot stopped answering me" that are actually this feature working — check `human_handoff` before debugging anything else.
- `OWNER_PHONE` comes from `config.json`'s `owner_phone`. Currently set to `555596611311`, which is *also* the client's own test/lead number, so handoff alerts and customer replies land in the same chat during testing.

### 10. ⚠️ The "Zombie Connection" — #1 cause of "the agent stopped replying"
**`GET /instance/connectionState` LIES.** It reports the state persisted in Postgres, not the health of the live Baileys websocket. The socket can die while the endpoint keeps answering `{"state":"open"}` indefinitely. On 2026-07-28 the agent was mute for **8 hours** in exactly this state — systemd `active`, process burning normal CPU (polling fine), connectionState `open`, and **zero errors in `watcher.log`**, because from the watcher's point of view it was simply receiving no new messages.

**How to confirm the zombie state (do this FIRST when "it stopped replying"):**
1. `tail /root/meu-agente/watcher.log` → last entry hours old, no errors. (Silence is the symptom; the log only writes on message activity.)
2. `docker logs evolution-api-9ic2-api-1 --since 30m` → completely empty.
3. `fetchInstances` → `updatedAt` frozen hours in the past while `connectionStatus` still says `open`.
4. Run `watcher.fetch_messages()` on the box — if the newest message returned is hours old and predates messages the user swears they sent, Evolution never received them.

**Fix:** `POST /instance/restart/{instance}` (note: **POST**, not PUT — PUT returns 404). It reconnects from stored credentials, **no QR scan needed**, and recovery is immediate (`CONNECTED TO WHATSAPP` in the container log).

**Automated since 2026-07-28:** `watch()` now runs a watchdog every `HEALTH_CHECK_EVERY` iterations (~5 min) — `is_evolution_socket_alive()` probes `POST /chat/fetchProfile/{instance}`, which forces a genuine WhatsApp round-trip (~1.9s, returns freshly-signed profile-pic URLs). After `HEALTH_FAIL_THRESHOLD` consecutive failures it auto-restarts the instance, notifies `OWNER_PHONE` on both success and failure, and respects `HEALTH_RESTART_COOLDOWN` to avoid restart loops.
- **Do NOT use `/chat/whatsappNumbers` as the probe** — it answers in ~0.03s from the local Contact cache and returns `200 OK` even with a dead socket.
- The auto-restart path (probe failing → restart firing) has **not been observed against a real zombie state yet**, only its components tested individually. If a future incident shows the probe returning healthy while messages don't arrive, the probe endpoint is the thing to re-examine.

### 11. WhatsApp Connection & LID Addressing
- **Reconnecting after a drop:** `GET /instance/connect/agente-agil` returns `{code, base64}`. Decode the `base64` data-URL to a PNG and send it to the user to scan. **The QR expires in roughly 20–30 seconds** — have the user sit on WhatsApp → Aparelhos Conectados → Conectar Aparelho *first*, then generate and send. Multiple attempts failed purely from generate-then-chat latency.
- **⚠️ Tell the user not to touch the Evolution manager UI during reconnect.** On 2026-07-28 a reconnect succeeded ("CONNECTED TO WHATSAPP") and then died 11 seconds later; container logs showed `Restarting instance: agente-agil` from `InstanceController` followed by `redis.delete` + `LOGOUT` — the user had clicked Restart/Disconnect in the web dashboard mid-flow. Check `docker logs evolution-api-9ic2-api-1` for `InstanceController` restarts before assuming the code is at fault.
- **Verify with** `GET /instance/connectionState/agente-agil` → `state` must be `"open"`. A `device_removed` / 401 `conflict` in the logs means the phone dropped the linked device and a fresh QR scan is required.
- **LID addressing (fixed 2026-07-28):** WhatsApp now delivers messages from non-contacts with `remoteJid` like `273662850638050@lid` and the real number only in `key.remoteJidAlt`. The old code gated on `key.get("addressingMode") == "lid"`, but that field is often absent even when the JID *is* `@lid`, so it fell through and used the raw LID as a phone number — every reply then failed with `HTTP 400` in a tight loop while the lead saw silence. `extract_message_data()` now prefers `remoteJidAlt` whenever present and **returns `{}` (ignores the message) if the JID is `@lid` with no alt**, since there is no usable number. Note this is a real limitation: such a lead genuinely cannot be answered — it's a WhatsApp privacy behavior, not something the code can work around.
