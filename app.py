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
            "mode": "Pomodoro",           # Pomodoro | Descanso corto | Descanso largo
            "durations": {                # minutos por modo
                "Pomodoro": 25,
                "Descanso corto": 5,
                "Descanso largo": 15
            },
            "long_break_every": 4,      # cada 4 pomodoros → descanso largo
            "cycles_done": 0,           # pomodoros terminados en el día
            "is_running": False,
            "remaining": 25 * 60,       # segundos
            "last_tick": None,
            "active_task_id": None      # tarea seleccionada para sumar pomodoros
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

    # Hacemos una copia de los datos para la vista, manteniendo el índice original
    tasks_with_original_indices = [dict(t, original_index=i) for i, t in enumerate(st.session_state.tasks)]
    df_view = apply_filters(tasks_with_original_indices)


    if df_view.empty:
        st.info("No hay tareas para mostrar con los filtros actuales.")
    else:
        # Orden visual: primero hoy, luego prioridad Alta>Media>Baja, luego no hechas
        prioridad_order = {"Alta": 0, "Media": 1, "Baja": 2}
        df_view['prioridad_sort'] = df_view['prioridad'].map(prioridad_order)

        df_view = df_view.sort_values(
            by=["hoy", "prioridad_sort", "done"],
            ascending=[False, True, True]
        )

        # Editor en línea
        edited_df = st.data_editor(
            df_view[["titulo", "prioridad", "categoria", "pomos_est", "pomos_done", "hoy", "done"]],
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            key="editor_tareas",
            column_config={
                "titulo": st.column_config.TextColumn("Título", width="large"),
                "prioridad": st.column_config.SelectboxColumn("Prioridad", options=PRIORIDADES),
                "categoria": st.column_config.SelectboxColumn("Categoría", options=CATEGORIAS),
                "pomos_est": st.column_config.NumberColumn("Pomodoros (est.)", min_value=1, max_value=20, step=1),
                "pomos_done": st.column_config.NumberColumn("Pomodoros hechos", min_value=0, max_value=100, step=1),
                "hoy": st.column_config.CheckboxColumn("Hoy"),
                "done": st.column_config.CheckboxColumn("Hecha"),
            },
        )
        
        # Aplicar cambios del editor a la lista real (por id)
        if edited_df is not None:
            # Iteramos sobre los cambios detectados por Streamlit
            for i, (original_row, edited_row) in enumerate(zip(df_view.to_dict('records'), edited_df.to_dict('records'))):
                # Comparamos si la fila ha cambiado para evitar escrituras innecesarias
                if original_row != edited_row:
                    original_index = original_row['original_index']
                    
                    st.session_state.tasks[original_index]["titulo"] = edited_row["titulo"]
                    st.session_state.tasks[original_index]["prioridad"] = edited_row["prioridad"]
                    st.session_state.tasks[original_index]["categoria"] = edited_row["categoria"]
                    st.session_state.tasks[original_index]["pomos_est"] = int(edited_row["pomos_est"])
                    st.session_state.tasks[original_index]["pomos_done"] = int(edited_row["pomos_done"])
                    st.session_state.tasks[original_index]["hoy"] = bool(edited_row["hoy"])
                    st.session_state.tasks[original_index]["done"] = bool(edited_row["done"])


    # Acciones rápidas
    col_actions_1, col_actions_2, col_actions_3 = st.columns([1, 1, 1])
    if col_actions_1.button("🧹 Borrar tareas hechas"):
        before = len(st.session_state.tasks)
        st.session_state.tasks = [t for t in st.session_state.tasks if not t["done"]]
        st.success(f"Eliminadas {before - len(st.session_state.tasks)} tareas completadas.")
        st.rerun()

    if col_actions_2.button("✅ Marcar 'Hoy' las tareas de prioridad Alta"):
        for t in st.session_state.tasks:
            if t["prioridad"] == "Alta":
                t["hoy"] = True
        st.toast("Tareas Alta → Hoy ✅")
        st.rerun()

    if col_actions_3.button("🔄 Reset pomodoros hechos (todas)"):
        for t in st.session_state.tasks:
            t["pomos_done"] = 0
            t["done"] = False
        st.toast("Contadores de pomodoros reiniciados.")
        st.rerun()


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
        
        # Encontrar el índice de la tarea activa actual, si existe
        try:
            current_task_index = ids.index(p.get("active_task_id"))
        except (ValueError, TypeError):
            current_task_index = 0 # Por defecto la primera
            p["active_task_id"] = ids[0] if ids else None

        sel = st.selectbox("Tarea activa (sumará pomodoros al completar un ciclo de foco)", nombres, index=current_task_index)
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
            # Si cambiamos tiempos, actualizamos remaining del modo actual si no está corriendo
            if not p["is_running"]:
                p["remaining"] = p["durations"][p["mode"]] * 60
            st.success("Duraciones actualizadas.")
            st.rerun()

    # Botones de modo (como pestañas simples)
    col_m1, col_m2, col_m3 = st.columns(3)
    def set_mode(new_mode: str):
        p["mode"] = new_mode
        p["is_running"] = False
        p["remaining"] = p["durations"][new_mode] * 60
        p["last_tick"] = None

    if col_m1.button("Pomodoro"):
        set_mode("Pomodoro")
        st.rerun()
    if col_m2.button("Descanso corto"):
        set_mode("Descanso corto")
        st.rerun()
    if col_m3.button("Descanso largo"):
        set_mode("Descanso largo")
        st.rerun()

    # -----------------------------
    # Lógica de temporizador
    # -----------------------------
    def tick():
        """Actualiza el temporizador si está en marcha."""
        if not p["is_running"]:
            return
        now = time.time()
        if p["last_tick"] is None:
            p["last_tick"] = now
            return
        elapsed = now - p["last_tick"]
        if elapsed >= 1:
            # Descontamos segundos enteros para ser estables
            dec = math.floor(elapsed)
            p["remaining"] = max(0, p["remaining"] - dec)
            p["last_tick"] = now

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

    # Si llega a cero, gestionar fin
    if p["remaining"] <= 0:
        on_timer_complete()
        st.rerun()


    # Mostrar cronómetro
    mins, secs = divmod(p["remaining"], 60)
    timer_str = f"{int(mins):02d}:{int(secs):02d}"

    st.markdown(
        f"""
        <div style="text-align:center; background-color: #2E2E38; border-radius: 10px; padding: 1rem;">
            <p style="text-align:center; color:#888; margin-top:-10px; font-size: 1.2rem;">Modo: <b>{p['mode']}</b></p>
            <div style="font-size: 6rem; font-weight:700; margin: 10px 0; font-family: 'Courier New', monospace;">
                {timer_str}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Barra de progreso
    total_secs = p["durations"][p["mode"]] * 60
    progress = 1.0 - (p["remaining"] / total_secs if total_secs > 0 else 0)
    st.progress(progress)

    # Controles
    col_c1, col_c2, col_c3 = st.columns(3)
    if not p["is_running"]:
        if col_c1.button("▶️ Iniciar", use_container_width=True, type="primary"):
            if p["active_task_id"] is None and p["mode"] == "Pomodoro":
                st.warning("Selecciona una tarea activa antes de iniciar el pomodoro.")
            else:
                p["is_running"] = True
                p["last_tick"] = None
                st.rerun()
    else:
        if col_c2.button("⏸️ Pausa", use_container_width=True):
            p["is_running"] = False
            p["last_tick"] = None
            st.rerun()

    if col_c3.button("⏹️ Reiniciar", use_container_width=True):
        p["is_running"] = False
        p["remaining"] = p["durations"][p["mode"]] * 60
        p["last_tick"] = None
        st.rerun()
        
    # Actualizar cada segundo cuando está en marcha
    if p["is_running"]:
        tick()
        time.sleep(1)
        st.rerun()


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
