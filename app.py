import time
from datetime import datetime, timedelta, date
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, Date, DateTime
)
from sqlalchemy.orm import declarative_base, sessionmaker

# ─────────────────────────────────────────────────────────────
# Configuración básica
# ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Productividad: Tareas + Pomodoro", page_icon="⏱️", layout="wide")
DB_URL = "sqlite:///tasks.db"  # fichero local

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ─────────────────────────────────────────────────────────────
# Modelo de datos
# ─────────────────────────────────────────────────────────────
class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    priority = Column(String, default="Media")  # Baja/Media/Alta
    category = Column(String, default="General")
    pomodoros_est = Column(Integer, default=1)
    pomodoros_done = Column(Integer, default=0)
    is_done = Column(Boolean, default=False)
    is_today = Column(Boolean, default=False)  # marcar para la vista del día
    due_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


# ─────────────────────────────────────────────────────────────
# Utilidades DB
# ─────────────────────────────────────────────────────────────
CATEGORIES = [
    "Bolsa Academy", "Turbo Bolsa", "Marketing", "Youtube",
    "Instagram", "Blog", "Web"
]
PRIORITIES = ["Baja", "Media", "Alta"]


def get_session():
    return SessionLocal()


def add_task(title, priority, category, pom_est, due_date, is_today):
    with get_session() as db:
        t = Task(
            title=title.strip(),
            priority=priority,
            category=category,
            pomodoros_est=max(int(pom_est), 0),
            due_date=due_date,
            is_today=is_today,
        )
        db.add(t)
        db.commit()


def update_task(task: Task, **kwargs):
    with get_session() as db:
        db.merge(task)  # asegura instancia gestionada
        for k, v in kwargs.items():
            setattr(task, k, v)
        db.commit()


def delete_task(task_id: int):
    with get_session() as db:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            db.delete(task)
            db.commit()


def list_tasks(filters: Optional[dict] = None) -> list[Task]:
    with get_session() as db:
        q = db.query(Task)
        if filters:
            if "only_today" in filters and filters["only_today"]:
                q = q.filter(Task.is_today.is_(True), Task.is_done.is_(False))
            if "category" in filters and filters["category"] != "Todas":
                q = q.filter(Task.category == filters["category"])
            if "priority" in filters and filters["priority"] != "Todas":
                q = q.filter(Task.priority == filters["priority"])
            if "status" in filters:
                if filters["status"] == "Pendientes":
                    q = q.filter(Task.is_done.is_(False))
                elif filters["status"] == "Hechas":
                    q = q.filter(Task.is_done.is_(True))
        return q.order_by(Task.is_done.asc(), Task.priority.desc(), Task.created_at.asc()).all()


def tasks_dataframe(tasks: list[Task]) -> pd.DataFrame:
    rows = []
    for t in tasks:
        rows.append({
            "ID": t.id,
            "Tarea": t.title,
            "Prioridad": t.priority,
            "Categoría": t.category,
            "⏱️ Pom. hechos/estimados": f"{t.pomodoros_done}/{t.pomodoros_est}",
            "Para hoy": "Sí" if t.is_today else "No",
            "Fecha límite": t.due_date.strftime("%Y-%m-%d") if t.due_date else "",
            "Estado": "Hecha" if t.is_done else "Pendiente",
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────
# Estado de la app (Pomodoro)
# ─────────────────────────────────────────────────────────────
def init_state():
    ss = st.session_state
    ss.setdefault("timer_mode", "focus")  # focus / short / long
    ss.setdefault("focus_minutes", 25)
    ss.setdefault("short_minutes", 5)
    ss.setdefault("long_minutes", 15)
    ss.setdefault("is_running", False)
    ss.setdefault("end_time", None)
    ss.setdefault("selected_task_id", None)
    ss.setdefault("completed_pomodoros_counter", 0)  # para sesión
    ss.setdefault("last_tick", time.time())


init_state()


def minutes_for_mode(mode: str) -> int:
    if mode == "focus":
        return int(st.session_state.focus_minutes)
    if mode == "short":
        return int(st.session_state.short_minutes)
    return int(st.session_state.long_minutes)


def start_timer():
    mins = minutes_for_mode(st.session_state.timer_mode)
    st.session_state.end_time = datetime.utcnow() + timedelta(minutes=mins)
    st.session_state.is_running = True


def stop_timer():
    st.session_state.is_running = False
    st.session_state.end_time = None


def reset_timer():
    stop_timer()


def remaining_seconds() -> int:
    if not st.session_state.is_running or not st.session_state.end_time:
        return minutes_for_mode(st.session_state.timer_mode) * 60
    delta = st.session_state.end_time - datetime.utcnow()
    return max(int(delta.total_seconds()), 0)


def fmt_time(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"


# ─────────────────────────────────────────────────────────────
# UI: Cabecera
# ─────────────────────────────────────────────────────────────
st.markdown(
    "<h2 style='margin-bottom:0'>⏱️ Productividad: Tareas + Pomodoro</h2>"
    "<p style='margin-top:2px;color:#999'>Gestor simple con prioridades, categorías y temporizador Pomodoro.</p>",
    unsafe_allow_html=True
)

tabs = st.tabs(["✅ Tareas", "🍅 Pomodoro"])


# ─────────────────────────────────────────────────────────────
# Pestaña 1: TAREAS
# ─────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("Añadir tarea")
    c1, c2, c3, c4, c5 = st.columns([3, 1.2, 1.6, 1.2, 1.2])

    with c1:
        title = st.text_input("Título", placeholder="Ej: Preparar mentoría de TurboBolsa")
    with c2:
        priority = st.selectbox("Prioridad", PRIORITIES, index=1)
    with c3:
        category = st.selectbox("Categoría", ["General"] + CATEGORIES)
    with c4:
        pom_est = st.number_input("Pomodoros (estimación)", min_value=0, max_value=20, value=1)
    with c5:
        due = st.date_input("Fecha límite (opcional)", value=None)

    col_t1, col_t2 = st.columns([1, 3])
    with col_t1:
        is_today = st.checkbox("Añadir a Hoy", value=True)
    with col_t2:
        if st.button("➕ Añadir tarea", type="primary", use_container_width=True, disabled=not title.strip()):
            add_task(title, priority, category, pom_est, due if due else None, is_today)
            st.success("Tarea creada.")
            st.rerun()

    st.divider()
    st.subheader("Listado y filtros")

    fc1, fc2, fc3, fc4 = st.columns([1.4, 1.4, 1.2, 1.2])
    with fc1:
        f_category = st.selectbox("Filtrar por categoría", ["Todas"] + CATEGORIES)
    with fc2:
        f_priority = st.selectbox("Filtrar por prioridad", ["Todas"] + PRIORITIES)
    with fc3:
        f_status = st.selectbox("Estado", ["Pendientes", "Hechas", "Todas"])
    with fc4:
        only_today = st.checkbox("Solo 'Hoy'", value=False)

    filters = {
        "category": f_category,
        "priority": f_priority,
        "status": f_status,
        "only_today": only_today
    }
    tasks = list_tasks(filters)

    df = tasks_dataframe(tasks)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

    st.caption("Consejo: marca tareas para Hoy y así aparecerán directas en la pestaña Pomodoro.")

    st.subheader("Acciones rápidas")
    if tasks:
        for t in tasks:
            with st.expander(f"[{t.id}] {t.title}", expanded=False):
                cA, cB, cC, cD, cE, cF = st.columns([3, 1, 1, 1, 1, 1.2])
                with cA:
                    new_title = st.text_input("Título", value=t.title, key=f"title_{t.id}")
                with cB:
                    new_priority = st.selectbox("Prioridad", PRIORITIES, index=PRIORITIES.index(t.priority), key=f"prio_{t.id}")
                with cC:
                    new_category = st.selectbox("Categoría", ["General"] + CATEGORIES,
                                                index=(["General"] + CATEGORIES).index(t.category),
                                                key=f"cat_{t.id}")
                with cD:
                    new_est = st.number_input("Pom. estimados", min_value=0, max_value=20, value=int(t.pomodoros_est), key=f"est_{t.id}")
                with cE:
                    new_today = st.checkbox("Para hoy", value=bool(t.is_today), key=f"today_{t.id}")
                with cF:
                    new_due = st.date_input("Fecha límite", value=t.due_date, key=f"due_{t.id}")

                c1x, c2x, c3x, c4x = st.columns([1, 1, 1, 1])
                with c1x:
                    if st.button("💾 Guardar", key=f"save_{t.id}"):
                        t.title = new_title.strip()
                        t.priority = new_priority
                        t.category = new_category
                        t.pomodoros_est = int(new_est)
                        t.is_today = bool(new_today)
                        t.due_date = new_due
                        update_task(t)
                        st.success("Guardado.")
                        st.rerun()
                with c2x:
                    if st.button(("✅ Marcar hecha" if not t.is_done else "↩️ Marcar pendiente"), key=f"done_{t.id}"):
                        t.is_done = not t.is_done
                        update_task(t)
                        st.rerun()
                with c3x:
                    if st.button("➕ +1 Pomodoro", key=f"plus_{t.id}"):
                        t.pomodoros_done = int(t.pomodoros_done) + 1
                        update_task(t)
                        st.rerun()
                with c4x:
                    if st.button("🗑️ Borrar", key=f"del_{t.id}"):
                        delete_task(t.id)
                        st.rerun()
    else:
        st.info("No hay tareas con esos filtros.")

    st.download_button(
        "⬇️ Exportar tareas a CSV",
        tasks_dataframe(list_tasks({"status": "Todas"})).to_csv(index=False).encode("utf-8"),
        "tareas.csv",
        "text/csv",
        use_container_width=True
    )


# ─────────────────────────────────────────────────────────────
# Pestaña 2: POMODORO
# ─────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("Configuración (duraciones)")
    sc1, sc2, sc3, sc4 = st.columns([1, 1, 1, 2])
    with sc1:
        st.number_input("Foco (min)", min_value=1, max_value=90, key="focus_minutes")
    with sc2:
        st.number_input("Descanso corto (min)", min_value=1, max_value=30, key="short_minutes")
    with sc3:
        st.number_input("Descanso largo (min)", min_value=1, max_value=60, key="long_minutes")
    with sc4:
        st.selectbox("Modo", options=[("Pomodoro (Foco)", "focus"),
                                      ("Short Break", "short"),
                                      ("Long Break", "long")],
                     index={"focus":0, "short":1, "long":2}[st.session_state.timer_mode],
                     key="mode_selector",
                     format_func=lambda x: x[0])
        # sincroniza el modo con el selectbox
        st.session_state.timer_mode = st.session_state.mode_selector[1]

    st.divider()
    left, right = st.columns([2, 1])

    with left:
        # Selector de tarea del día
        today_tasks = list_tasks({"only_today": True, "status": "Pendientes"})
        options = [(t.id, f"[{t.priority}] {t.title}  ({t.pomodoros_done}/{t.pomodoros_est})") for t in today_tasks]
        st.selectbox(
            "Tarea del ciclo actual",
            options=[(None, "— Sin tarea asignada —")] + options,
            index=0 if st.session_state.selected_task_id is None else
                  1 + next((i for i, (tid, _) in enumerate(options) if tid == st.session_state.selected_task_id), 0),
            key="task_selector",
            format_func=lambda x: x[1]
        )
        st.session_state.selected_task_id = st.session_state.task_selector[0]

        # Timer
        st.markdown("### ⏲️ Temporizador")
        secs = remaining_seconds()
        st.markdown(
            f"<div style='font-size:72px;font-weight:700;text-align:center'>{fmt_time(secs)}</div>",
            unsafe_allow_html=True
        )
        progress = 1 - secs / (minutes_for_mode(st.session_state.timer_mode) * 60)
        st.progress(progress)

        cbt1, cbt2, cbt3 = st.columns(3)
        with cbt1:
            if st.button("▶️ Start", use_container_width=True):
                start_timer()
        with cbt2:
            if st.button("⏸️ Stop", use_container_width=True):
                stop_timer()
        with cbt3:
            if st.button("🔁 Reset", use_container_width=True):
                reset_timer()

        # Auto-refresh cada segundo si está corriendo
        if st.session_state.is_running:
            st.experimental_rerun() if remaining_seconds() == 0 else st.autorefresh(interval=1000, key="tick")

        # Al terminar un ciclo:
        if st.session_state.is_running and remaining_seconds() == 0:
            stop_timer()
            # sumar pomodoro a la tarea seleccionada si era foco
            if st.session_state.timer_mode == "focus" and st.session_state.selected_task_id:
                with get_session() as db:
                    t = db.query(Task).filter(Task.id == st.session_state.selected_task_id).first()
                    if t:
                        t.pomodoros_done = int(t.pomodoros_done) + 1
                        db.commit()
            st.success("¡Tiempo completado!")
            st.balloons()

    with right
