"""Herramientas (tools) de AI-SIGU.

Dos capas:
- Pasos 1 a 3B: funciones de negocio. Reciben una Session o parámetros directos y devuelven un dict.
- Paso 4: lo ÚNICO que el LLM puede invocar. La identidad la pone el servidor.
"""
import json
import logging
import os
import re
import secrets
import smtplib
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib import request as urlrequest

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload

from models import Alumno, Area, Folio, Pago, Tramite

ADJUNTOS_DIR = Path(__file__).resolve().parent / "static" / "uploads"
ADJUNTOS_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


# ─────────────────────────── 0. Reglas y utilidades ───────────────────────────

CORREO_ESCALAMIENTO = "dudas.academicas@iztapalapa3.tecnm.mx"
PLAZO_HORAS = 72
MIN_MOTIVO, MAX_MOTIVO = 10, 600

AVISO_FOLIO = "Folio INTERNO de AI-SIGU. No es un folio oficial del SIGU ni del TecNM."
RECORDATORIOS = [
    f"Plazo estimado de respuesta: {PLAZO_HORAS} horas a partir de que envíes el correo.",
    f"Si no hay solución o tienes más dudas, escribe a {CORREO_ESCALAMIENTO}.",
]
NOTA_REQUISITOS = (
    "Si requisitos_verificados es false, di que no hay requisitos oficiales cargados. "
    "Eso NO significa que el trámite no tenga requisitos."
)
TRAMITES_SIN_ACCESO_POSIBLE = {"cc_correo_oficial", "cc_recuperar_pass"}

ALIAS = {
    "dep_titulacion": "titulo titularme",
    "dep_mindbox": "carga materias",
    "se_subes": "beca",
    "se_mindbox_acceso": "acceso",
    "se_correccion_calif": "corregir boleta error",
    "se_correccion_kardex": "corregir error",
    "se_titulo_cedula": "titulacion",
    "cc_correo_oficial": "institucional",
    "cc_recuperar_pass": "correo olvide",
    "rf_validar_pagos": "validar",
    "rf_pago_titulacion": "titulo",
    "vin_ingles": "liberar",
}

_RE_CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _normalizar(texto: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(ascii_.lower().split())


def _singular(palabra: str) -> str:
    if len(palabra) > 5 and palabra.endswith("es") and palabra[-3] in "dlnr":
        return palabra[:-2]
    if len(palabra) > 3 and palabra.endswith("s"):
        return palabra[:-1]
    return palabra


_VACIAS = set(
    "a al como con cual de del donde el en es esta hacer hago la las lo los me mi mis "
    "necesito no o para por puedo que quiero se si solicitar solicitud su tengo "
    "tramite un una y".split()
)


def _palabras(texto: str) -> set[str]:
    encontradas = re.findall(r"[a-z0-9]+", _normalizar(texto))
    return {_singular(p) for p in encontradas if p not in _VACIAS}


def _error(codigo: str, mensaje: str, **extra) -> dict:
    return {"ok": False, "codigo": codigo, "error": mensaje, **extra}


# ─────────────────────── 1. Catálogo: buscar y listar ─────────────────────────

def _consulta_tramites():
    return (
        select(Tramite)
        .options(joinedload(Tramite.area), selectinload(Tramite.requisitos))
        .order_by(Tramite.id)
    )


def _serializar_tramite(tramite: Tramite) -> dict:
    requisitos = sorted(tramite.requisitos, key=lambda r: r.orden)
    return {
        "clave": tramite.clave,
        "nombre": tramite.nombre,
        "area": tramite.area.nombre,
        "correo_area": tramite.area.correo,
        "audiencia": tramite.audiencia,
        "requisitos_verificados": bool(tramite.requisitos_verificados and requisitos),
        "requisitos": [
            {"orden": r.orden, "descripcion": r.descripcion, "es_evidencia": r.es_evidencia}
            for r in requisitos
        ],
    }


def buscar_tramites(db: Session, palabra_clave: str) -> dict:
    consulta = _palabras(palabra_clave)
    if not consulta:
        return _error("consulta_vacia", "Escribe una palabra clave más específica.")

    puntuados = []
    for tramite in db.scalars(_consulta_tramites()):
        texto = f"{tramite.nombre} {ALIAS.get(tramite.clave, '')}"
        puntos = len(consulta & _palabras(texto))
        if puntos:
            puntuados.append((puntos, tramite))

    mejor = max((puntos for puntos, _ in puntuados), default=0)
    tramites = [_serializar_tramite(t) for puntos, t in puntuados if puntos == mejor]
    return {
        "ok": True,
        "total": len(tramites),
        "varias_coincidencias": len(tramites) > 1,
        "areas": sorted({t["area"] for t in tramites}),
        "tramites": tramites,
        "nota_requisitos": NOTA_REQUISITOS,
    }


def listar_tramites_por_area(db: Session, area_clave: str) -> dict:
    area = db.get(Area, area_clave.strip().upper())
    if area is None:
        validas = list(db.scalars(select(Area.clave).order_by(Area.clave)))
        return _error("area_no_encontrada", "Esa área no existe.", areas_validas=validas)

    consulta = _consulta_tramites().where(Tramite.area_clave == area.clave)
    return {
        "ok": True,
        "area": area.nombre,
        "correo_area": area.correo,
        "tramites": [_serializar_tramite(t) for t in db.scalars(consulta)],
        "nota_requisitos": NOTA_REQUISITOS,
    }


# ──────────────────────────── 2. Estado del alumno ────────────────────────────

def _obtener_alumno(db: Session, numero_control: str) -> Alumno | None:
    limpio = numero_control.strip().upper()
    return db.scalar(select(Alumno).where(Alumno.numero_control == limpio))


def consultar_alumno(db: Session, numero_control: str) -> dict:
    alumno = _obtener_alumno(db, numero_control)
    if alumno is None:
        return _error("alumno_no_encontrado", "No hay un alumno con ese número de control.")

    pagos = db.scalars(
        select(Pago)
        .where(Pago.alumno_id == alumno.id)
        .order_by(Pago.periodo.desc(), Pago.id.desc())
    )
    return {
        "ok": True,
        "alumno": {
            "numero_control": alumno.numero_control,
            "nombre": alumno.nombre_completo,
            "carrera": alumno.carrera,
            "semestre": alumno.semestre,
            "correo_institucional": alumno.correo_institucional,
            "estatus_inscripcion": alumno.estatus_inscripcion,
            "pagos": [
                {"concepto": p.concepto, "periodo": p.periodo, "estatus": p.estatus}
                for p in pagos
            ],
        },
    }


# ───────────────────────────── 3. Borrador de folio ───────────────────────────

def _nuevo_folio() -> str:
    anio = datetime.now(timezone.utc).year
    return f"AISIGU-INT-{anio}-{secrets.token_hex(6).upper()}"


def _redactar_cuerpo(alumno, tramite, folio, motivo, evidencias, confirmadas) -> str:
    lineas = [
        f"Estimado equipo de {tramite.area.nombre}:",
        "",
        f"Solicito su apoyo con el siguiente trámite: {tramite.nombre}.",
        "",
        "Datos del estudiante:",
        f"- Nombre: {alumno.nombre_completo}",
        f"- Número de control: {alumno.numero_control}",
        f"- Carrera: {alumno.carrera}",
        "",
        f"Descripción: {motivo}",
    ]
    if evidencias:
        titulo = "Adjunto a este correo:" if confirmadas else "Documentos pendientes de adjuntar:"
        lineas += ["", titulo, *[f"- {e}" for e in evidencias]]
    lineas += [
        "",
        f"Referencia interna de AI-SIGU (no es un folio oficial): {folio}",
        "",
        "Quedo en espera de su respuesta.",
        "",
        "Atentamente,",
        alumno.nombre_completo,
    ]
    return "\n".join(lineas)


def crear_borrador_folio(
    db: Session,
    *,
    numero_control: str | None,
    nombre: str | None,
    carrera: str | None,
    tramite_clave: str,
    motivo: str,
    evidencias_confirmadas: bool = False,
) -> dict:
    datos = {"nombre": nombre, "numero_control": numero_control, "carrera": carrera}
    faltan = [campo for campo, valor in datos.items() if not (valor or "").strip()]
    if faltan:
        return _error("faltan_datos", "Faltan datos obligatorios.", faltan=faltan)

    alumno = _obtener_alumno(db, numero_control)
    if (
        alumno is None
        or _normalizar(alumno.nombre_completo) != _normalizar(nombre)
        or _normalizar(alumno.carrera) != _normalizar(carrera)
    ):
        return _error("datos_no_coinciden", "Los datos no coinciden con el registro escolar.")

    tramite = db.scalar(_consulta_tramites().where(Tramite.clave == tramite_clave))
    if tramite is None:
        return _error("tramite_no_encontrado", "La clave de trámite no existe. Búscala primero.")
    if tramite.audiencia == "aspirante":
        return _error(
            "solo_orientacion",
            "Este trámite es para aspirantes: solo se ofrece orientación, sin folio.",
            correo_area=tramite.area.correo,
        )

    motivo = " ".join(_RE_CORREO.sub("[correo omitido]", motivo).split())
    if not MIN_MOTIVO <= len(motivo) <= MAX_MOTIVO:
        return _error(
            "motivo_invalido",
            f"El motivo debe tener entre {MIN_MOTIVO} y {MAX_MOTIVO} caracteres.",
        )

    evidencias = [
        r.descripcion
        for r in sorted(tramite.requisitos, key=lambda r: r.orden)
        if r.es_evidencia
    ]
    confirmadas = bool(evidencias) and evidencias_confirmadas

    folio = db.scalar(
        select(Folio)
        .where(
            Folio.alumno_id == alumno.id,
            Folio.tramite_id == tramite.id,
            Folio.estado == "borrador",
        )
        .order_by(Folio.id.desc())
    )
    actualizado = folio is not None
    if folio is None:
        folio = Folio(
            folio=_nuevo_folio(),
            alumno_id=alumno.id,
            tramite_id=tramite.id,
            estado="borrador",
        )

    numero = folio.folio
    destinatario = tramite.area.correo
    asunto = f"[{numero}] {tramite.nombre} - {alumno.numero_control}"[:200]
    cuerpo = _redactar_cuerpo(alumno, tramite, numero, motivo, evidencias, confirmadas)

    advertencias = []
    if not (tramite.requisitos_verificados and tramite.requisitos):
        advertencias.append(
            "No hay requisitos oficiales cargados para este trámite; confírmalos con el área."
        )
    if evidencias and not confirmadas:
        advertencias.append("Antes de enviar, confirma que adjuntarás: " + "; ".join(evidencias))
    sin_correo = not alumno.correo_institucional
    if sin_correo or tramite.clave in TRAMITES_SIN_ACCESO_POSIBLE:
        computo = db.get(Area, "CC")
        problema = (
            "No tienes correo institucional registrado."
            if sin_correo
            else "Puede que no tengas acceso a tu correo institucional."
        )
        contacto = f" ({computo.correo})" if computo else ""
        advertencias.append(
            f"{problema} Confirma con Centro de Cómputo{contacto} cómo pedir apoyo."
        )

    folio.destinatario = destinatario
    folio.asunto = asunto
    folio.cuerpo = cuerpo
    folio.evidencias_confirmadas = confirmadas
    db.add(folio)
    db.commit()

    return {
        "ok": True,
        "folio": numero,
        "aviso_folio": AVISO_FOLIO,
        "estado": "borrador",
        "borrador_actualizado": actualizado,
        "listo_para_enviar": not evidencias or confirmadas,
        "destinatario": destinatario,
        "asunto": asunto,
        "cuerpo": cuerpo,
        "evidencias_requeridas": evidencias,
        "advertencias": advertencias,
        "recordatorios": list(RECORDATORIOS),
    }


# ──────────────────── 3B. Despacho de correos y Teams ─────────────────────────

def _enviar_smtp(
    host: str,
    port: int,
    usuario: str,
    password: str,
    destinatario: str,
    asunto: str,
    cuerpo: str,
    ruta_adjunto: str | None = None,
) -> dict:
    msg = MIMEMultipart()
    msg["From"] = usuario
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

    if ruta_adjunto:
        archivo = Path(ruta_adjunto)
        if archivo.exists() and archivo.is_file():
            parte = MIMEBase("application", "octet-stream")
            parte.set_payload(archivo.read_bytes())
            encoders.encode_base64(parte)
            parte.add_header("Content-Disposition", f'attachment; filename="{archivo.name}"')
            msg.attach(parte)

    with smtplib.SMTP(host, port, timeout=15) as server:
        server.starttls()
        server.login(usuario, password)
        server.send_message(msg)

    return {"ok": True, "canal": host, "destinatario": destinatario, "adjunto": bool(ruta_adjunto)}


def despachar_mensaje_agente(
    canal: str,
    destinatario: str,
    asunto: str,
    cuerpo: str,
    ruta_adjunto: str | None = None,
) -> dict:
    """Envía un mensaje real por Gmail, Outlook o Teams (o simula si faltan credenciales)."""
    canal_norm = canal.strip().lower()

    if canal_norm == "gmail":
        user = os.getenv("GMAIL_USER", "").strip()
        pwd = os.getenv("GMAIL_APP_PASSWORD", "").strip()
        if user and pwd:
            return _enviar_smtp("smtp.gmail.com", 587, user, pwd, destinatario, asunto, cuerpo, ruta_adjunto)
        return {
            "ok": True,
            "modo": "simulado_local",
            "canal": "Gmail",
            "destinatario": destinatario,
            "asunto": asunto,
            "adjunto": Path(ruta_adjunto).name if ruta_adjunto else None,
            "detalle": "Configura GMAIL_USER y GMAIL_APP_PASSWORD en .env para envío SMTP real.",
        }

    if canal_norm == "outlook":
        user = os.getenv("OUTLOOK_USER", "").strip()
        pwd = os.getenv("OUTLOOK_PASSWORD", "").strip()
        if user and pwd:
            return _enviar_smtp("smtp.office365.com", 587, user, pwd, destinatario, asunto, cuerpo, ruta_adjunto)
        return {
            "ok": True,
            "modo": "simulado_local",
            "canal": "Outlook",
            "destinatario": destinatario,
            "asunto": asunto,
            "adjunto": Path(ruta_adjunto).name if ruta_adjunto else None,
            "detalle": "Configura OUTLOOK_USER y OUTLOOK_PASSWORD en .env para envío SMTP real.",
        }

    if canal_norm == "teams":
        webhook = os.getenv("TEAMS_WEBHOOK_URL", "").strip()
        texto_teams = f"**{asunto}**\n\nPara: {destinatario}\n\n{cuerpo}"
        if ruta_adjunto:
            texto_teams += f"\n\nArchivo adjunto: `{Path(ruta_adjunto).name}`"
        if webhook:
            payload = json.dumps({"text": texto_teams}).encode("utf-8")
            req = urlrequest.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
            with urlrequest.urlopen(req, timeout=10) as resp:
                return {"ok": True, "canal": "Microsoft Teams", "status": resp.status}
        return {
            "ok": True,
            "modo": "simulado_local",
            "canal": "Microsoft Teams",
            "destinatario": destinatario,
            "asunto": asunto,
            "adjunto": Path(ruta_adjunto).name if ruta_adjunto else None,
            "detalle": "Configura TEAMS_WEBHOOK_URL en .env para publicar directo en tu canal de Teams.",
        }

    return _error("canal_no_soportado", f"Canal no soportado: {canal}")


# ───────────────────────── 4. Interfaz para el LLM ────────────────────────────

@dataclass
class ContextoSesion:
    numero_control: str | None = None
    nombre: str | None = None
    carrera: str | None = None
    evidencias_confirmadas: frozenset[str] = frozenset()
    borradores: list[dict] = field(default_factory=list)


def _tool_buscar(db: Session, ctx: ContextoSesion, palabra_clave: str) -> dict:
    return buscar_tramites(db, palabra_clave)


def _tool_listar(db: Session, ctx: ContextoSesion, area_clave: str) -> dict:
    return listar_tramites_por_area(db, area_clave)


def _tool_mi_estado(db: Session, ctx: ContextoSesion) -> dict:
    if not ctx.numero_control:
        return _error("sin_sesion", "El alumno debe iniciar sesión.")
    resultado = consultar_alumno(db, ctx.numero_control)
    if not resultado["ok"]:
        return resultado
    alumno = resultado["alumno"]
    permitidos = ("carrera", "semestre", "estatus_inscripcion", "pagos")
    return {
        "ok": True,
        **{campo: alumno[campo] for campo in permitidos},
        "tiene_correo_institucional": bool(alumno["correo_institucional"]),
    }


def _tool_crear_borrador(
    db: Session, ctx: ContextoSesion, tramite_clave: str, motivo: str
) -> dict:
    resultado = crear_borrador_folio(
        db,
        numero_control=ctx.numero_control,
        nombre=ctx.nombre,
        carrera=ctx.carrera,
        tramite_clave=tramite_clave,
        motivo=motivo,
        evidencias_confirmadas=tramite_clave in ctx.evidencias_confirmadas,
    )
    if not resultado["ok"]:
        return resultado
    ctx.borradores = [b for b in ctx.borradores if b["folio"] != resultado["folio"]]
    ctx.borradores.append(resultado)
    return {k: v for k, v in resultado.items() if k not in ("asunto", "cuerpo")}


def _tool_despachar(
    db: Session,
    ctx: ContextoSesion,
    canal: str,
    destinatario: str,
    asunto: str,
    cuerpo: str,
    ruta_adjunto: str = "",
) -> dict:
    adjunto = ruta_adjunto.strip() or None
    return despachar_mensaje_agente(canal, destinatario, asunto, cuerpo, adjunto)


def _spec(
    nombre: str,
    descripcion: str,
    opcionales: set[str] | None = None,
    **parametros: str,
) -> dict:
    opcionales = opcionales or set()
    return {
        "name": nombre,
        "description": descripcion,
        "parameters": {
            "type": "object",
            "properties": {
                p: {"type": "string", "description": d} for p, d in parametros.items()
            },
            "required": [p for p in parametros if p not in opcionales],
        },
    }


TOOL_SPECS = [
    _spec(
        "buscar_tramites",
        "Busca trámites y sus requisitos. Si hay varias coincidencias y la consulta "
        "no permite distinguirlas, pregunta al alumno antes de elegir.",
        palabra_clave="Palabras clave del trámite, por ejemplo: 'corregir calificación'.",
    ),
    _spec(
        "listar_tramites_por_area",
        "Lista los trámites de un área con sus requisitos.",
        area_clave="Una de: DEP, SE, DDA, CC, RF, VIN, CBAS.",
    ),
    _spec(
        "consultar_mi_estado",
        "Consulta semestre, carrera, inscripción y pagos del alumno de la sesión actual.",
    ),
    _spec(
        "crear_borrador_folio",
        "Crea o actualiza un borrador de correo con folio interno. No lo envía. "
        "Úsala solo si el alumno lo pide o acepta.",
        tramite_clave="Clave exacta devuelta por las herramientas de catálogo.",
        motivo="Descripción breve del problema, sin contraseñas ni datos personales.",
    ),
    _spec(
        "despachar_mensaje",
        "Envía un mensaje o correo directamente por 'gmail', 'outlook' o 'teams', con archivo adjunto opcional.",
        opcionales={"ruta_adjunto"},
        canal="Canal de envío: 'gmail', 'outlook' o 'teams'.",
        destinatario="Correo del área o destinatario.",
        asunto="Asunto o título del mensaje.",
        cuerpo="Texto completo del mensaje a enviar.",
        ruta_adjunto="Ruta local del archivo adjunto si el alumno subió uno.",
    ),
]

_FUNCIONES = {
    "buscar_tramites": _tool_buscar,
    "listar_tramites_por_area": _tool_listar,
    "consultar_mi_estado": _tool_mi_estado,
    "crear_borrador_folio": _tool_crear_borrador,
    "despachar_mensaje": _tool_despachar,
}
_REQUERIDOS = {s["name"]: set(s["parameters"]["required"]) for s in TOOL_SPECS}
_PERMITIDOS = {s["name"]: set(s["parameters"]["properties"]) for s in TOOL_SPECS}


def ejecutar_herramienta(
    db: Session, ctx: ContextoSesion, nombre: str, argumentos: dict | None
) -> dict:
    if nombre not in _FUNCIONES:
        return _error("herramienta_desconocida", "Esa herramienta no existe.")

    argumentos = {} if argumentos is None else argumentos
    requeridos = _REQUERIDOS[nombre]
    permitidos = _PERMITIDOS[nombre]
    if (
        not isinstance(argumentos, dict)
        or not requeridos.issubset(argumentos)
        or not set(argumentos).issubset(permitidos)
        or not all(isinstance(v, str) for v in argumentos.values())
    ):
        return _error(
            "argumentos_invalidos",
            f"Argumentos inválidos. Requeridos: {sorted(requeridos)}, opcionales: {sorted(permitidos - requeridos)}",
        )

    try:
        return _FUNCIONES[nombre](db, ctx, **argumentos)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error de base de datos en la herramienta %s", nombre)
        return _error("error_bd", "No se pudo completar la operación.")