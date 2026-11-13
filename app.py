"""Dashboard Streamlit – Agente de calidad del aire del Valle de Aburrá.

Ejecutar:  streamlit run app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).parent / "src"))

from aire import config as C  # noqa: E402
from aire.agent import LLMAgent, OfflineAgent  # noqa: E402
from aire.data import ica_category, ica_color, load_daily, load_stations  # noqa: E402
from aire.tools import get_forecaster, get_retriever, call_tool  # noqa: E402

st.set_page_config(page_title="Aire Valle de Aburrá – Agente IA", page_icon="🌫️", layout="wide")

SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # validado (dataviz)
INK, MUTED, GRID = "#2b2b2b", "#6b6b6b", "#e6e6e3"


# ---------------------------------------------------------------------------
# Datos y recursos en caché
# ---------------------------------------------------------------------------
@st.cache_data
def daily() -> pd.DataFrame:
    return load_daily()


@st.cache_data
def stations() -> pd.DataFrame:
    return load_stations()


@st.cache_resource(show_spinner="Cargando modelos (HMM + clasificador) e índice RAG…")
def resources():
    return get_forecaster(), get_retriever()


@st.cache_data
def metrics() -> dict:
    p = C.METRICS_JSON
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


fc, retriever = resources()
D, S = daily(), stations()
lo, hi = D["fecha"].min().date(), D["fecha"].max().date()
label = {r.codigo: f"{r.nombre_corto} · {r.nombre}" for r in S.itertuples()}

# ---------------------------------------------------------------------------
# Barra lateral: parámetros
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Parámetros")
    codes = S.sort_values("nombre")["codigo"].tolist()
    main = st.selectbox("Estación", codes, index=codes.index(28) if 28 in codes else 0,
                        format_func=lambda c: label[c])
    default_fecha = pd.Timestamp("2019-03-15").date()
    if not (lo <= default_fecha <= hi):  # datos distintos a los del proyecto: no fallar
        default_fecha = hi
    fecha = st.date_input("Fecha de referencia («hoy»)", value=default_fecha,
                          min_value=lo, max_value=hi)
    comparar = st.multiselect("Comparar con (máx. 3)", [c for c in codes if c != main],
                              default=[25] if 25 in codes and main != 25 else [],
                              max_selections=3, format_func=lambda c: label[c])
    ventana = st.slider("Días en la serie de tiempo", 14, 365, 90, step=7)
    st.divider()
    st.subheader("Agente")
    hay_llm = bool(C.LLM_API_KEY)
    modo = st.radio("Motor del chat", ["LLM + herramientas", "Respaldo sin LLM"],
                    index=0 if hay_llm else 1, disabled=not hay_llm,
                    help="Sin LLM_API_KEY en .env solo está disponible el router determinista.")
    if hay_llm:
        st.caption(f"Modelo: `{C.LLM_MODEL}` · Tmáx = {C.AGENT_MAX_STEPS} pasos")
    else:
        st.warning("No hay LLM_API_KEY configurada: el chat usa el modo de respaldo.")
    st.caption(f"RAG: {retriever.backend} · {len(retriever.chunks)} fragmentos")
    st.divider()
    st.caption(f"Datos: SIATA – AMVA, PM2.5 horario {lo} a {hi}. "
               "Herramienta académica: no es un pronóstico oficial ni consejo médico.")

fecha_ts = pd.Timestamp(fecha)
st_row = S[S["codigo"] == main].iloc[0]

# ---------------------------------------------------------------------------
# Encabezado e indicadores
# ---------------------------------------------------------------------------
st.title("🌫️ Agente de calidad del aire del Valle de Aburrá")
st.caption("PM2.5 de SIATA · HMM + regresión logística propios · agente LLM con RAG "
           "sobre Res. 2254/2017, POECA y OMS — SI3003 Inteligencia Artificial, EAFIT")

day = D[(D["codigo"] == main) & (D["fecha"] == fecha_ts)]
pm_hoy = float(day["pm25"].iloc[0]) if len(day) else None
try:
    pred = fc.predict(main, fecha_ts)
except ValueError as exc:
    pred = None
    pred_err = str(exc)
reg = call_tool("estado_regional", {"fecha": str(fecha)})

k1, k2, k3, k4 = st.columns(4)
k1.metric(f"PM2.5 {fecha} · {st_row.nombre_corto}",
          f"{pm_hoy:.1f} µg/m³" if pm_hoy is not None else "sin dato",
          help="Promedio de 24 h con al menos 18 horas válidas.")
k1.markdown(f"<span style='color:{MUTED}'>ICA: <b style='color:{INK}'>"
            f"{ica_category(pm_hoy) if pm_hoy is not None else '—'}</b></span>",
            unsafe_allow_html=True)
if pred:
    k2.metric("Estado latente (HMM)", pred["estado_hmm_actual"],
              help="Régimen estimado por filtrado forward del HMM propio.")
    k3.metric(f"Pronóstico {pred['fecha_pronostico']}", pred["clase_predicha"])
    k3.caption(f"P(Dañina) = {pred['probabilidades']['Dañina']:.0%}")
else:
    k2.metric("Estado latente (HMM)", "—")
    k3.metric("Pronóstico", "—")
if "error" not in reg:
    k4.metric("Estaciones poblacionales sobre la norma",
              f"{reg['porcentaje_poblacionales_sobre_norma']:.0f} %")
    k4.caption(f"Nivel {reg['nivel_indicativo_res2254_art12'].lower()} · criterio 50 % (Res. 2254, art. 12)")

tab1, tab2, tab3 = st.tabs(["📍 Mapa y series", "🔮 Pronóstico y modelo", "💬 Chat con el agente"])

# ---------------------------------------------------------------------------
# Pestaña 1: mapa + serie de tiempo
# ---------------------------------------------------------------------------
with tab1:
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.subheader(f"PM2.5 por estación · {fecha}")
        dm = D[D["fecha"] == fecha_ts][["codigo", "pm25"]]
        mp = S.merge(dm, on="codigo", how="left")
        mp["categoria"] = mp["pm25"].map(lambda v: ica_category(v) if pd.notna(v) else "Sin dato")
        mp["pm_txt"] = mp["pm25"].map(lambda v: f"{v:.1f} µg/m³" if pd.notna(v) else "sin dato")
        mp["sel"] = np.where(mp["codigo"] == main, 18, 12)
        orden = [b[2] for b in C.ICA_BREAKS] + ["Sin dato"]
        cmap = {b[2]: b[3] for b in C.ICA_BREAKS} | {"Sin dato": "#bdbdbd"}
        fig = px.scatter_map(mp, lat="lat", lon="lon", color="categoria", size="sel",
                             size_max=16, color_discrete_map=cmap,
                             category_orders={"categoria": orden},
                             hover_name="nombre", zoom=10.2, height=520,
                             hover_data={"pm_txt": True, "municipio": True, "tipo": True,
                                         "lat": False, "lon": False, "sel": False,
                                         "categoria": True},
                             labels={"pm_txt": "PM2.5", "categoria": "Categoría ICA"},
                             map_style="open-street-map", center={"lat": 6.25, "lon": -75.58})
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0),
                          legend=dict(orientation="h", y=-0.02, title=None, font_size=11))
        st.plotly_chart(fig, width="stretch")
        st.caption("Colores oficiales del ICA (Res. 2254/2017). El punto grande es la "
                   "estación seleccionada. Las estaciones de tráfico tienen área de influencia pequeña.")
    with c2:
        st.subheader("Serie de tiempo del PM2.5 diario")
        sel = [main] + comparar
        ini = fecha_ts - pd.Timedelta(days=ventana)
        ts = D[D["codigo"].isin(sel) & (D["fecha"] > ini) & (D["fecha"] <= fecha_ts)]
        fig = go.Figure()
        for lo_, hi_, name, col in C.ICA_BREAKS[:4]:
            fig.add_hrect(y0=lo_, y1=hi_, fillcolor=col, opacity=0.07, line_width=0, layer="below")
        fig.add_hline(y=C.NORMA_DIARIA, line_dash="dash", line_color=MUTED, line_width=1,
                      annotation_text="Norma diaria 37 µg/m³", annotation_position="top left",
                      annotation_font_color=MUTED)
        for i, c in enumerate(sel):
            s = ts[ts["codigo"] == c].set_index("fecha")["pm25"].asfreq("D")
            fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines",
                                     name=S.set_index("codigo").loc[c, "nombre_corto"],
                                     line=dict(width=2, color=SERIES_COLORS[i]),
                                     hovertemplate="%{y:.1f} µg/m³"))
        ymax = max(60.0, float(ts["pm25"].max() if len(ts) else 60) * 1.1)
        fig.update_layout(height=520, hovermode="x unified", margin=dict(l=10, r=10, t=10, b=10),
                          yaxis=dict(title="PM2.5 (µg/m³)", range=[0, ymax], gridcolor=GRID),
                          xaxis=dict(gridcolor=GRID), plot_bgcolor="#fcfcfb",
                          legend=dict(orientation="h", y=1.06, x=0))
        st.plotly_chart(fig, width="stretch")
        st.caption("Bandas de fondo: categorías ICA (verde Buena, amarillo Aceptable, naranja "
                   "Dañina para grupos sensibles, rojo Dañina).")
        with st.expander("Ver datos en tabla"):
            tbl = ts.pivot(index="fecha", columns="codigo", values="pm25")
            tbl.columns = [S.set_index("codigo").loc[c, "nombre_corto"] for c in tbl.columns]
            st.dataframe(tbl.sort_index(ascending=False).round(1), width="stretch")

# ---------------------------------------------------------------------------
# Pestaña 2: pronóstico, estados HMM y métricas
# ---------------------------------------------------------------------------
with tab2:
    if pred is None:
        st.info(pred_err)
    else:
        c1, c2 = st.columns([1, 1.4])
        with c1:
            st.subheader(f"Pronóstico {pred['fecha_pronostico']}")
            rows = []
            for mname, key in [("Regresión logística + HMM", "probabilidades"),
                               ("Naive Bayes + HMM", "probabilidades_naive_bayes"),
                               ("HMM solo", "probabilidades_hmm")]:
                for cl, p in pred[key].items():
                    rows.append({"Modelo": mname, "Clase": cl, "p": p})
            pdf = pd.DataFrame(rows)
            fig = px.bar(pdf, y="Modelo", x="p", color="Clase", orientation="h",
                         color_discrete_map=C.CLASS_COLORS, text=pdf["p"].map(lambda v: f"{v:.0%}" if v >= .08 else ""),
                         category_orders={"Clase": C.CLASSES, "Modelo": [
                             "Regresión logística + HMM", "Naive Bayes + HMM", "HMM solo"]},
                         height=300)
            fig.update_traces(marker_line_color="#fcfcfb", marker_line_width=2,
                              textfont_color=INK, hovertemplate="%{y}<br>%{fullData.name}: %{x:.1%}<extra></extra>")
            fig.update_layout(barmode="stack", xaxis=dict(tickformat=".0%", range=[0, 1], title=None),
                              yaxis_title=None, margin=dict(l=10, r=10, t=10, b=10),
                              legend=dict(orientation="h", y=1.15, title=None), plot_bgcolor="#fcfcfb")
            st.plotly_chart(fig, width="stretch")
            real = pred["valor_real_dia_siguiente"]
            st.markdown(
                f"**Modelo principal:** {pred['clase_predicha']} · PM2.5 hoy "
                f"{pred['pm25_fecha_base']} µg/m³ · estado HMM **{pred['estado_hmm_actual']}**  \n"
                + (f"Valor real observado al día siguiente: **{real} µg/m³** "
                   f"({ica_category(real)})." if real is not None else "Sin dato real del día siguiente."))
            if not pred["en_periodo_de_prueba"]:
                st.caption("⚠️ Fecha dentro del periodo de entrenamiento (≤ 2019-10-31): el "
                           "modelo ya vio datos de este periodo.")
        with c2:
            st.subheader("Estados latentes del HMM (filtrado) · " + st_row.nombre_corto)
            hs = fc.states(main)
            hs = hs[(hs["fecha"] > fecha_ts - pd.Timedelta(days=ventana)) & (hs["fecha"] <= fecha_ts)]
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.6, 0.4],
                                vertical_spacing=0.06)
            fig.add_trace(go.Scatter(x=hs["fecha"], y=hs["pm25_t"], mode="lines", name="PM2.5",
                                     line=dict(color=SERIES_COLORS[0], width=2),
                                     hovertemplate="%{y:.1f} µg/m³"), 1, 1)
            fig.add_hline(y=37, line_dash="dash", line_color=MUTED, line_width=1, row=1, col=1)
            st_cols = ["#9db8d9", "#eda100", "#c0392b"]
            for i, (nm, col) in enumerate(zip(C.HMM_STATES, ["p_normal", "p_alerta", "p_critico"])):
                fig.add_trace(go.Scatter(x=hs["fecha"], y=hs[col], name=f"P({nm})", stackgroup="s",
                                         mode="lines", line=dict(width=0.5, color=st_cols[i]),
                                         hovertemplate="%{y:.0%}"), 2, 1)
            fig.update_layout(height=430, hovermode="x unified", margin=dict(l=10, r=10, t=10, b=10),
                              plot_bgcolor="#fcfcfb", legend=dict(orientation="h", y=1.1))
            fig.update_yaxes(title_text="µg/m³", row=1, col=1, gridcolor=GRID)
            fig.update_yaxes(title_text="P(estado)", tickformat=".0%", range=[0, 1], row=2, col=1)
            st.plotly_chart(fig, width="stretch")
            m = metrics().get("hmm", {})
            if m:
                st.caption(f"Medias por estado: {dict(zip(m['estados'], m['media_pm25_por_estado']))} µg/m³ · "
                           f"duración esperada (días): {dict(zip(m['estados'], m['duracion_esperada_dias']))}")

    st.subheader("Evaluación en el periodo de prueba (nov-2019 a feb-2020)")
    met = metrics().get("clasificacion_dia_siguiente", {})
    if met:
        tab = pd.DataFrame([{
            "Modelo": k, "Exactitud": v["accuracy"], "F1-macro": v["macro_f1"],
            "Exactitud balanceada": v["balanced_accuracy"],
            "Recall excedencia (>37)": v["excedencia_norma"]["recall"],
            "F1 excedencia": v["excedencia_norma"]["f1"],
            "Log-loss": v.get("log_loss", np.nan)} for k, v in met.items()])
        st.dataframe(tab.style.format(precision=3, na_rep="—")
                     .highlight_max(subset=["Exactitud balanceada", "Recall excedencia (>37)"],
                                    color="#dbeafe")
                     .highlight_min(subset=["Log-loss"], color="#dbeafe"),
                     width="stretch", hide_index=True)
        st.caption("Implementaciones propias (NumPy). Hiperparámetros elegidos con validación "
                   "temporal dentro del entrenamiento. Detalle en reports/metricas_parte1.json.")
    else:
        st.info("Ejecute `python scripts/train.py` para generar las métricas.")

# ---------------------------------------------------------------------------
# Pestaña 3: chat con el agente
# ---------------------------------------------------------------------------
with tab3:
    st.subheader("Converse con el agente")
    st.caption(f"Contexto enviado al agente: estación **{st_row.nombre_corto}**, fecha **{fecha}**. "
               "Las respuestas citan fuentes entre corchetes.")
    if "chat" not in st.session_state:
        st.session_state.chat = []
    ejemplos = ["¿Cómo está el aire hoy y puedo hacer ejercicio afuera?",
                "¿Qué calidad del aire se espera mañana?",
                "¿Hay un episodio crítico en el valle?",
                "¿Qué medidas aplica el POECA en nivel de alerta?"]
    cols = st.columns(len(ejemplos))
    pending = None
    for c, ej in zip(cols, ejemplos):
        if c.button(ej, width="stretch"):
            pending = ej
    if st.button("🗑️ Limpiar conversación"):
        st.session_state.chat = []

    for m in st.session_state.chat:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("fuentes"):
                with st.expander("Fuentes"):
                    st.markdown(m["fuentes"])
            if m.get("traza"):
                with st.expander(f"Traza del agente ({len(m['traza'])} llamadas a herramientas)"):
                    for i, s in enumerate(m["traza"], 1):
                        st.markdown(f"**{i}. `{s['tool']}`** `{json.dumps(s['args'], ensure_ascii=False)}`"
                                    + (" ⚠️ error" if "error" in s["result"] else ""))
                        st.json(s["result"], expanded=False)

    q = st.chat_input("Escriba su pregunta sobre la calidad del aire…") or pending
    if q:
        hist = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat]
        st.session_state.chat.append({"role": "user", "content": q})
        agent = LLMAgent() if (modo == "LLM + herramientas" and hay_llm) else OfflineAgent()
        with st.spinner("El agente está consultando herramientas…"):
            try:
                res = agent.run(q, history=hist, context={"estacion": st_row.nombre_corto,
                                                          "fecha": str(fecha)})
                content = res.answer + (f"\n\n_ℹ️ {res.notice}_" if res.notice else "")
                if res.backend == "offline":
                    content += "\n\n_Respuesta del modo de respaldo (sin LLM)._"
                st.session_state.chat.append({
                    "role": "assistant", "content": content, "fuentes": res.sources_markdown(),
                    "traza": [{"tool": s.tool, "args": s.args, "result": s.result} for s in res.steps]})
            except Exception as exc:  # noqa: BLE001 – la demo nunca debe caerse
                st.session_state.chat.append({"role": "assistant",
                                              "content": f"Ocurrió un error inesperado: {exc}"})
        st.rerun()
