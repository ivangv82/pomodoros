# app.py — Gestor de Tareas + Pomodoros
# -------------------------------------------------
# Requisitos:
#   streamlit>=1.28.0
#   pandas>=1.5.0
# -------------------------------------------------
import time
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Gestión de Tiempo y Pomodoros", page_icon="⏳", layout="wide")

# --------------------------
# Estado inicial
# --------------------------
if "tasks" not in st.session_state:
    st.session_state.tasks = []  # [{name, priority, category, pomodoros, done, done_pomodoros}]
if "pomodoro" not in st.session_state:
    st.session_state.pomodoro = {
        "is_running": False,
        "remaining": 25 * 60,     # segundos
        "last_tick": None,        # timestamp último tick
        "mode": "work",           # work | short_break | long_break
        "cycles": 0,              # nº pomodoros completados
        "active_task": None       # index de tarea activa
    }

P = st.session_state.pomodoro

# --------------------------
# Helpers
# --------------------------
def add_task(name, priority, category, pomodoros):
    st.session_state.tasks.append({
        "name": name.strip(),
        "priority": priority,
        "category": category,
        "pomodoros": int(pomodoros),
        "done": False,
        "done_pomodoros": 0
    })

def toggle_task(i: int):
    st.session_state.tasks[i]["done"] = not st.session_state.tasks[i]["done"]

def select_task(i: int):
    P["active_task"] = i

def set_mode(mode: str):
    """Configura la duración por modo y resetea el reloj sin arrancarlo."""
    durations = {"work": 25*60, "short_break": 5*60, "long_break": 15*60}
    P["mode"] = mode
    P["remaining"] = durations[mode]
    P["last_tick"] = None
    P["is_running"] = False

def reset_timer():
    """Reset al modo actual sin cambiarlo."""
    set_mode(P["mode"])

def tick():
    """Descuenta segundos si está corriendo, calculado por diferencia de reloj."""
    if not P["is_running"]:
        return
    now = time.time()
    if P["last_tick"] is None:
        P["last_tick"] = now
        return
    dec = int(now - P["last_tick"])
    if dec >= 1:
        P["remaining"] = max(0, P["remaining"] - dec)
        P["last_tick"] = now

def on_timer_complete():
    """Acciones al terminar un bloque."""
    if P["mode"] == "work":
        P["cycles"] += 1
        if P["active_task"] is not None:
            t = st.session_state.tasks[P["active_task"]]
            t["done_pomodoros"] += 1
            if t["done_pomodoros"] >= t["pomodoros"]:
                t["done"] = True
        # Cada 4 pomodoros -> descanso largo
        if P["cycles"] % 4 == 0:
            set_mode("long_break")
        else:
            set_mode("short_break")
    else:
        # Al terminar descanso, volvemos a trabajo
        set_mode("work")

# --------------------------
# UI
# --------------------------
st.title("⏳ Gestor de Tareas + Pomodoros")

left, right = st.columns([1.2, 1])

# ---- Columna izquierda: Tareas ----
with left:
    st.header("📋 Tareas")
    with st.form("add_task_form", clear_on_submit=True):
        name = st.text_input("Descripción de la tarea")
        priority = st.selectbox("Prioridad", ["Baja", "Media", "Alta"], index=1)
        category = st.selectbox(
            "Categoría",
            ["Bolsa Academy", "Turbo Bolsa", "Marketing", "Youtube", "Instagram", "Blog", "Web"]
        )
        pomodoros = st.number_input("Nº de Pomodoros estimados", min_value=1, max_value=20, value=1, step=1)
        submitted = st.form_submit_button("➕ Añadir Tarea")
        if submitted:
            if name.strip():
                add_task(name, priority, category, pomodoros)
                st.success("Tarea añadida ✅")
            else:
                st.warning("Escribe una descripción.")

    if st.session_state.tasks:
        # Tabla simple de lectura
        df = pd.DataFrame(st.session_state.tasks)
        df_view = df.copy()
        df_view["estado"] = df_view["done"].map({True: "Hecha", False: "Pendiente"})
        df_view = df_view[["name", "priority", "category", "done_pomodoros", "pomodoros", "estado"]]
        df_view.rename(columns={
            "name": "Tarea", "priority": "Prioridad", "category": "Categoría",
            "done_pomodoros": "🍅 hechos", "pomodoros": "🍅 estimados"
        }, inplace=True)
        st.dataframe(df_view, use_container_width=True, hide_index=True)

        # Lista con acciones
        st.subheader("Acciones rápidas")
        for i, t in enumerate(st.session_state.tasks):
            c1, c2, c3, c4 = st.columns([0.06, 0.54, 0.2, 0.2])
            with c1:
                st.checkbox("", value=t["done"], key=f"chk_{i}", on_change=toggle_task, args=(i,))
            with c2:
                st.write(f"**{t['name']}** — {t['priority']} · {t['category']}")
            with c3:
                st.write(f"{t['done_pomodoros']}/{t['pomodoros']} 🍅")
            with c4:
                if st.button("🎯 Focalizar", key=f"focus_{i}"):
                    select_task(i)
    else:
        st.info("Aún no hay tareas. Añade la primera con el formulario de arriba.")

# ---- Columna derecha: Pomodoro ----
with right:
    st.header("⏱️ Pomodoro")

    # Botones de modo
    colm1, colm2, colm3 = st.columns(3)
    if colm1.button("Trabajo"):
        set_mode("work")
    if colm2.button("Descanso corto"):
        set_mode("short_break")
    if colm3.button("Descanso largo"):
        set_mode("long_break")

    # Lógica de tiempo
    tick()
    mins, secs = divmod(P["remaining"], 60)
    st.markdown(
        f"<div style='text-align:center;font-size:64px;font-weight:700;margin:10px 0;'>{mins:02d}:{secs:02d}</div>"
        f"<p style='text-align:center;margin-top:-8px;'>Modo: <b>{P['mode']}</b></p>",
        unsafe_allow_html=True
    )
    st.progress(1.0 - (P["remaining"] / (25*60 if P["mode"]=='work' else 5*60 if P['mode']=='short_break' else 15*60)))

    # Controles
    c1, c2, c3 = st.columns(3)
    if c1.button("▶️ Start"):
        P["is_running"] = True
        P["last_tick"] = time.time()
    if c2.bu
