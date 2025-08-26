import streamlit as st
import pandas as pd
import time

st.set_page_config(page_title="Gestión de Tiempo y Pomodoros", layout="wide")

# --------------------------
# Inicialización de session_state
# --------------------------
if "tasks" not in st.session_state:
    st.session_state["tasks"] = []  # lista de dicts
if "pomodoro" not in st.session_state:
    st.session_state["pomodoro"] = {
        "is_running": False,
        "remaining": 25 * 60,  # 25 minutos
        "last_tick": None,
        "mode": "work",  # work / short_break / long_break
        "cycles": 0,
        "active_task": None,
    }

# --------------------------
# Funciones auxiliares
# --------------------------
def add_task(name, priority, category, pomodoros):
    st.session_state["tasks"].append({
        "name": name,
        "priority": priority,
        "category": category,
        "pomodoros": pomodoros,
        "done": False,
        "done_pomodoros": 0
    })

def toggle_task(i):
    st.session_state["tasks"][i]["done"] = not st.session_state["tasks"][i]["done"]

def select_task(i):
    st.session_state["pomodoro"]["active_task"] = i

def reset_timer(mode="work"):
    if mode == "work":
        st.session_state["pomodoro"]["remaining"] = 25 * 60
    elif mode == "short_break":
        st.session_state["pomodoro"]["remaining"] = 5 * 60
    elif mode == "long_break":
        st.session_state["pomodoro"]["remaining"] = 15 * 60
    st.session_state["pomodoro"]["mode"] = mode
    st.session_state["pomodoro"]["last_tick"] = None
    st.session_state["pomodoro"]["is_running"] = False

def tick():
    p = st.session_state["pomodoro"]
    if not p["is_running"]:
        return
    now = time.time()
    if p["last_tick"] is None:
        p["last_tick"] = now
        return
    dec = int(now - p["last_tick"])
    if dec >= 1:
        p["remaining"] = max(0, p["remaining"] - dec)
        p["last_tick"] = now

def on_timer_complete():
    p = st.session_state["pomodoro"]
    if p["mode"] == "work":
        p["cycles"] += 1
        if p["active_task"] is not None:
            st.session_state["tasks"][p["active_task"]]["done_pomodoros"] += 1
        # cada 4 ciclos → descanso largo
        if p["cycles"] % 4 == 0:
            reset_timer("long_break")
        else:
            reset_timer("short_break")
    else:
        reset_timer("work")

# --------------------------
# Layout de la App
# --------------------------
left, right = st.columns(2)

# --- Columna Izquierda: Tareas ---
with left:
    st.header("📋 Lista de Tareas")
    with st.form("add_task_form", clear_on_submit=True):
        name = st.text_input("Descripción de la tarea")
        priority = st.selectbox("Prioridad", ["Baja", "Media", "Alta"])
        category = st.selectbox("Categoría", ["Bolsa Academy", "Turbo Bolsa", "Marketing", "YouTube", "Instagram", "Blog", "Web"])
        pomodoros = st.number_input("Nº de Pomodoros estimados", min_value=1, max_value=20, value=1)
        submitted = st.form_submit_button("➕ Añadir Tarea")
        if submitted and name.strip() != "":
            add_task(name, priority, category, pomodoros)

    for i, task in enumerate(st.session_state["tasks"]):
        cols = st.columns([0.1, 0.5, 0.2, 0.2])
        with cols[0]:
            st.checkbox("", value=task["done"], key=f"chk_{i}", on_change=toggle_task, args=(i,))
        with cols[1]:
            st.write(f"**{task['name']}** ({task['priority']}) - {task['category']}")
        with cols[2]:
            st.write(f"{task['done_pomodoros']}/{task['pomodoros']} 🍅")
        with cols[3]:
            if st.button("🎯 Focalizar", key=f"focus_{i}"):
                select_task(i)

# --- Columna Derecha: Pomodoro ---
with right:
    st.header("⏳ Temporizador Pomodoro")
    p = st.session_state["pomodoro"]

    tick()  # actualizar cada render
    mins, secs = divmod(p["remaining"], 60)
    st.subheader(f"{mins:02d}:{secs:02d} - {p['mode'].upper()}")

    col_c1, col_c2, col_c3 = st.columns(3)
    if col_c1.button("▶️ Start"):
        p["is_running"] = True
        p["last_tick"] = time.time()
    if col_c2.button("⏸ Pause"):
        p["is_running"] = False
    if col_c3.button("⏹ Reset"):
        reset_timer(p["mode"])

    if p["remaining"] <= 0:
        on_timer_complete()

    if p["active_task"] is not None:
        t = st.session_state["tasks"][p["active_task"]]
        st.info(f"Tarea activa: **{t['name']}** ({t['done_pomodoros']}/{t['pomodoros']} 🍅)")
    else:
        st.info("Selecciona una tarea para asociar al pomodoro.")

    # Refrescar cada segundo
    st.experimental_singleton.clear()  # limpiar cache (truco visual)
    st.empty()
    st.rerun()
