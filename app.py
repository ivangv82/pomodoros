# app.py
# =========================================
# Gestor de Tareas + Temporizador Pomodoro
# Autor: Formación en Bolsa (Iván)
# Requisitos mínimos:
#   streamlit>=1.25.0
#   pandas>=1.5.0
# =========================================

import time
import math
import uuid
import pandas as pd
import streamlit as st

# -----------------------------
# Configuración general página
# -----------------------------
st.set_page_config(
    page_title="Gestor de tiempo | Formación en Bolsa",
    page_icon="⏳",
    layout="wide"
)

# -----------------------------
# Helpers de sesión (estado)
# -----------------------------
def init_state():
    # Lista de tareas
    if "tasks" not in st.session_state:
        st.session_state.tasks = []  # cada tarea: dict (id, titulo, prioridad, categoria, pomos_est, pomos_done, hoy, done)

    # Filtros
    if "filters" not in st.session_state:
        st.session_state.filters = {"categoria": "Todas", "prioridad": "Todas", "solo_hoy": False, "solo_pendientes": False}

    # Pomodoro
    if "pomodoro" not in st.session_state:
        st.session_state.pomodoro = {
            "mode": "Pomodoro",          # Pomodoro | Descanso corto | Descanso largo
            "durations": {               # minutos por modo
                "Pomodoro": 25,
                "Descanso corto": 5,
                "Descanso largo": 15
            },
            "long_break_every": 4,       # cada 4 pomodoros → descanso largo
            "cycles_done": 0,            # pomodoros terminados en el día
            "is_running": False,
            "remaining": 25 * 60,        # segundos
            "last_tick": None,
            "active_task_id": None       # tarea seleccionada para sumar pomodoros
        }

init_state()

CATEGORIAS = ["Bolsa Academy", "Turbo Bolsa", "Marketing", "Youtube", "Instagram", "Blog", "Web"]
PRIORIDADES = ["Alta", "Media", "Baja"]

# -----------------------------
# Barra superior — título
# -----------------------------
st.title("⏳ Gestor de Tareas + Pomodoros")
st.caption("Planifica tu día, prioriza tareas y trabaja en ciclos de foco con descansos. Estilo Formación en Bolsa.")

# =============================
# COLUMNA IZQ: TAREAS
# COLUMNA DCHA: POMODORO
# =============================
left, right = st.columns([1.2, 1])

# ----------------------------------------
# IZQUIERDA — Gestión de tareas
# ----------------------------------------
with left:
    st.subheader("📋 Tareas")

    with st.expander("➕ Añadir nueva tarea", expanded=True):
        with st.form("form_add_task", clear_on_submit=True):
            col_a, col_b = st.columns([2, 1])
            titulo = col_a.text_input("Título de la tarea", placeholder="Ej. Preparar mentoría")
            prioridad = col_b.selectbox("Prioridad", PRIORIDADES, index=1)
            col_c, col_d, col_e = st.columns([1.2, 1, 1])
            categoria = col_c.selectbox("Categoría", CATEGORIAS, index=0)
            pomos_est = col_d.number_input("Pomodoros estimados", min_value=1, max_value=20, value=1, step=1)
            para_hoy = col_e.checkbox("Para hoy", value=True)
            submitted = st.form_submit_button("Añadir tarea")

        if submitted:
            if titulo.strip():
                st.session_state.tasks.append({
                    "id": str(uuid.uuid4()),
                    "titulo": titulo.strip(),
                    "prioridad": prioridad,
                    "categoria": categoria,
                    "pomos_est": int(pomos_est),
                    "pomos_done": 0,
                    "hoy": bool(para_hoy),
                    "done": False,
                })
                st.success("Tarea añadida ✅")
            else:
                st.warning("Escribe un título para la tarea.")

    # ---- Filtros ----
    col_f1, col_f2, col_f3, col_f4 = st.columns([1, 1, 1, 1])
    st.session_state.filters["categoria"] = col_f1.selectbox("Filtrar por categoría", ["Todas"] + CATEGORIAS, index=0)
    st.session_state.filters["prioridad"] = col_f2.selectbox("Filtrar por prioridad", ["Todas"] + PRIORIDADES, index=0)
    st.session_state.filters["solo_hoy"] = col_f3.checkbox("Solo hoy")
    st.session_state.filters["solo_pendientes"] = col_f4.checkbox("Solo pendientes")

    # ---- Preparar DataFrame para mostrar/editar ----
    def apply_filters(rows):
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        mask = pd.Series([True] * len(df))
        f = st.session_state.filters
        if f["categoria"] != "Todas":
            mask &= (df["categoria"] == f["categoria"])
        if f["prioridad"] != "Todas":
            mask &= (df["prioridad"] == f["prioridad"])
        if f["solo_hoy"]:
            mask &= (df["hoy"] == True)
        if f["solo_pendientes"]:
            mask &= (df["done"] == False)
        return df[mask]

    df_view = apply_filters(st.session_state.tasks)

    if df_view.empty:
        st.info("No hay tareas para mostrar con los filtros actuales.")
    else:
        # Orden visual: primero hoy, luego prioridad Alta>Media>Baja, luego no hechas
        prioridad_order = {"Alta": 0, "Media": 1, "Baja": 2}
        df_view = df_view.sort_values(
            by=["hoy", "prioridad", "done", "pomos_done"],
            ascending=[False, True, True, True],
            key=lambda s: s.map(prioridad_order) if s.name == "prioridad" else s
        )

        # Editor en línea
        edited = st.data_editor(
            df_view[["titulo", "prioridad", "categoria", "pomos_est", "pomos_done", "hoy", "done"]],
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "titulo": st.column_config.TextColumn("Título", width="medium"),
                "prioridad": st.column_config.SelectboxColumn("Prioridad", options=PRIORIDADES),
                "categoria": st.column_config.SelectboxColumn("Categoría", options=CATEGORIAS),
                "pomos_est": st.column_config.NumberColumn("Pomodoros (est.)", min_value=1, max_value=20, step=1),
                "pomos_done": st.column_config.NumberColumn("Pomodoros hechos", min_value=0, max_value=100, step=1),
                "hoy": st.column_config.CheckboxColumn("Hoy"),
                "done": st.column_config.CheckboxColumn("Hecha"),
            },
            key="editor_tareas"
        )

        # Aplicar cambios del editor a la lista real (por id)
        # Hacemos merge por posición visible (índices alineados con df_view)
        for idx, (_, row) in enumerate(edited.iterrows()):
            real_idx = df_view.index[idx]  # índice dentro de la lista original
            t = st.session_state.tasks[real_idx]
            t["titulo"] = row["titulo"]
            t["prioridad"] = row["prioridad"]
            t["categoria"] = row["categoria"]
            t["pomos_est"] = int(row["pomos_est"])
            t["pomos_done"] = int(row["pomos_done"])
            t["hoy"] = bool(row["hoy"])
            t["done"] = bool(row["done"])

    # Acciones rápidas
    col_actions_1, col_actions_2, col_actions_3 = st.columns([1, 1, 1])
    if col_actions_1.button("🧹 Borrar tareas hechas"):
        before = len(st.session_state.tasks)
        st.session_state.tasks = [t for t in st.session_state.tasks if not t["done"]]
        st.success(f"Eliminadas {before - len(st.session_state.tasks)} tareas completadas.")

    if col_actions_2.button("✅ Marcar 'Hoy' las tareas de prioridad Alta"):
        for t in st.session_state.tasks:
            if t["prioridad"] == "Alta":
                t["hoy"] = True
        st.toast("Tareas Alta → Hoy ✅")

    if col_actions_3.button("🔄 Reset pomodoros hechos (todas)"):
        for t in st.session_state.tasks:
            t["pomos_done"] = 0
            t["done"] = False
        st.toast("Contadores de pomodoros reiniciados.")


# ----------------------------------------
# DERECHA — Temporizador Pomodoro
# ----------------------------------------
with right:
    st.subheader("⏱️ Pomodoro")

    p = st.session_state.pomodoro

    # Seleccionar tarea activa (solo las marcadas para hoy y no hechas)
    opciones = [(t["titulo"], t["id"]) for t in st.session_state.tasks if t["hoy"] and not t["done"]]
    if not opciones:
        st.info("Marca alguna tarea como **Hoy** para poder seleccionarla aquí.")
        p["active_task_id"] = None
    else:
        nombres = [op[0] for op in opciones]
        ids = [op[1] for op in opciones]
        sel = st.selectbox("Tarea activa (sumará pomodoros al completar un ciclo de foco)", nombres)
        p["active_task_id"] = ids[nombres.index(sel)]

    # Configuración rápida de tiempos
    with st.expander("⚙️ Duraciones y opciones", expanded=False):
        col_d1, col_d2, col_d3 = st.columns(3)
        pom_min = col_d1.number_input("Pomodoro (min)", min_value=1, max_value=120, value=p["durations"]["Pomodoro"], step=1)
        sb_min = col_d2.number_input("Descanso corto (min)", min_value=1, max_value=60, value=p["durations"]["Descanso corto"], step=1)
        lb_min = col_d3.number_input("Descanso largo (min)", min_value=1, max_value=90, value=p["durations"]["Descanso largo"], step=1)
        every = st.number_input("Descanso largo cada N pomodoros", min_value=1, max_value=10, value=p["long_break_every"], step=1)
        if st.button("Guardar ajustes de tiempo"):
            p["durations"]["Pomodoro"] = int(pom_min)
            p["durations"]["Descanso corto"] = int(sb_min)
            p["durations"]["Descanso largo"] = int(lb_min)
            p["long_break_every"] = int(every)
            # Si cambiamos tiempos, actualizamos remaining del modo actual
            p["remaining"] = p["durations"][p["mode"]] * 60
            st.success("Duraciones actualizadas.")

    # Botones de modo (como pestañas simples)
    col_m1, col_m2, col_m3 = st.columns(3)
    def set_mode(new_mode: str):
        p["mode"] = new_mode
        p["is_running"] = False
        p["remaining"] = p["durations"][new_mode] * 60
        p["last_tick"] = None

    if col_m1.button("Pomodoro", type="secondary"):
        set_mode("Pomodoro")
    if col_m2.button("Descanso corto", type="secondary"):
        set_mode("Descanso corto")
    if col_m3.button("Descanso largo", type="secondary"):
        set_mode("Descanso largo")

    # -----------------------------
    # Lógica de temporizador
    # -----------------------------
    def tick():
        """Actualiza el temporizador si está en marcha (1 segundo por ciclo)."""
        if not p["is_running"]:
            return
        now = time.time()
        if p["last_tick"] is None:
            p["last_tick"] = now
            return
        elapsed = now - p["last_tick"]
        if elapsed >= 1:
            # Descontamos segundos enteros para ser estables
            dec = int(elapsed)
            p["remaining"] = max(0, p["remaining"] - dec)
            p["last_tick"] = now

    # Actualizar cada segundo cuando está en marcha
    if p["is_running"]:
        st.experimental_rerun  # noqa: only to hint linter
        st.autorefresh = st.experimental_get_query_params  # silence linter (compat)
        st.experimental_set_query_params(_=int(time.time()))  # fuerza un rerun cada segundo
        tick()

    # Al finalizar el conteo
    def on_timer_complete():
        p["is_running"] = False
        p["last_tick"] = None
        # Si terminó un pomodoro de foco, sumamos 1 a la tarea activa
        if p["mode"] == "Pomodoro" and p["active_task_id"] is not None:
            for t in st.session_state.tasks:
                if t["id"] == p["active_task_id"]:
                    t["pomos_done"] += 1
                    # marcar hecha si alcanza estimación
                    if t["pomos_done"] >= t["pomos_est"]:
                        t["done"] = True
                    break
            p["cycles_done"] += 1
            st.balloons()
            st.toast("🎉 ¡Pomodoro completado! Suma 1 a la tarea activa.")

            # Elegir descanso corto/largo
            if p["cycles_done"] % p["long_break_every"] == 0:
                set_mode("Descanso largo")
            else:
                set_mode("Descanso corto")
        else:
            # Si termina un descanso, volvemos a modo Pomodoro
            set_mode("Pomodoro")
        # No arrancamos automáticamente: que el usuario pulse Start

    # Mostrar cronómetro
    mins = p["remaining"] // 60
    secs = p["remaining"] % 60
    timer_str = f"{int(mins):02d}:{int(secs):02d}"

    st.markdown(
        f"""
        <div style="text-align:center; font-size: 72px; font-weight:700; margin: 10px 0;">
            {timer_str}
        </div>
        <p style="text-align:center; color:#888; margin-top:-10px;">Modo: <b>{p['mode']}</b></p>
        """,
        unsafe_allow_html=True
    )

    # Barra de progreso
    total_secs = p["durations"][p["mode"]] * 60
    progress = 1.0 - (p["remaining"] / total_secs if total_secs else 0)
    st.progress(progress)

    # Controles
    col_c1, col_c2, col_c3 = st.columns(3)
    if col_c1.button("▶️ Start"):
        # Si estaba parado, arrancamos desde remaining actual
        p["is_running"] = True
        p["last_tick"] = None  # se fijará en tick()
    if col_c2.button("⏸️ Pausa"):
        p["is_running"] = False
        p["last_tick"] = None
    if col_c3.button("⏹️ Reset"):
        p["is_running"] = False
        p["remaining"] = p["durations"][p["mode"]] * 60
        p["last_tick"] = None

    # Si llega a cero, gestionar fin
    if p["remaining"] <= 0:
        on_timer_complete()

    # Info de ciclos
    st.caption(f"Pomodoros completados hoy: **{p['cycles_done']}**")

# ----------------------------------------
# Pie: Resumen rápido
# ----------------------------------------
st.markdown("---")
col_s1, col_s2, col_s3, col_s4 = st.columns(4)
total = len(st.session_state.tasks)
hechas = len([t for t in st.session_state.tasks if t["done"]])
hoy = len([t for t in st.session_state.tasks if t["hoy"] and not t["done"]])
pomos_tot = sum(t["pomos_done"] for t in st.session_state.tasks)
col_s1.metric("Tareas totales", total)
col_s2.metric("Completadas", hechas)
col_s3.metric("Pendientes para hoy", hoy)
col_s4.metric("Pomodoros hechos", pomos_tot)

st.caption("💡 Consejo: marca como **Hoy** lo crítico, usa **Alta** para priorizar y trabaja en bloques de 25' con descansos.")
