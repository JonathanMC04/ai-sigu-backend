"""Puebla la base de datos de AI-SIGU con datos ficticios y catálogo de TecNM Iztapalapa III."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from models import Alumno, Area, Base, Pago, Requisito, Tramite

DATABASE_URL = "sqlite:///./ai_sigu.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


AREAS_DATA = [
    {"clave": "DEP", "nombre": "División de Estudios Profesionales", "correo": "dep_iztapalapa3@tecnm.mx"},
    {"clave": "SE", "nombre": "Servicios Escolares", "correo": "se_iztapalapa3@tecnm.mx"},
    {"clave": "DDA", "nombre": "Desarrollo Académico", "correo": "dda_iztapalapa3@tecnm.mx"},
    {"clave": "CC", "nombre": "Centro de Cómputo", "correo": "cc_iztapalapa3@tecnm.mx"},
    {"clave": "RF", "nombre": "Recursos Financieros", "correo": "rf_iztapalapa3@tecnm.mx"},
    {"clave": "VIN", "nombre": "Vinculación", "correo": "vin_iztapalapa3@tecnm.mx"},
    {"clave": "CBAS", "nombre": "Ciencias Básicas", "correo": "cbas_iztapalapa3@tecnm.mx"},
]

TRAMITES_DATA = [
    # DEP
    {"clave": "dep_titulacion", "nombre": "Inicio de proceso de titulación", "area": "DEP", "audiencia": "alumno", "reqs": []},
    {"clave": "dep_comite", "nombre": "Solicitud a Comité académico", "area": "DEP", "audiencia": "alumno", "reqs": []},
    {"clave": "dep_mindbox", "nombre": "Cargas académicas en Mindbox", "area": "DEP", "audiencia": "alumno", "reqs": []},
    {"clave": "dep_horarios", "nombre": "Horarios", "area": "DEP", "audiencia": "alumno", "reqs": []},
    {"clave": "dep_residencia", "nombre": "Residencia profesional", "area": "DEP", "audiencia": "alumno", "reqs": []},
    {"clave": "dep_revisores", "nombre": "Asignación de Revisores de residencia profesional", "area": "DEP", "audiencia": "alumno", "reqs": []},
    {"clave": "dep_boletas", "nombre": "Boletas", "area": "DEP", "audiencia": "alumno", "reqs": []},
    {"clave": "dep_calif_residencia", "nombre": "Calificación final de Residencia Profesional", "area": "DEP", "audiencia": "alumno", "reqs": []},
    # SE
    {"clave": "se_becas", "nombre": "Becas", "area": "SE", "audiencia": "alumno", "reqs": []},
    {"clave": "se_subes", "nombre": "Validación en la plataforma SUBES", "area": "SE", "audiencia": "alumno", "reqs": []},
    {"clave": "se_mindbox_acceso", "nombre": "Usuario y contraseña de la plataforma Mindbox", "area": "SE", "audiencia": "alumno", "reqs": []},
    {
        "clave": "se_correccion_calif",
        "nombre": "Corrección de calificaciones",
        "area": "SE",
        "audiencia": "alumno",
        "reqs": [
            {"descripcion": "Evidencia de boleta oficial con la calificación aprobatoria", "es_evidencia": True},
            {"descripcion": "Oficio por parte del docente para la corrección de calificación", "es_evidencia": True},
        ],
    },
    {"clave": "se_correccion_kardex", "nombre": "Corrección de Kardex", "area": "SE", "audiencia": "alumno", "reqs": []},
    {"clave": "se_certificado", "nombre": "Trámite de certificado", "area": "SE", "audiencia": "alumno", "reqs": []},
    {"clave": "se_titulo_cedula", "nombre": "Título y cédula profesional", "area": "SE", "audiencia": "alumno", "reqs": []},
    {"clave": "se_num_control", "nombre": "Asignación de número de control", "area": "SE", "audiencia": "aspirante", "reqs": []},
    {"clave": "se_constancias", "nombre": "Solicitud de constancias", "area": "SE", "audiencia": "alumno", "reqs": []},
    {"clave": "se_kardex", "nombre": "Solicitud de kardex", "area": "SE", "audiencia": "alumno", "reqs": []},
    {"clave": "se_creditos_comp", "nombre": "Liberación de créditos complementarios", "area": "SE", "audiencia": "alumno", "reqs": []},
    # DDA
    {"clave": "dda_fichas", "nombre": "Fichas de nuevo ingreso", "area": "DDA", "audiencia": "aspirante", "reqs": []},
    {"clave": "dda_tutorias", "nombre": "Tutorías", "area": "DDA", "audiencia": "alumno", "reqs": []},
    {"clave": "dda_cambio_tutor", "nombre": "Asignación y cambio de tutores", "area": "DDA", "audiencia": "alumno", "reqs": []},
    {"clave": "dda_info_ingreso", "nombre": "Solicitud de información para nuevo Ingreso", "area": "DDA", "audiencia": "aspirante", "reqs": []},
    {"clave": "dda_examen_admision", "nombre": "Examen de admisión", "area": "DDA", "audiencia": "aspirante", "reqs": []},
    # CC
    {"clave": "cc_correo_oficial", "nombre": "Correo oficial", "area": "CC", "audiencia": "ambos", "reqs": []},
    {"clave": "cc_recuperar_pass", "nombre": "Recuperación de contraseña", "area": "CC", "audiencia": "ambos", "reqs": []},
    {"clave": "cc_teams", "nombre": "Problemas con la plataforma Teams", "area": "CC", "audiencia": "ambos", "reqs": []},
    # RF
    {"clave": "rf_validar_pagos", "nombre": "Validación de pagos en la plataforma Mindbox", "area": "RF", "audiencia": "alumno", "reqs": []},
    {"clave": "rf_pago_titulacion", "nombre": "Pagos de titulación", "area": "RF", "audiencia": "alumno", "reqs": []},
    {"clave": "rf_pago_constancias", "nombre": "Pago de constancias", "area": "RF", "audiencia": "alumno", "reqs": []},
    {"clave": "rf_pago_kardex", "nombre": "Pago de Kardex", "area": "RF", "audiencia": "alumno", "reqs": []},
    {"clave": "rf_pago_certificado", "nombre": "Pago de certificado", "area": "RF", "audiencia": "alumno", "reqs": []},
    {"clave": "rf_prorrogas", "nombre": "Prórrogas", "area": "RF", "audiencia": "alumno", "reqs": []},
    # VIN
    {"clave": "vin_servicio_social", "nombre": "Servicio Social", "area": "VIN", "audiencia": "alumno", "reqs": []},
    {"clave": "vin_calif_social", "nombre": "Calificación de Social en Mindbox", "area": "VIN", "audiencia": "alumno", "reqs": []},
    {"clave": "vin_residencia_cartas", "nombre": "Residencia Profesional (Carta de Presentación, Inicio y Término)", "area": "VIN", "audiencia": "alumno", "reqs": []},
    {"clave": "vin_ingles", "nombre": "Liberación del idioma Ingles", "area": "VIN", "audiencia": "alumno", "reqs": []},
    # CBAS
    {"clave": "cbas_creditos", "nombre": "Créditos académicos", "area": "CBAS", "audiencia": "alumno", "reqs": []},
    {"clave": "cbas_propedeutico", "nombre": "Curso propedéutico", "area": "CBAS", "audiencia": "aspirante", "reqs": []},
    {"clave": "cbas_remedial", "nombre": "Curso remedial", "area": "CBAS", "audiencia": "alumno", "reqs": []},
]


def run_seed():
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        if db.query(Area).first():
            print("La base de datos ya contiene datos. No se duplicaron registros.")
            return

        for a in AREAS_DATA:
            db.add(Area(clave=a["clave"], nombre=a["nombre"], correo=a["correo"]))
        db.flush()

        for t in TRAMITES_DATA:
            tramite = Tramite(
                clave=t["clave"],
                nombre=t["nombre"],
                area_clave=t["area"],
                audiencia=t["audiencia"],
                requisitos_verificados=True,
            )
            for idx, req in enumerate(t["reqs"], start=1):
                tramite.requisitos.append(
                    Requisito(
                        orden=idx,
                        descripcion=req["descripcion"],
                        es_evidencia=req["es_evidencia"],
                    )
                )
            db.add(tramite)

        alumno_1 = Alumno(
            numero_control="25120001",
            nombre_completo="Carlos Mendoza Ruiz",
            carrera="Ingeniería en Informática",
            semestre=3,
            correo_institucional="l25120001@iztapalapa3.tecnm.mx",
            estatus_inscripcion="inscrito",
        )
        alumno_2 = Alumno(
            numero_control="24120045",
            nombre_completo="Ana Sofía López Herrera",
            carrera="Ingeniería en Informática",
            semestre=5,
            correo_institucional=None,
            estatus_inscripcion="no_inscrito",
        )
        db.add_all([alumno_1, alumno_2])
        db.flush()

        db.add_all([
            Pago(alumno_id=alumno_1.id, concepto="Inscripción semestral", periodo="2026-2", estatus="validado"),
            Pago(alumno_id=alumno_2.id, concepto="Constancia de estudios", periodo="2026-2", estatus="en_validacion"),
        ])

        db.commit()
        print("Seed completado con éxito en ai_sigu.db.")


if __name__ == "__main__":
    run_seed()
    """Puebla la base de datos de AI-SIGU con datos ficticios y catálogo de TecNM Iztapalapa III."""
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from models import (
    Alumno,
    Area,
    Asistencia,
    AvisoInstitucional,
    Base,
    Docente,
    Inscripcion,
    Libro,
    Materia,
    Pago,
    PrestamoBiblioteca,
    Requisito,
    SolicitudTramite,
    Tramite,
)

DATABASE_URL = "sqlite:///./ai_sigu.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


AREAS_DATA = [
    {"clave": "DEP", "nombre": "División de Estudios Profesionales", "correo": "dep_iztapalapa3@tecnm.mx"},
    {"clave": "SE", "nombre": "Servicios Escolares", "correo": "se_iztapalapa3@tecnm.mx"},
    {"clave": "DDA", "nombre": "Desarrollo Académico", "correo": "dda_iztapalapa3@tecnm.mx"},
    {"clave": "CC", "nombre": "Centro de Cómputo", "correo": "cc_iztapalapa3@tecnm.mx"},
    {"clave": "RF", "nombre": "Recursos Financieros", "correo": "rf_iztapalapa3@tecnm.mx"},
    {"clave": "VIN", "nombre": "Vinculación", "correo": "vin_iztapalapa3@tecnm.mx"},
    {"clave": "CBAS", "nombre": "Ciencias Básicas", "correo": "cbas_iztapalapa3@tecnm.mx"},
]

TRAMITES_DATA = [
    # DEP
    {"clave": "dep_titulacion", "nombre": "Inicio de proceso de titulación", "area": "DEP", "audiencia": "alumno", "reqs": []},
    {"clave": "dep_comite", "nombre": "Solicitud a Comité académico", "area": "DEP", "audiencia": "alumno", "reqs": []},
    {"clave": "dep_mindbox", "nombre": "Cargas académicas en Mindbox", "area": "DEP", "audiencia": "alumno", "reqs": []},
    {"clave": "dep_horarios", "nombre": "Horarios", "area": "DEP", "audiencia": "alumno", "reqs": []},
    {"clave": "dep_residencia", "nombre": "Residencia profesional", "area": "DEP", "audiencia": "alumno", "reqs": []},
    {"clave": "dep_revisores", "nombre": "Asignación de Revisores de residencia profesional", "area": "DEP", "audiencia": "alumno", "reqs": []},
    {"clave": "dep_boletas", "nombre": "Boletas", "area": "DEP", "audiencia": "alumno", "reqs": []},
    {"clave": "dep_calif_residencia", "nombre": "Calificación final de Residencia Profesional", "area": "DEP", "audiencia": "alumno", "reqs": []},
    # SE
    {"clave": "se_becas", "nombre": "Becas", "area": "SE", "audiencia": "alumno", "reqs": []},
    {"clave": "se_subes", "nombre": "Validación en la plataforma SUBES", "area": "SE", "audiencia": "alumno", "reqs": []},
    {"clave": "se_mindbox_acceso", "nombre": "Usuario y contraseña de la plataforma Mindbox", "area": "SE", "audiencia": "alumno", "reqs": []},
    {
        "clave": "se_correccion_calif",
        "nombre": "Corrección de calificaciones",
        "area": "SE",
        "audiencia": "alumno",
        "reqs": [
            {"descripcion": "Evidencia de boleta oficial con la calificación aprobatoria", "es_evidencia": True},
            {"descripcion": "Oficio por parte del docente para la corrección de calificación", "es_evidencia": True},
        ],
    },
    {"clave": "se_correccion_kardex", "nombre": "Corrección de Kardex", "area": "SE", "audiencia": "alumno", "reqs": []},
    {"clave": "se_certificado", "nombre": "Trámite de certificado", "area": "SE", "audiencia": "alumno", "reqs": []},
    {"clave": "se_titulo_cedula", "nombre": "Título y cédula profesional", "area": "SE", "audiencia": "alumno", "reqs": []},
    {"clave": "se_num_control", "nombre": "Asignación de número de control", "area": "SE", "audiencia": "aspirante", "reqs": []},
    {"clave": "se_constancias", "nombre": "Solicitud de constancias", "area": "SE", "audiencia": "alumno", "reqs": []},
    {"clave": "se_kardex", "nombre": "Solicitud de kardex", "area": "SE", "audiencia": "alumno", "reqs": []},
    {"clave": "se_creditos_comp", "nombre": "Liberación de créditos complementarios", "area": "SE", "audiencia": "alumno", "reqs": []},
    # DDA
    {"clave": "dda_fichas", "nombre": "Fichas de nuevo ingreso", "area": "DDA", "audiencia": "aspirante", "reqs": []},
    {"clave": "dda_tutorias", "nombre": "Tutorías", "area": "DDA", "audiencia": "alumno", "reqs": []},
    {"clave": "dda_cambio_tutor", "nombre": "Asignación y cambio de tutores", "area": "DDA", "audiencia": "alumno", "reqs": []},
    {"clave": "dda_info_ingreso", "nombre": "Solicitud de información para nuevo Ingreso", "area": "DDA", "audiencia": "aspirante", "reqs": []},
    {"clave": "dda_examen_admision", "nombre": "Examen de admisión", "area": "DDA", "audiencia": "aspirante", "reqs": []},
    # CC
    {"clave": "cc_correo_oficial", "nombre": "Correo oficial", "area": "CC", "audiencia": "ambos", "reqs": []},
    {"clave": "cc_recuperar_pass", "nombre": "Recuperación de contraseña", "area": "CC", "audiencia": "ambos", "reqs": []},
    {"clave": "cc_teams", "nombre": "Problemas con la plataforma Teams", "area": "CC", "audiencia": "ambos", "reqs": []},
    # RF
    {"clave": "rf_validar_pagos", "nombre": "Validación de pagos en la plataforma Mindbox", "area": "RF", "audiencia": "alumno", "reqs": []},
    {"clave": "rf_pago_titulacion", "nombre": "Pagos de titulación", "area": "RF", "audiencia": "alumno", "reqs": []},
    {"clave": "rf_pago_constancias", "nombre": "Pago de constancias", "area": "RF", "audiencia": "alumno", "reqs": []},
    {"clave": "rf_pago_kardex", "nombre": "Pago de Kardex", "area": "RF", "audiencia": "alumno", "reqs": []},
    {"clave": "rf_pago_certificado", "nombre": "Pago de certificado", "area": "RF", "audiencia": "alumno", "reqs": []},
    {"clave": "rf_prorrogas", "nombre": "Prórrogas", "area": "RF", "audiencia": "alumno", "reqs": []},
    # VIN
    {"clave": "vin_servicio_social", "nombre": "Servicio Social", "area": "VIN", "audiencia": "alumno", "reqs": []},
    {"clave": "vin_calif_social", "nombre": "Calificación de Social en Mindbox", "area": "VIN", "audiencia": "alumno", "reqs": []},
    {"clave": "vin_residencia_cartas", "nombre": "Residencia Profesional (Carta de Presentación, Inicio y Término)", "area": "VIN", "audiencia": "alumno", "reqs": []},
    {"clave": "vin_ingles", "nombre": "Liberación del idioma Ingles", "area": "VIN", "audiencia": "alumno", "reqs": []},
    # CBAS
    {"clave": "cbas_creditos", "nombre": "Créditos académicos", "area": "CBAS", "audiencia": "alumno", "reqs": []},
    {"clave": "cbas_propedeutico", "nombre": "Curso propedéutico", "area": "CBAS", "audiencia": "aspirante", "reqs": []},
    {"clave": "cbas_remedial", "nombre": "Curso remedial", "area": "CBAS", "audiencia": "alumno", "reqs": []},
]


def run_seed():
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        if not db.scalar(select(Area.clave).limit(1)):
            for a in AREAS_DATA:
                db.add(Area(clave=a["clave"], nombre=a["nombre"], correo=a["correo"]))
            db.flush()

            for t in TRAMITES_DATA:
                tramite = Tramite(
                    clave=t["clave"],
                    nombre=t["nombre"],
                    area_clave=t["area"],
                    audiencia=t["audiencia"],
                    requisitos_verificados=True,
                )
                for idx, req in enumerate(t["reqs"], start=1):
                    tramite.requisitos.append(
                        Requisito(
                            orden=idx,
                            descripcion=req["descripcion"],
                            es_evidencia=req["es_evidencia"],
                        )
                    )
                db.add(tramite)

            alumno_1 = Alumno(
                numero_control="25120001",
                nombre_completo="Carlos Mendoza Ruiz",
                carrera="Ingeniería en Informática",
                semestre=3,
                correo_institucional="l25120001@iztapalapa3.tecnm.mx",
                estatus_inscripcion="inscrito",
            )
            alumno_2 = Alumno(
                numero_control="24120045",
                nombre_completo="Ana Sofía López Herrera",
                carrera="Ingeniería en Informática",
                semestre=5,
                correo_institucional=None,
                estatus_inscripcion="no_inscrito",
            )
            db.add_all([alumno_1, alumno_2])
            db.flush()

            db.add_all([
                Pago(alumno_id=alumno_1.id, concepto="Inscripción semestral", periodo="2026-2", estatus="validado"),
                Pago(alumno_id=alumno_2.id, concepto="Constancia de estudios", periodo="2026-2", estatus="en_validacion"),
            ])
            db.flush()
        else:
            alumno_1 = db.scalar(select(Alumno).where(Alumno.numero_control == "25120001"))
            alumno_2 = db.scalar(select(Alumno).where(Alumno.numero_control == "24120045"))

        if not db.scalar(select(Docente.id).limit(1)) and alumno_1 and alumno_2:
            doc_1 = Docente(
                matricula="DOC-101",
                nombre_completo="Mtra. Elena Ramírez Soto",
                especialidad="Ingeniería de Software y Bases de Datos",
                correo="eramirez@iztapalapa3.tecnm.mx",
            )
            doc_2 = Docente(
                matricula="DOC-102",
                nombre_completo="Ing. Jorge Alberto Cruz",
                especialidad="Sistemas Embebidos y Redes",
                correo="jcruz@iztapalapa3.tecnm.mx",
            )
            db.add_all([doc_1, doc_2])
            db.flush()

            mat_1 = Materia(
                clave="IF-301",
                nombre="Estructura de Datos",
                creditos=5,
                semestre_sugerido=3,
                horario="Lun-Mie 09:00-11:00",
                docente_id=doc_1.id,
            )
            mat_2 = Materia(
                clave="IF-502",
                nombre="Ingeniería de Software",
                creditos=5,
                semestre_sugerido=5,
                horario="Mar-Jue 11:00-13:00",
                docente_id=doc_1.id,
            )
            mat_3 = Materia(
                clave="IF-304",
                nombre="Arquitectura de Computadoras",
                creditos=4,
                semestre_sugerido=3,
                horario="Vie 08:00-12:00",
                docente_id=doc_2.id,
            )
            db.add_all([mat_1, mat_2, mat_3])
            db.flush()

            ins_1 = Inscripcion(
                alumno_id=alumno_1.id,
                materia_id=mat_1.id,
                periodo="2026-2",
                calificacion_final=92.0,
                estado="cursando",
            )
            ins_2 = Inscripcion(
                alumno_id=alumno_2.id,
                materia_id=mat_2.id,
                periodo="2026-2",
                calificacion_final=None,
                estado="pendiente_pago",
            )
            db.add_all([ins_1, ins_2])
            db.flush()

            db.add_all([
                Asistencia(inscripcion_id=ins_1.id, fecha="2026-11-18", presente=True),
                Asistencia(inscripcion_id=ins_1.id, fecha="2026-11-20", presente=True),
                Asistencia(inscripcion_id=ins_2.id, fecha="2026-11-19", presente=False),
            ])

            lib_1 = Libro(
                codigo="BIB-001",
                titulo="Fundamentos de Ingeniería de Software",
                autor="Ian Sommerville",
                ejemplares_disponibles=3,
            )
            lib_2 = Libro(
                codigo="BIB-002",
                titulo="Sistemas de Bases de Datos",
                autor="Abraham Silberschatz",
                ejemplares_disponibles=2,
            )
            db.add_all([lib_1, lib_2])
            db.flush()

            db.add_all([
                PrestamoBiblioteca(
                    alumno_id=alumno_1.id,
                    libro_id=lib_1.id,
                    fecha_prestamo="2026-11-10",
                    fecha_devolucion=None,
                    multa_mxn=0.0,
                    estado="activo",
                ),
                PrestamoBiblioteca(
                    alumno_id=alumno_2.id,
                    libro_id=lib_2.id,
                    fecha_prestamo="2026-10-20",
                    fecha_devolucion=None,
                    multa_mxn=25.0,
                    estado="retrasado",
                ),
            ])

            db.add_all([
                SolicitudTramite(
                    folio="SOL-2026-0001",
                    alumno_id=alumno_1.id,
                    tramite_clave="se_constancias",
                    motivo="Constancia de estudios con promedio para trámite de beca.",
                    estado="en_revision",
                ),
                SolicitudTramite(
                    folio="SOL-2026-0002",
                    alumno_id=alumno_2.id,
                    tramite_clave="rf_validar_pagos",
                    motivo="Validación de comprobante de pago de constancia.",
                    estado="pendiente",
                ),
            ])

            db.add_all([
                AvisoInstitucional(
                    titulo="Cierre de validación de pagos en Mindbox",
                    area_clave="RF",
                    contenido="Recuerda subir tu comprobante legible en Mindbox para habilitar cargas y trámites en Servicios Escolares.",
                ),
                AvisoInstitucional(
                    titulo="Entrega de evidencias para trámites escolares",
                    area_clave="SE",
                    contenido="Verifica tus evidencias antes de solicitar constancias, kardex o corrección de calificaciones.",
                ),
            ])

        db.commit()
        print("Seed SIGU completado con éxito en ai_sigu.db.")


if __name__ == "__main__":
    run_seed()