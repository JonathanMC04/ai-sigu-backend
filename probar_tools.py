"""Prueba rápida de tools.py. Uso: python probar_tools.py

Usa una base en memoria: no toca ai_sigu.db (el mensaje del seed la menciona igual).
"""
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

import seed
from models import Folio
from tools import (
    ContextoSesion,
    buscar_tramites,
    ejecutar_herramienta,
    listar_tramites_por_area,
)

seed.engine = create_engine("sqlite://")
event.listen(seed.engine, "connect", seed.set_sqlite_pragma)
seed.run_seed()


def claves(texto):
    return {t["clave"] for t in buscar_tramites(db, texto)["tramites"]}


with Session(seed.engine) as db:
    # 1. Catálogo
    assert claves("corregir calificación") == {"se_correccion_calif"}
    assert claves("contraseña") == {"se_mindbox_acceso", "cc_recuperar_pass"}
    assert claves("olvidé la contraseña de mi correo") == {"cc_recuperar_pass"}
    assert claves("Mindbox") == {
        "dep_mindbox", "se_mindbox_acceso", "rf_validar_pagos", "vin_calif_social"
    }
    correccion = buscar_tramites(db, "corregir calificación")["tramites"][0]
    assert [r["es_evidencia"] for r in correccion["requisitos"]] == [True, True]
    assert buscar_tramites(db, "becas")["tramites"][0]["requisitos_verificados"] is False
    assert len(listar_tramites_por_area(db, "dep")["tramites"]) == 8

    # 2. Estado del alumno e identidad
    ctx = ContextoSesion("25120001", "Carlos Mendoza Ruiz", "Ingenieria en Informatica")
    estado = ejecutar_herramienta(db, ctx, "consultar_mi_estado", {})
    assert estado["semestre"] == 3 and len(estado["pagos"]) == 1
    assert "nombre" not in estado and "numero_control" not in estado
    intruso = ejecutar_herramienta(
        db, ctx, "consultar_mi_estado", {"numero_control": "24120045"}
    )
    assert intruso["codigo"] == "argumentos_invalidos"

    # 3. Borradores
    args = {
        "tramite_clave": "se_correccion_calif",
        "motivo": "Mi calificación aparece incorrecta en el sistema.",
    }
    incompleto = ejecutar_herramienta(
        db, ContextoSesion("25120001"), "crear_borrador_folio", args
    )
    assert incompleto["faltan"] == ["nombre", "carrera"]

    primero = ejecutar_herramienta(db, ctx, "crear_borrador_folio", args)
    assert primero["ok"] and not primero["listo_para_enviar"]
    assert primero["destinatario"] == "se_iztapalapa3@tecnm.mx"
    assert "cuerpo" not in primero and "asunto" not in primero
    assert "Carlos" not in str(primero) and "25120001" not in str(primero)

    ctx.evidencias_confirmadas = frozenset({"se_correccion_calif"})
    segundo = ejecutar_herramienta(db, ctx, "crear_borrador_folio", args)
    assert segundo["listo_para_enviar"] and segundo["folio"] == primero["folio"]
    assert len(ctx.borradores) == 1 and "25120001" in ctx.borradores[0]["cuerpo"]
    assert db.scalar(select(func.count(Folio.id))) == 1

    aspirante = ejecutar_herramienta(
        db, ctx, "crear_borrador_folio",
        {"tramite_clave": "dda_fichas", "motivo": "Quiero información sobre las fichas."},
    )
    assert aspirante["codigo"] == "solo_orientacion"

    ana = ContextoSesion("24120045", "Ana Sofia Lopez Herrera", "Ingeniería en Informática")
    sin_correo = ejecutar_herramienta(
        db, ana, "crear_borrador_folio",
        {"tramite_clave": "se_constancias", "motivo": "Necesito una constancia de estudios."},
    )
    assert any("correo institucional" in a for a in sin_correo["advertencias"])

    print(ctx.borradores[0]["cuerpo"])
    print("\nTodas las pruebas pasaron.")
