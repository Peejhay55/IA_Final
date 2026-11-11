"""Pruebas de datos, herramientas, RAG y loop agéntico (sin red ni API key)."""
import pandas as pd

from aire import config as C
from aire.agent import LLMAgent, OfflineAgent, extract_citations
from aire.data import load_daily, load_stations
from aire.tools import call_tool, get_retriever
from fakes import ScriptedClient


def test_datos_procesados():
    d, s = load_daily(), load_stations()
    assert len(s) == 21
    assert d["horas"].min() >= C.MIN_HOURS_PER_DAY
    assert d["pm25"].between(0, 500).all()
    assert d["fecha"].min() == pd.Timestamp("2019-02-21")


def test_herramientas_y_errores_como_observacion():
    r = call_tool("get_pm25", {"estacion": "SAB-RAME", "fecha": "2019-03-16", "dias": 2})
    assert r["pm25_promedio_24h"] > 37 and r["supera_norma_diaria_37"] is True
    assert "error" in call_tool("get_pm25", {"estacion": "Marte"})
    assert "error" in call_tool("predict_tomorrow", {"estacion": "Bello", "fecha": "2022-01-01"})
    assert "error" in call_tool("herramienta_inexistente", {})
    assert "error" in call_tool("get_pm25", "{json malo")
    p = call_tool("predict_tomorrow", {"estacion": "ITA-CJUS", "fecha": "2019-12-01"})
    assert abs(sum(p["probabilidades"].values()) - 1) < 0.01


def test_en_vivo_cae_al_historico():
    r = call_tool("get_pm25", {"estacion": "Bello", "en_vivo": True, "fecha": "2019-05-01"})
    assert "en_vivo" in r or "aviso" in r  # con o sin red, nunca lanza excepción


def test_rag_recupera_documento_correcto():
    res = get_retriever().search("nivel máximo permisible diario de PM2.5", k=3)
    assert res[0]["cita"] == "[RES2254-NORMA]"


def test_loop_agente_con_llm_simulado():
    script = [[("get_pm25", {"estacion": "Atlantis"})],                     # error → observación
              [("get_pm25", {"estacion": "Sabaneta"}), ("search_docs", {"query": "naranja"})],
              "En Sabaneta hubo 48.9 µg/m³ [SIATA-DATOS]. Reduzca el ejercicio [SALUD]."]
    res = LLMAgent(client=ScriptedClient(script), model="x").run(
        "¿cómo está Sabaneta?", context={"fecha": "2019-03-15"})
    assert res.tools_used == ["get_pm25", "get_pm25", "search_docs"]
    assert not res.steps[0].ok and res.steps[1].ok
    assert res.steps[1].args["fecha"] == "2019-03-15"  # se inyecta la fecha del tablero
    assert res.citations == ["SIATA-DATOS", "SALUD"]


def test_tmax_fuerza_respuesta_final():
    client = ScriptedClient([[("get_pm25", {"estacion": "Bello"})]] * 10)
    res = LLMAgent(client=client, model="x", max_steps=3).run("bucle")
    assert len(res.steps) == 3 and res.notice
    assert client.calls[-1]["tool_choice"] == "none"


def test_falla_del_proveedor_usa_respaldo():
    res = LLMAgent(client=ScriptedClient([], fail_times=10), model="x").run(
        "¿Cuál es la norma diaria de PM2.5?")
    assert res.backend == "offline" and "falló" in res.notice
    assert "RES2254-NORMA" in res.citations


def test_router_respaldo():
    res = OfflineAgent().run("¿Qué calidad del aire habrá mañana en Sabaneta?",
                             context={"fecha": "2019-03-15"})
    assert "predict_tomorrow" in res.tools_used and "MODELO" in res.citations


def test_extraer_citas_ignora_codigos_desconocidos():
    assert extract_citations("dato [SIATA-DATOS] y [INVENTADO] y [POECA]") == ["SIATA-DATOS", "POECA"]
