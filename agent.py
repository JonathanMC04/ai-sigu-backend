"""Orquestador del agente AI-SIGU con razonamiento avanzado y respaldo automático en Groq."""
import json
import os
import re
from typing import Protocol

from groq import APIError, AuthenticationError, Groq, NotFoundError, RateLimitError
from sqlalchemy.orm import Session

from tools import ContextoSesion, TOOL_SPECS, despachar_mensaje_agente, ejecutar_herramienta


class ErrorConfiguracion(Exception):
    pass


class ErrorLimite(Exception):
    pass


class ErrorProveedor(Exception):
    pass


class Proveedor(Protocol):
    def completar(self, mensajes: list[dict], herramientas: list[dict]): ...


MODELOS_RESPALDO = [
    "llama-3.3-70b-versatile",
    "qwen/qwen3-32b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
]


class ProveedorGroq:
    def __init__(self, api_key: str, modelo_preferido: str):
        self.cliente = Groq(api_key=api_key)
        orden: list[str] = []
        if modelo_preferido and modelo_preferido != "llama-3.1-8b-instant":
            orden.append(modelo_preferido)
        for m in MODELOS_RESPALDO:
            if m not in orden:
                orden.append(m)
        self.modelos = orden

    def completar(self, mensajes: list[dict], herramientas: list[dict]):
        ultimo_error = None
        for modelo in self.modelos:
            try:
                return self.cliente.chat.completions.create(
                    model=modelo,
                    messages=mensajes,
                    tools=herramientas,
                    tool_choice="auto",
                    temperature=0.3,
                    max_tokens=2048,
                )
            except AuthenticationError as err:
                raise ErrorConfiguracion("GROQ_API_KEY inválida o sin permisos.") from err
            except RateLimitError as err:
                raise ErrorLimite("Límite de peticiones alcanzado en Groq. Intenta en unos segundos.") from err
            except NotFoundError as err:
                ultimo_error = err
                continue
            except APIError as err:
                if "model_not_found" in str(err) or "does not exist" in str(err):
                    ultimo_error = err
                    continue
                raise ErrorProveedor(f"Error del proveedor Groq: {err}") from err
        raise ErrorProveedor(f"Ningún modelo de Groq estuvo disponible en tu cuenta: {ultimo_error}")


def crear_proveedor() -> Proveedor:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ErrorConfiguracion("Falta GROQ_API_KEY en el archivo .env.")
    modelo = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    return ProveedorGroq(api_key=api_key, modelo_preferido=modelo)


def _herramientas_openai() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": spec["name"],
                "description": spec["description"],
                "parameters": spec["parameters"],
            },
        }
        for spec in TOOL_SPECS
    ]


def _limpiar_respuesta(texto: str) -> str:
    """Elimina bloques internos de pensamiento (<think>) si el modelo los incluye."""
    limpio = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()
    return limpio


SYSTEM_PROMPT = """Eres el Agente Inteligente Oficial AI-SIGU del Instituto Tecnológico de Iztapalapa III (TecNM).
Tu función es analizar a profundidad cada consulta académica, administrativa o docente y entregar respuestas completas, estructuradas, precisas y resolutivas en español.

OFERTA EDUCATIVA DEL PLANTEL:
- Modalidad Escolarizada: Ingeniería Civil, Ingeniería Informática, Ingeniería en Gestión Empresarial.
- Modalidad TecNM Virtual: Ingeniería Industrial, Ingeniería en Gestión Empresarial, Ingeniería en Sistemas Computacionales.

PLATAFORMAS Y ENLACES OFICIALES:
- Sitio oficial y avisos del plantel: https://iztapalapa3.tecnm.mx/
- Mindbox (acceso estudiantes): https://itiztapalapa3.mindbox.app/login/student

MÉTODOS DE CONTACTO Y HORARIO DE ATENCIÓN:
- Dirección: Cda. Orquídea 71, San Miguel Teotongo, Alcaldía Iztapalapa, C.P. 09630, Ciudad de México, CDMX.
- Transporte: A 7 minutos de la Estación Teleférico (Línea 2) San Miguel Teotongo.
- Contacto Inscripciones: Correo dda_iztapalapa3@tecnm.mx | WhatsApp: https://wa.me/5215530792382 (55 3079 2382).
- Contacto Web y Soporte: Correo cyd_iztapalapa3@tecnm.mx | Teléfono: 55 5670 4173.
- Horario de atención: Lunes a Viernes de 8:00 am a 6:00 pm. Sábado y Domingo: Cerrado.

DATOS OFICIALES PARA PAGOS Y REINSCRIPCIÓN (BANAMEX):
- Caja o Practicaja en Banco Banamex:
  * Banco: Banamex
  * Número de cuenta: 7013 758639
  * Nombre: Instituto Tecnológico de Iztapalapa III
  * Referencia: Número de control de 9 dígitos del alumno
- Transferencia Electrónica (SPEI):
  * Banco: Banamex
  * CLABE Interbancaria: 002180701307586392
  * Nombre: Instituto Tecnológico de Iztapalapa III
  * Referencia: Número de control de 9 dígitos del alumno
- Banca en línea Banamex: https://www.banamex.com/

REGLAS DE OPERACIÓN Y RAZONAMIENTO:
1. Analiza la intención completa del usuario antes de responder y verifica qué información necesitas consultar en el sistema.
2. Usa 'buscar_tramites', 'listar_tramites_por_area' o 'consultar_mi_estado' siempre que el usuario pregunte por requisitos, estatus, calificaciones, kardex, biblioteca o gestiones escolares.
3. Si el usuario solicita redactar una solicitud o correo institucional, ejecuta 'crear_borrador_folio' incluyendo su número de control de 9 dígitos, nombre completo y carrera.
4. Si el usuario pide enviar un correo o mensaje por Gmail, Outlook o Microsoft Teams (con o sin archivo adjunto), ejecuta directamente 'despachar_mensaje' con el canal, destinatario, asunto y cuerpo completo.
5. Cuando pregunten por contacto, ubicación, teléfonos, correos o horarios, entrega directamente los métodos de contacto oficiales y el horario de atención del plantel.
6. Cuando pregunten por pagos o reinscripción, proporciona las opciones de pago en Banamex (Practicaja/Caja y Transferencia CLABE) indicando su número de control de 9 dígitos como referencia.
7. Nunca menciones modos de demostración, servidores locales ni detalles técnicos internos. Responde con claridad, orden (viñetas o pasos numerados cuando ayude) y tono institucional profesional."""


def ejecutar_agente(
    db: Session,
    proveedor: Proveedor,
    ctx: ContextoSesion,
    mensaje_usuario: str,
    historial: list[dict],
) -> str:
    contexto_datos = []
    if ctx.numero_control:
        contexto_datos.append(f"Número de control / Identificador activo (9 dígitos): {ctx.numero_control}")
    if ctx.nombre:
        contexto_datos.append(f"Nombre completo: {ctx.nombre}")
    if ctx.carrera:
        contexto_datos.append(f"Carrera / Área: {ctx.carrera}")

    prompt_sistema = SYSTEM_PROMPT
    if contexto_datos:
        prompt_sistema += "\n\nDATOS DE LA SESIÓN ACTIVA:\n- " + "\n- ".join(contexto_datos)

    mensajes: list[dict] = [{"role": "system", "content": prompt_sistema}]
    for item in historial[-16:]:
        rol = "assistant" if item.get("rol") == "asistente" else "user"
        texto = (item.get("texto") or "").strip()
        if texto:
            mensajes.append({"role": rol, "content": texto})
    mensajes.append({"role": "user", "content": mensaje_usuario})

    herramientas = _herramientas_openai()

    for _ in range(8):
        resp = proveedor.completar(mensajes, herramientas)
        eleccion = resp.choices[0].message

        if not eleccion.tool_calls:
            respuesta_final = _limpiar_respuesta(eleccion.content or "")
            return respuesta_final or "Listo, operación completada."

        mensajes.append(
            {
                "role": "assistant",
                "content": eleccion.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in eleccion.tool_calls
                ],
            }
        )

        for tc in eleccion.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            resultado = ejecutar_herramienta(db, ctx, tc.function.name, args)
            mensajes.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(resultado, ensure_ascii=False),
                }
            )

    return "Se completaron todas las consultas y acciones solicitadas."
