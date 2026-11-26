"""Orquestador del agente AI-SIGU con respaldo automático de modelos en Groq."""
import json
import os
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
    "llama-3.1-8b-instant",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "openai/gpt-oss-20b",
    "qwen/qwen3-32b",
    "llama-3.3-70b-versatile",
]


class ProveedorGroq:
    def __init__(self, api_key: str, modelo_preferido: str):
        self.cliente = Groq(api_key=api_key)
        orden = [modelo_preferido] if modelo_preferido else []
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
                    temperature=0.2,
                    max_tokens=1024,
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
    modelo = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
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


SYSTEM_PROMPT = (
    "Eres el Agente Inteligente AI-SIGU del Instituto Tecnológico de Iztapalapa III (TecNM). "
    "Oferta educativa del plantel: Escolarizada (Ingeniería Civil, Ingeniería Informática, Ingeniería Gestión Empresarial) "
    "y TecNM Virtual (Ingeniería Industrial, Ingeniería Gestión Empresarial, Ingeniería Sistemas Computacionales). "
    "Tu objetivo es resolver trámites escolares y docentes de forma rápida, directa y eficiente sin demoras.\n"
    "Reglas:\n"
    "1. Usa 'buscar_tramites', 'listar_tramites_por_area' o 'consultar_mi_estado' para consultar información real.\n"
    "2. Si el usuario pide redactar una solicitud o requiere un correo formal, usa 'crear_borrador_folio'.\n"
    "3. Si el usuario pide enviar un correo o mensaje por Gmail, Outlook o Microsoft Teams (con o sin archivo adjunto), "
    "ejecuta directamente 'despachar_mensaje' con el canal indicado, destinatario, asunto y cuerpo.\n"
    "4. Responde siempre en español, claro, conciso y confirmando las acciones realizadas."
)


def ejecutar_agente(
    db: Session,
    proveedor: Proveedor,
    ctx: ContextoSesion,
    mensaje_usuario: str,
    historial: list[dict],
) -> str:
    contexto_datos = []
    if ctx.numero_control:
        contexto_datos.append(f"Identificador activo: {ctx.numero_control}")
    if ctx.nombre:
        contexto_datos.append(f"Nombre: {ctx.nombre}")
    if ctx.carrera:
        contexto_datos.append(f"Carrera / Área: {ctx.carrera}")

    prompt_sistema = SYSTEM_PROMPT
    if contexto_datos:
        prompt_sistema += "\n\nDatos de sesión activa:\n- " + "\n- ".join(contexto_datos)

    mensajes: list[dict] = [{"role": "system", "content": prompt_sistema}]
    for item in historial[-12:]:
        rol = "assistant" if item.get("rol") == "asistente" else "user"
        mensajes.append({"role": rol, "content": item.get("texto", "")})
    mensajes.append({"role": "user", "content": mensaje_usuario})

    herramientas = _herramientas_openai()

    for _ in range(5):
        resp = proveedor.completar(mensajes, herramientas)
        eleccion = resp.choices[0].message

        if not eleccion.tool_calls:
            return (eleccion.content or "").strip() or "Listo, operación completada."

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

    return "Se completaron los pasos solicitados."