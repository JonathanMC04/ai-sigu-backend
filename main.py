"""API de AI-SIGU + Módulos SIGU para TecNM Campus Iztapalapa III."""
import html
import os
import re
import uuid
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from agent import (
    ErrorConfiguracion,
    ErrorLimite,
    ErrorProveedor,
    Proveedor,
    crear_proveedor,
    ejecutar_agente,
)
from models import (
    Alumno,
    Asistencia,
    AvisoInstitucional,
    Base,
    Docente,
    Inscripcion,
    Libro,
    Materia,
    Pago,
    PrestamoBiblioteca,
    SolicitudTramite,
    Tramite,
)
from seed import engine, run_seed
from tools import (
    ADJUNTOS_DIR,
    ContextoSesion,
    consultar_alumno,
    despachar_mensaje_agente,
)

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

PORTAL_OFICIAL_URL = "https://iztapalapa3.tecnm.mx/"
MINDBOX_URL = "https://itiztapalapa3.mindbox.app/login/student"


# ──────────────────────────────── 1. Arranque ─────────────────────────────────

def modo_demo() -> bool:
    return os.getenv("AISIGU_DEMO") == "1"


def _migrar_columnas_sqlite(conexion) -> None:
    """Agrega columnas nuevas si ya existe un ai_sigu.db previo en local."""
    migraciones = {
        "libros": [
            ("categoria", "VARCHAR(80) NOT NULL DEFAULT 'General'"),
            ("carrera", "VARCHAR(120) NOT NULL DEFAULT 'Todas'"),
            ("url_recurso", "VARCHAR(300)"),
        ],
        "solicitudes_tramites": [
            ("area_destino", "VARCHAR(80) NOT NULL DEFAULT 'Servicios Escolares'"),
        ],
        "avisos_institucionales": [
            ("url_origen", "VARCHAR(300)"),
        ],
    }
    for tabla, columnas in migraciones.items():
        existentes = {
            fila[1]
            for fila in conexion.exec_driver_sql(f"PRAGMA table_info({tabla})").fetchall()
        }
        for col, definicion in columnas:
            if col not in existentes:
                conexion.exec_driver_sql(
                    f"ALTER TABLE {tabla} ADD COLUMN {col} {definicion}"
                )


def preparar_bd() -> None:
    Base.metadata.create_all(engine)
    if engine.dialect.name == "sqlite":
        with engine.begin() as conexion:
            if conexion.exec_driver_sql("PRAGMA foreign_keys").scalar() != 1:
                raise RuntimeError("SQLite no activó las llaves foráneas.")
            _migrar_columnas_sqlite(conexion)
    run_seed()


@asynccontextmanager
async def lifespan(app: FastAPI):
    preparar_bd()
    yield


app = FastAPI(title="AI-SIGU · TecNM Iztapalapa III", version="1.0.0", lifespan=lifespan)

_origenes = [o.strip() for o in os.getenv("AISIGU_CORS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origenes or ["*"],
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ─────────────────────────────── 2. Dependencias ──────────────────────────────

def obtener_db():
    with Session(engine) as db:
        yield db


@lru_cache
def _proveedor_unico() -> Proveedor:
    return crear_proveedor()


def obtener_proveedor() -> Proveedor:
    try:
        return _proveedor_unico()
    except ErrorConfiguracion as error:
        raise HTTPException(503, str(error)) from error


def _obtener_o_crear_alumno(
    db: Session,
    numero_control: str,
    nombre: str | None = None,
    carrera: str | None = None,
) -> Alumno:
    nc = numero_control.strip()
    alumno = db.scalar(select(Alumno).where(Alumno.numero_control == nc))
    if alumno:
        actualizado = False
        if nombre and nombre.strip() and alumno.nombre_completo.startswith("Estudiante "):
            alumno.nombre_completo = nombre.strip()
            actualizado = True
        if carrera and carrera.strip() and alumno.carrera == "Ingeniería":
            alumno.carrera = carrera.strip()
            actualizado = True
        if actualizado:
            db.commit()
            db.refresh(alumno)
        return alumno

    nuevo = Alumno(
        numero_control=nc,
        nombre_completo=(nombre or f"Estudiante {nc}").strip(),
        carrera=(carrera or "Ingeniería").strip(),
        semestre=1,
        correo_institucional=f"l{nc}@iztapalapa3.tecnm.mx",
        estatus_inscripcion="activo",
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


# ───────────────────────────────── 3. Esquemas ────────────────────────────────

class Entrada(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class LoginAlumnoIn(Entrada):
    numero_control: str = Field(pattern=r"^\d{9}$", description="Número de control de 9 dígitos")
    nombre_completo: str = Field(min_length=2, max_length=150)
    carrera: str = Field(min_length=2, max_length=120)


class MensajeHistorial(Entrada):
    rol: Literal["usuario", "asistente"]
    contenido: str = Field(min_length=1, max_length=8000)


class PeticionChat(Entrada):
    mensaje: str = Field(min_length=1, max_length=1500)
    historial: list[MensajeHistorial] = Field(default_factory=list, max_length=50)
    numero_control: str | None = Field(default=None, max_length=20)
    nombre: str | None = Field(default=None, max_length=150)
    carrera: str | None = Field(default=None, max_length=120)
    evidencias_confirmadas: list[Annotated[str, Field(min_length=1, max_length=60)]] = Field(
        default_factory=list, max_length=20
    )


class Borrador(BaseModel):
    folio: str
    aviso_folio: str
    estado: str
    borrador_actualizado: bool
    listo_para_enviar: bool
    destinatario: str
    asunto: str
    cuerpo: str
    evidencias_requeridas: list[str]
    advertencias: list[str]
    recordatorios: list[str]


class RespuestaChat(BaseModel):
    respuesta: str
    borradores: list[Borrador]


class NuevaInscripcionIn(Entrada):
    numero_control: str = Field(min_length=1, max_length=20)
    materia_id: int
    periodo: str = Field(default="2026-2", max_length=20)


class CalificacionIn(Entrada):
    calificacion_final: float = Field(ge=0, le=100)


class AsistenciaIn(Entrada):
    fecha: str = Field(min_length=4, max_length=20)
    presente: bool = True


class NuevaSolicitudIn(Entrada):
    numero_control: str = Field(min_length=1, max_length=20)
    tramite_clave: str = Field(min_length=1, max_length=80)
    motivo: str = Field(min_length=3, max_length=1000)
    area_destino: str = Field(default="Servicios Escolares", max_length=80)
    nombre_alumno: str | None = Field(default=None, max_length=150)
    carrera: str | None = Field(default=None, max_length=120)


class EstadoSolicitudIn(Entrada):
    estado: Literal["pendiente", "en_revision", "aprobado", "rechazado"]


class NuevoLibroIn(Entrada):
    titulo: str = Field(min_length=2, max_length=180)
    autor: str = Field(min_length=2, max_length=120)
    categoria: str = Field(default="Ingeniería", max_length=80)
    carrera: str = Field(default="Todas", max_length=120)
    ejemplares_disponibles: int = Field(default=1, ge=1, le=500)
    codigo: str | None = Field(default=None, max_length=30)
    url_recurso: str | None = Field(default=None, max_length=300)


class NuevoPrestamoIn(Entrada):
    numero_control: str = Field(min_length=1, max_length=20)
    libro_id: int


class NuevoPagoIn(Entrada):
    numero_control: str = Field(min_length=1, max_length=20)
    concepto: str = Field(min_length=2, max_length=120)
    periodo: str = Field(default="2026-2", max_length=20)
    nombre_alumno: str | None = Field(default=None, max_length=150)
    carrera: str | None = Field(default=None, max_length=120)


class NuevoAvisoIn(Entrada):
    titulo: str = Field(min_length=3, max_length=160)
    area_clave: str = Field(min_length=2, max_length=10)
    contenido: str = Field(min_length=5, max_length=2000)
    url_origen: str | None = Field(default=None, max_length=300)


# ─────────────────────────── 4. Endpoints Base AI-SIGU ────────────────────────

def construir_contexto(db: Session, peticion: PeticionChat) -> ContextoSesion:
    numero_control = None
    if peticion.numero_control:
        alumno = _obtener_o_crear_alumno(
            db,
            peticion.numero_control,
            peticion.nombre,
            peticion.carrera,
        )
        existente = consultar_alumno(db, alumno.numero_control)
        numero_control = (
            existente["alumno"]["numero_control"]
            if existente.get("ok")
            else alumno.numero_control
        )

    return ContextoSesion(
        numero_control=numero_control,
        nombre=peticion.nombre,
        carrera=peticion.carrera,
        evidencias_confirmadas=frozenset(peticion.evidencias_confirmadas),
    )


@app.get("/", include_in_schema=False)
def inicio() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/salud")
def salud() -> dict:
    return {
        "estado": "activo",
        "demo": False,
        "llm_configurado": bool(os.getenv("GROQ_API_KEY", "").strip()),
        "portal_oficial": PORTAL_OFICIAL_URL,
        "mindbox_url": MINDBOX_URL,
    }


@app.post("/api/auth/login")
def iniciar_sesion_alumno(datos: LoginAlumnoIn, db: Session = Depends(obtener_db)) -> dict:
    """Valida matrícula de 9 dígitos, persiste el alumno y devuelve su perfil y trámites."""
    alumno = _obtener_o_crear_alumno(
        db,
        datos.numero_control,
        datos.nombre_completo,
        datos.carrera,
    )
    tramites_map = {t.clave: t.nombre for t in db.scalars(select(Tramite)).all()}
    solicitudes = db.scalars(
        select(SolicitudTramite)
        .where(SolicitudTramite.alumno_id == alumno.id)
        .order_by(SolicitudTramite.id.desc())
    ).all()

    return {
        "ok": True,
        "alumno": {
            "id": alumno.id,
            "numero_control": alumno.numero_control,
            "nombre_completo": alumno.nombre_completo,
            "carrera": alumno.carrera,
            "semestre": alumno.semestre,
            "correo_institucional": alumno.correo_institucional,
            "estatus_inscripcion": alumno.estatus_inscripcion,
        },
        "tramites": [
            {
                "id": s.id,
                "folio": s.folio,
                "tramite_clave": s.tramite_clave,
                "tramite_nombre": tramites_map.get(s.tramite_clave, s.tramite_clave),
                "area_destino": s.area_destino,
                "motivo": s.motivo,
                "estado": s.estado,
                "creado_en": s.creado_en.strftime("%Y-%m-%d %H:%M") if s.creado_en else "",
            }
            for s in solicitudes
        ],
    }


@app.post("/chat", response_model=RespuestaChat)
def chat(
    peticion: PeticionChat,
    db: Session = Depends(obtener_db),
    proveedor: Proveedor = Depends(obtener_proveedor),
) -> RespuestaChat:
    ctx = construir_contexto(db, peticion)
    historial = [{"rol": m.rol, "texto": m.contenido} for m in peticion.historial]
    try:
        texto = ejecutar_agente(db, proveedor, ctx, peticion.mensaje, historial)
    except ErrorLimite as error:
        raise HTTPException(429, str(error)) from error
    except ErrorConfiguracion as error:
        raise HTTPException(503, str(error)) from error
    except ErrorProveedor as error:
        raise HTTPException(502, str(error)) from error
    return RespuestaChat(
        respuesta=texto,
        borradores=[Borrador.model_validate(b) for b in ctx.borradores],
    )


# ──────────────────── 4B. Subida de Archivos y Despacho ───────────────────────

@app.post("/api/agente/subir-archivo")
async def subir_archivo_agente(archivo: UploadFile = File(...)) -> dict:
    nombre_seguro = Path(archivo.filename or "documento.pdf").name
    destino = ADJUNTOS_DIR / nombre_seguro
    destino.write_bytes(await archivo.read())
    return {
        "ok": True,
        "nombre": nombre_seguro,
        "ruta": str(destino),
        "url": f"/static/uploads/{nombre_seguro}",
    }


@app.post("/api/agente/despachar")
def despachar_desde_ui(
    canal: str = Form(...),
    destinatario: str = Form(...),
    asunto: str = Form(...),
    cuerpo: str = Form(...),
    ruta_adjunto: str | None = Form(default=None),
) -> dict:
    resultado = despachar_mensaje_agente(canal, destinatario, asunto, cuerpo, ruta_adjunto)
    if not resultado.get("ok"):
        raise HTTPException(400, resultado.get("error", "No se pudo enviar el mensaje."))
    return resultado


# ─────────────────────────── 5. Endpoints Módulos SIGU ────────────────────────

@app.get("/api/resumen")
def resumen_sistema(db: Session = Depends(obtener_db)) -> dict:
    alumnos = db.scalars(select(Alumno).order_by(Alumno.id)).all()
    docentes = db.scalars(select(Docente).order_by(Docente.id)).all()
    materias = db.scalars(select(Materia).order_by(Materia.clave)).all()
    tramites = db.scalars(select(Tramite).order_by(Tramite.area_clave, Tramite.nombre)).all()
    avisos = db.scalars(select(AvisoInstitucional).order_by(AvisoInstitucional.id.desc())).all()

    return {
        "kpis": {
            "alumnos": len(alumnos),
            "docentes": len(docentes),
            "materias": len(materias),
            "tramites_catalogo": len(tramites),
        },
        "enlaces_oficiales": {
            "portal": PORTAL_OFICIAL_URL,
            "mindbox": MINDBOX_URL,
            "banamex": "https://www.banamex.com/",
        },
        "alumnos": [
            {
                "id": a.id,
                "numero_control": a.numero_control,
                "nombre_completo": a.nombre_completo,
                "carrera": a.carrera,
                "semestre": a.semestre,
                "correo_institucional": a.correo_institucional,
                "estatus_inscripcion": a.estatus_inscripcion,
            }
            for a in alumnos
        ],
        "docentes": [
            {
                "id": d.id,
                "matricula": d.matricula,
                "nombre_completo": d.nombre_completo,
                "especialidad": d.especialidad,
                "correo": d.correo,
            }
            for d in docentes
        ],
        "tramites_catalogo": [
            {"clave": t.clave, "nombre": t.nombre, "area_clave": t.area_clave}
            for t in tramites
        ],
        "avisos": [
            {
                "id": av.id,
                "titulo": av.titulo,
                "area_clave": av.area_clave,
                "contenido": av.contenido,
                "url_origen": av.url_origen or PORTAL_OFICIAL_URL,
                "publicado_en": av.publicado_en.isoformat() if av.publicado_en else "",
            }
            for av in avisos
        ],
    }


@app.get("/api/escolar")
def modulo_escolar(db: Session = Depends(obtener_db)) -> dict:
    materias = db.scalars(select(Materia).order_by(Materia.semestre_sugerido, Materia.clave)).all()
    inscripciones = db.scalars(select(Inscripcion).order_by(Inscripcion.id.desc())).all()

    return {
        "materias": [
            {
                "id": m.id,
                "clave": m.clave,
                "nombre": m.nombre,
                "creditos": m.creditos,
                "semestre_sugerido": m.semestre_sugerido,
                "horario": m.horario,
                "docente": m.docente.nombre_completo if m.docente else "Sin asignar",
            }
            for m in materias
        ],
        "inscripciones": [
            {
                "id": ins.id,
                "numero_control": ins.alumno.numero_control,
                "alumno": ins.alumno.nombre_completo,
                "materia_clave": ins.materia.clave,
                "materia": ins.materia.nombre,
                "creditos": ins.materia.creditos,
                "periodo": ins.periodo,
                "calificacion_final": ins.calificacion_final,
                "estado": ins.estado,
                "asistencias_total": len(ins.asistencias),
                "asistencias_presentes": sum(1 for a in ins.asistencias if a.presente),
            }
            for ins in inscripciones
        ],
    }


@app.post("/api/escolar/inscribir")
def inscribir_materia(datos: NuevaInscripcionIn, db: Session = Depends(obtener_db)) -> dict:
    alumno = db.scalar(select(Alumno).where(Alumno.numero_control == datos.numero_control))
    if not alumno:
        raise HTTPException(404, "Alumno no encontrado.")
    materia = db.get(Materia, datos.materia_id)
    if not materia:
        raise HTTPException(404, "Materia no encontrada.")
    existente = db.scalar(
        select(Inscripcion).where(
            Inscripcion.alumno_id == alumno.id,
            Inscripcion.materia_id == materia.id,
            Inscripcion.periodo == datos.periodo,
        )
    )
    if existente:
        raise HTTPException(400, "El alumno ya está inscrito en esa materia en este periodo.")

    estado = "cursando" if alumno.estatus_inscripcion == "inscrito" else "pendiente_pago"
    nueva = Inscripcion(
        alumno_id=alumno.id,
        materia_id=materia.id,
        periodo=datos.periodo,
        estado=estado,
    )
    db.add(nueva)
    db.commit()
    return {"ok": True, "estado": estado}


@app.patch("/api/docente/inscripciones/{inscripcion_id}/calificacion")
def actualizar_calificacion(
    inscripcion_id: int, datos: CalificacionIn, db: Session = Depends(obtener_db)
) -> dict:
    ins = db.get(Inscripcion, inscripcion_id)
    if not ins:
        raise HTTPException(404, "Inscripción no encontrada.")
    ins.calificacion_final = datos.calificacion_final
    ins.estado = "aprobada" if datos.calificacion_final >= 70 else "reprobada"
    db.commit()
    return {"ok": True, "calificacion_final": ins.calificacion_final, "estado": ins.estado}


@app.post("/api/docente/inscripciones/{inscripcion_id}/asistencia")
def registrar_asistencia(
    inscripcion_id: int, datos: AsistenciaIn, db: Session = Depends(obtener_db)
) -> dict:
    ins = db.get(Inscripcion, inscripcion_id)
    if not ins:
        raise HTTPException(404, "Inscripción no encontrada.")
    db.add(Asistencia(inscripcion_id=ins.id, fecha=datos.fecha, presente=datos.presente))
    db.commit()
    return {"ok": True}


# ─────────────────────── 6. Trámites por Alumno (9 dígitos) ───────────────────

def _serializar_solicitud(s: SolicitudTramite, tramites_map: dict[str, str]) -> dict:
    return {
        "id": s.id,
        "folio": s.folio,
        "numero_control": s.alumno.numero_control,
        "alumno": s.alumno.nombre_completo,
        "carrera": s.alumno.carrera,
        "tramite_clave": s.tramite_clave,
        "tramite_nombre": tramites_map.get(s.tramite_clave, s.tramite_clave),
        "area_destino": s.area_destino,
        "motivo": s.motivo,
        "estado": s.estado,
        "creado_en": s.creado_en.strftime("%Y-%m-%d %H:%M") if s.creado_en else "",
    }


@app.get("/api/tramites/solicitudes")
def listar_solicitudes(
    numero_control: str | None = None, db: Session = Depends(obtener_db)
) -> list[dict]:
    tramites_map = {t.clave: t.nombre for t in db.scalars(select(Tramite)).all()}
    consulta = select(SolicitudTramite).order_by(SolicitudTramite.id.desc())
    if numero_control:
        alumno = db.scalar(
            select(Alumno).where(Alumno.numero_control == numero_control.strip())
        )
        if not alumno:
            return []
        consulta = consulta.where(SolicitudTramite.alumno_id == alumno.id)
    solicitudes = db.scalars(consulta).all()
    return [_serializar_solicitud(s, tramites_map) for s in solicitudes]


@app.get("/api/tramites/alumno/{numero_control}")
def listar_solicitudes_por_alumno(
    numero_control: str, db: Session = Depends(obtener_db)
) -> list[dict]:
    """Devuelve todos los trámites registrados para una matrícula específica."""
    return listar_solicitudes(numero_control=numero_control, db=db)


@app.post("/api/tramites/solicitudes")
def crear_solicitud(datos: NuevaSolicitudIn, db: Session = Depends(obtener_db)) -> dict:
    alumno = _obtener_o_crear_alumno(
        db,
        datos.numero_control,
        datos.nombre_alumno,
        datos.carrera,
    )
    total = len(db.scalars(select(SolicitudTramite)).all()) + 1
    folio = f"SOL-2026-{total:04d}"
    sol = SolicitudTramite(
        folio=folio,
        alumno_id=alumno.id,
        tramite_clave=datos.tramite_clave,
        area_destino=datos.area_destino,
        motivo=datos.motivo,
        estado="pendiente",
    )
    db.add(sol)
    db.commit()
    db.refresh(sol)
    tramites_map = {t.clave: t.nombre for t in db.scalars(select(Tramite)).all()}
    return {
        "ok": True,
        "folio": folio,
        "solicitud": _serializar_solicitud(sol, tramites_map),
    }


@app.patch("/api/tramites/solicitudes/{solicitud_id}")
def cambiar_estado_solicitud(
    solicitud_id: int, datos: EstadoSolicitudIn, db: Session = Depends(obtener_db)
) -> dict:
    sol = db.get(SolicitudTramite, solicitud_id)
    if not sol:
        raise HTTPException(404, "Solicitud no encontrada.")
    sol.estado = datos.estado
    db.commit()
    return {"ok": True, "estado": sol.estado}


# ──────────────────── 7. Biblioteca (Consultar y Agregar Libros) ──────────────

@app.get("/api/biblioteca")
def modulo_biblioteca(db: Session = Depends(obtener_db)) -> dict:
    libros = db.scalars(select(Libro).order_by(Libro.id.desc())).all()
    prestamos = db.scalars(select(PrestamoBiblioteca).order_by(PrestamoBiblioteca.id.desc())).all()
    return {
        "libros": [
            {
                "id": l.id,
                "codigo": l.codigo,
                "titulo": l.titulo,
                "autor": l.autor,
                "categoria": l.categoria,
                "carrera": l.carrera,
                "ejemplares_disponibles": l.ejemplares_disponibles,
                "url_recurso": l.url_recurso or "",
            }
            for l in libros
        ],
        "prestamos": [
            {
                "id": p.id,
                "numero_control": p.alumno.numero_control,
                "alumno": p.alumno.nombre_completo,
                "libro": p.libro.titulo,
                "fecha_prestamo": p.fecha_prestamo,
                "fecha_devolucion": p.fecha_devolucion,
                "multa_mxn": p.multa_mxn,
                "estado": p.estado,
            }
            for p in prestamos
        ],
    }


@app.post("/api/biblioteca/libros")
def agregar_libro(datos: NuevoLibroIn, db: Session = Depends(obtener_db)) -> dict:
    """Agrega un nuevo libro o recurso digital al catálogo de biblioteca."""
    codigo = (datos.codigo or f"LIB-{uuid.uuid4().hex[:6].upper()}").strip().upper()
    existente = db.scalar(select(Libro).where(Libro.codigo == codigo))
    if existente:
        existente.ejemplares_disponibles += datos.ejemplares_disponibles
        db.commit()
        db.refresh(existente)
        return {"ok": True, "id": existente.id, "codigo": existente.codigo, "actualizado": True}

    nuevo_libro = Libro(
        codigo=codigo,
        titulo=datos.titulo,
        autor=datos.autor,
        categoria=datos.categoria,
        carrera=datos.carrera,
        ejemplares_disponibles=datos.ejemplares_disponibles,
        url_recurso=datos.url_recurso,
    )
    db.add(nuevo_libro)
    db.commit()
    db.refresh(nuevo_libro)
    return {
        "ok": True,
        "libro": {
            "id": nuevo_libro.id,
            "codigo": nuevo_libro.codigo,
            "titulo": nuevo_libro.titulo,
            "autor": nuevo_libro.autor,
            "categoria": nuevo_libro.categoria,
            "carrera": nuevo_libro.carrera,
            "ejemplares_disponibles": nuevo_libro.ejemplares_disponibles,
            "url_recurso": nuevo_libro.url_recurso or "",
        },
    }


@app.post("/api/biblioteca/prestar")
def prestar_libro(datos: NuevoPrestamoIn, db: Session = Depends(obtener_db)) -> dict:
    alumno = _obtener_o_crear_alumno(db, datos.numero_control)
    libro = db.get(Libro, datos.libro_id)
    if not libro or libro.ejemplares_disponibles <= 0:
        raise HTTPException(400, "No hay ejemplares disponibles.")
    libro.ejemplares_disponibles -= 1
    db.add(
        PrestamoBiblioteca(
            alumno_id=alumno.id,
            libro_id=libro.id,
            fecha_prestamo="2026-11-26",
            estado="activo",
        )
    )
    db.commit()
    return {"ok": True}


@app.patch("/api/biblioteca/prestamos/{prestamo_id}/devolver")
def devolver_libro(prestamo_id: int, db: Session = Depends(obtener_db)) -> dict:
    prestamo = db.get(PrestamoBiblioteca, prestamo_id)
    if not prestamo or prestamo.estado == "devuelto":
        raise HTTPException(400, "Préstamo inválido o ya devuelto.")
    prestamo.estado = "devuelto"
    prestamo.fecha_devolucion = "2026-11-26"
    prestamo.multa_mxn = 0.0
    prestamo.libro.ejemplares_disponibles += 1
    db.commit()
    return {"ok": True}


# ──────────────────── 8. Finanzas, Reinscripción y Banamex ────────────────────

@app.get("/api/finanzas/datos-bancarios")
def obtener_datos_bancarios() -> dict:
    """Datos oficiales Banamex para pagos y reinscripción TecNM Iztapalapa III."""
    return {
        "url_banamex": "https://www.banamex.com/",
        "practicaja": {
            "metodo": "Caja o Practicaja en Banco Banamex",
            "banco": "Banamex",
            "numero_cuenta": "7013 758639",
            "nombre": "Instituto Tecnológico de Iztapalapa III",
            "referencia": "Número de control (9 dígitos)",
        },
        "transferencia": {
            "metodo": "Transferencia Electrónica (SPEI)",
            "banco": "Banamex",
            "clabe": "002180701307586392",
            "nombre": "Instituto Tecnológico de Iztapalapa III",
            "referencia": "Número de control (9 dígitos)",
        },
    }


@app.get("/api/finanzas")
def modulo_finanzas(db: Session = Depends(obtener_db)) -> list[dict]:
    pagos = db.scalars(select(Pago).order_by(Pago.id.desc())).all()
    return [
        {
            "id": p.id,
            "numero_control": p.alumno.numero_control,
            "alumno": p.alumno.nombre_completo,
            "estatus_inscripcion_alumno": p.alumno.estatus_inscripcion,
            "concepto": p.concepto,
            "periodo": p.periodo,
            "estatus": p.estatus,
        }
        for p in pagos
    ]


@app.post("/api/finanzas/pagos")
def registrar_pago(datos: NuevoPagoIn, db: Session = Depends(obtener_db)) -> dict:
    alumno = _obtener_o_crear_alumno(
        db,
        datos.numero_control,
        datos.nombre_alumno,
        datos.carrera,
    )
    db.add(
        Pago(
            alumno_id=alumno.id,
            concepto=datos.concepto,
            periodo=datos.periodo,
            estatus="en_validacion",
        )
    )
    db.commit()
    return {"ok": True, "referencia": alumno.numero_control}


@app.patch("/api/finanzas/pagos/{pago_id}/validar")
def validar_pago_integrado(pago_id: int, db: Session = Depends(obtener_db)) -> dict:
    """Integración Tesorería -> Control Escolar (Etapa 4 SIGU)."""
    pago = db.get(Pago, pago_id)
    if not pago:
        raise HTTPException(404, "Pago no encontrado.")
    pago.estatus = "validado"
    pago.alumno.estatus_inscripcion = "inscrito"
    for ins in pago.alumno.inscripciones:
        if ins.estado == "pendiente_pago":
            ins.estado = "cursando"
    db.commit()
    return {"ok": True, "alumno": pago.alumno.nombre_completo, "estatus_inscripcion": "inscrito"}


# ─────────────── 9. Avisos Conectados al Portal Oficial TecNM ─────────────────

@app.get("/api/avisos-oficiales")
async def obtener_avisos_oficiales(db: Session = Depends(obtener_db)) -> dict:
    """Extrae comunicados vigentes desde https://iztapalapa3.tecnm.mx/ con respaldo local."""
    avisos_web: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(PORTAL_OFICIAL_URL)
            if resp.status_code == 200:
                enlaces = re.findall(
                    r'<a[^>]+href=["\'](https?://iztapalapa3\.tecnm\.mx/[^"\']+)["\'][^>]*>(.*?)</a>',
                    resp.text,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                vistos: set[str] = set()
                for href, contenido_html in enlaces:
                    titulo = re.sub(r"<[^>]+>", "", html.unescape(contenido_html)).strip()
                    titulo = re.sub(r"\s+", " ", titulo)
                    if (
                        len(titulo) >= 18
                        and titulo.lower() not in vistos
                        and not href.lower().endswith((".jpg", ".png", ".jpeg", ".webp"))
                    ):
                        vistos.add(titulo.lower())
                        avisos_web.append(
                            {
                                "titulo": titulo,
                                "url": href,
                                "area_clave": "OFICIAL",
                                "fuente": "Portal Oficial TecNM Iztapalapa III",
                            }
                        )
                    if len(avisos_web) >= 8:
                        break
    except Exception:
        pass

    avisos_bd = db.scalars(
        select(AvisoInstitucional).order_by(AvisoInstitucional.id.desc())
    ).all()
    locales = [
        {
            "id": av.id,
            "titulo": av.titulo,
            "area_clave": av.area_clave,
            "contenido": av.contenido,
            "url": av.url_origen or PORTAL_OFICIAL_URL,
            "publicado_en": av.publicado_en.strftime("%Y-%m-%d") if av.publicado_en else "",
        }
        for av in avisos_bd
    ]

    return {
        "portal_oficial": PORTAL_OFICIAL_URL,
        "avisos_web": avisos_web,
        "avisos_locales": locales,
    }


@app.post("/api/avisos")
def crear_aviso(datos: NuevoAvisoIn, db: Session = Depends(obtener_db)) -> dict:
    db.add(
        AvisoInstitucional(
            titulo=datos.titulo,
            area_clave=datos.area_clave.upper(),
            contenido=datos.contenido,
            url_origen=datos.url_origen or PORTAL_OFICIAL_URL,
        )
    )
    db.commit()
    return {"ok": True}
