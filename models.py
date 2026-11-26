"""Modelos ORM de AI-SIGU para TecNM Campus Iztapalapa III."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ─────────────────────────── Modelos base existentes ───────────────────────────

class Area(Base):
    __tablename__ = "areas"

    clave: Mapped[str] = mapped_column(String(10), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    correo: Mapped[str] = mapped_column(String(120), nullable=False)

    tramites: Mapped[list["Tramite"]] = relationship(back_populates="area")


class Tramite(Base):
    __tablename__ = "tramites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clave: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    area_clave: Mapped[str] = mapped_column(ForeignKey("areas.clave"), nullable=False)
    audiencia: Mapped[str] = mapped_column(String(20), nullable=False)
    requisitos_verificados: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    area: Mapped["Area"] = relationship(back_populates="tramites")
    requisitos: Mapped[list["Requisito"]] = relationship(
        back_populates="tramite",
        cascade="all, delete-orphan",
        order_by="Requisito.orden",
    )


class Requisito(Base):
    __tablename__ = "requisitos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tramite_id: Mapped[int] = mapped_column(ForeignKey("tramites.id"), nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    es_evidencia: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    tramite: Mapped["Tramite"] = relationship(back_populates="requisitos")


class Alumno(Base):
    __tablename__ = "alumnos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    numero_control: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nombre_completo: Mapped[str] = mapped_column(String(150), nullable=False)
    carrera: Mapped[str] = mapped_column(String(120), nullable=False)
    semestre: Mapped[int] = mapped_column(Integer, nullable=False)
    correo_institucional: Mapped[str | None] = mapped_column(String(120), nullable=True)
    estatus_inscripcion: Mapped[str] = mapped_column(String(30), default="no_inscrito", nullable=False)

    pagos: Mapped[list["Pago"]] = relationship(back_populates="alumno", cascade="all, delete-orphan")
    inscripciones: Mapped[list["Inscripcion"]] = relationship(back_populates="alumno", cascade="all, delete-orphan")
    prestamos: Mapped[list["PrestamoBiblioteca"]] = relationship(back_populates="alumno", cascade="all, delete-orphan")
    solicitudes: Mapped[list["SolicitudTramite"]] = relationship(back_populates="alumno", cascade="all, delete-orphan")


class Pago(Base):
    __tablename__ = "pagos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alumno_id: Mapped[int] = mapped_column(ForeignKey("alumnos.id"), nullable=False)
    concepto: Mapped[str] = mapped_column(String(120), nullable=False)
    periodo: Mapped[str] = mapped_column(String(20), nullable=False)
    estatus: Mapped[str] = mapped_column(String(30), nullable=False)

    alumno: Mapped["Alumno"] = relationship(back_populates="pagos")

class Folio(Base):
    __tablename__ = "folios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    tramite_clave: Mapped[str] = mapped_column(String(60), nullable=False)
    alumno_id: Mapped[int | None] = mapped_column(ForeignKey("alumnos.id"), nullable=True)
    estado: Mapped[str] = mapped_column(String(30), default="borrador", nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
# ────────────────────── Nuevos modelos SIGU (módulos) ──────────────────────

class Docente(Base):
    __tablename__ = "docentes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    matricula: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nombre_completo: Mapped[str] = mapped_column(String(150), nullable=False)
    especialidad: Mapped[str] = mapped_column(String(120), nullable=False)
    correo: Mapped[str] = mapped_column(String(120), nullable=False)

    materias: Mapped[list["Materia"]] = relationship(back_populates="docente")


class Materia(Base):
    __tablename__ = "materias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clave: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    creditos: Mapped[int] = mapped_column(Integer, nullable=False)
    semestre_sugerido: Mapped[int] = mapped_column(Integer, nullable=False)
    horario: Mapped[str] = mapped_column(String(80), nullable=False)
    docente_id: Mapped[int | None] = mapped_column(ForeignKey("docentes.id"), nullable=True)

    docente: Mapped["Docente | None"] = relationship(back_populates="materias")
    inscripciones: Mapped[list["Inscripcion"]] = relationship(back_populates="materia", cascade="all, delete-orphan")


class Inscripcion(Base):
    __tablename__ = "inscripciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alumno_id: Mapped[int] = mapped_column(ForeignKey("alumnos.id"), nullable=False)
    materia_id: Mapped[int] = mapped_column(ForeignKey("materias.id"), nullable=False)
    periodo: Mapped[str] = mapped_column(String(20), nullable=False)
    calificacion_final: Mapped[float | None] = mapped_column(nullable=True)
    estado: Mapped[str] = mapped_column(String(30), default="cursando", nullable=False)

    alumno: Mapped["Alumno"] = relationship(back_populates="inscripciones")
    materia: Mapped["Materia"] = relationship(back_populates="inscripciones")
    asistencias: Mapped[list["Asistencia"]] = relationship(back_populates="inscripcion", cascade="all, delete-orphan")


class Asistencia(Base):
    __tablename__ = "asistencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inscripcion_id: Mapped[int] = mapped_column(ForeignKey("inscripciones.id"), nullable=False)
    fecha: Mapped[str] = mapped_column(String(20), nullable=False)
    presente: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    inscripcion: Mapped["Inscripcion"] = relationship(back_populates="asistencias")


class Libro(Base):
    __tablename__ = "libros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    titulo: Mapped[str] = mapped_column(String(180), nullable=False)
    autor: Mapped[str] = mapped_column(String(120), nullable=False)
    ejemplares_disponibles: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    prestamos: Mapped[list["PrestamoBiblioteca"]] = relationship(back_populates="libro", cascade="all, delete-orphan")


class PrestamoBiblioteca(Base):
    __tablename__ = "prestamos_biblioteca"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alumno_id: Mapped[int] = mapped_column(ForeignKey("alumnos.id"), nullable=False)
    libro_id: Mapped[int] = mapped_column(ForeignKey("libros.id"), nullable=False)
    fecha_prestamo: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_devolucion: Mapped[str | None] = mapped_column(String(20), nullable=True)
    multa_mxn: Mapped[float] = mapped_column(default=0.0, nullable=False)
    estado: Mapped[str] = mapped_column(String(30), default="activo", nullable=False)

    alumno: Mapped["Alumno"] = relationship(back_populates="prestamos")
    libro: Mapped["Libro"] = relationship(back_populates="prestamos")


class SolicitudTramite(Base):
    __tablename__ = "solicitudes_tramites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    folio: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    alumno_id: Mapped[int] = mapped_column(ForeignKey("alumnos.id"), nullable=False)
    tramite_clave: Mapped[str] = mapped_column(String(60), nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(String(30), default="pendiente", nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    alumno: Mapped["Alumno"] = relationship(back_populates="solicitudes")


class AvisoInstitucional(Base):
    __tablename__ = "avisos_institucionales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    titulo: Mapped[str] = mapped_column(String(160), nullable=False)
    area_clave: Mapped[str] = mapped_column(String(10), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    publicado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)