import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- Configuración de la Página ---
st.set_page_config(page_title="Montana Club Mobile", layout="centered", initial_sidebar_state="expanded")

# --- Estilo Custom (Quiet Luxury) ---
st.markdown("""
    <style>
    .stApp {
        background-color: #0F0D0B;
        color: #F0EDE6;
    }
    /* Botones principales */
    div.stButton > button[kind="primary"] {
        background-color: #5ECFA0;
        color: black;
        border-radius: 8px;
        font-weight: bold;
        border: none;
    }
    /* Botones de peligro (Eliminar) */
    .btn-peligro > div > button {
        background-color: #E57373 !important;
        color: black !important;
    }
    </style>
    """, unsafe_allow_html=True)

DB_FILE = "montana_club.db"

# --- Funciones de Base de Datos ---
def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(productos)")
    columnas_prod = [info[1] for info in cursor.fetchall()]
    if 'precio' in columnas_prod and 'precio_venta' not in columnas_prod:
        cursor.execute("ALTER TABLE productos RENAME COLUMN precio TO costo")
        cursor.execute("ALTER TABLE productos ADD COLUMN precio_venta REAL NOT NULL DEFAULT 0")
        cursor.execute("UPDATE productos SET precio_venta = costo") 
        
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos 
                      (id TEXT PRIMARY KEY, nombre TEXT UNIQUE NOT NULL, costo REAL NOT NULL, precio_venta REAL NOT NULL DEFAULT 0, stock INTEGER NOT NULL DEFAULT 0)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS ventas 
                      (id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, producto_nombre TEXT NOT NULL, cantidad INTEGER NOT NULL, precio_unitario REAL NOT NULL, total REAL NOT NULL, metodo_pago TEXT NOT NULL)''')
    
    cursor.execute("PRAGMA table_info(ventas)")
    columnas_ventas = [info[1] for info in cursor.fetchall()]
    if 'costo_total' not in columnas_ventas:
        cursor.execute("ALTER TABLE ventas ADD COLUMN costo_total REAL NOT NULL DEFAULT 0")
        cursor.execute('''UPDATE ventas SET costo_total = cantidad * IFNULL((SELECT costo FROM productos WHERE productos.nombre = ventas.producto_nombre), 0) WHERE costo_total = 0''')

    cursor.execute("SELECT COUNT(*) FROM productos")
    if cursor.fetchone()[0] == 0:
        catalogo_inicial = [
            ("P001", "Red 750ml", 15000, 27500, 24), ("P002", "Black 750ml", 25000, 47000, 12),
            ("P003", "Gold 750ml", 40000, 72000, 8), ("P004", "Federico Alvear", 2000, 4300, 36),
            ("P006", "Chandon 750ml", 8000, 15000, 18), ("P008", "Sky Regular", 4000, 7500, 25),
            ("P013", "Coca Cola 1.75L", 1500, 3200, 48), ("P015", "Speed 269ml", 600, 1300, 60)
        ]
        cursor.executemany("INSERT INTO productos (id, nombre, costo, precio_venta, stock) VALUES (?, ?, ?, ?, ?)", catalogo_inicial)
    
    conn.commit()
    conn.close()

init_db()

# --- Interfaz de Usuario ---
# 1. Cargamos tu logo en la barra lateral superior
st.sidebar.image("logo_montana.jpeg", use_container_width=True)

# 2. Un título sobrio para el área principal
st.title("Panel de Control")

menu = ["+ Nueva Venta", "💰 Historial Ventas", "📦 Inventario", "🏧 Caja (Hoy)"]
# 3. Usamos 'radio' en lugar de 'selectbox' para que el menú quede fijo y desplegado
choice = st.sidebar.radio("Navegación", menu)

# ==========================================
# 1. NUEVA VENTA
# ==========================================
if choice == "+ Nueva Venta":
    st.markdown("### Registrar Nueva Venta")
    
    conn = get_connection()
    df_prod = pd.read_sql("SELECT nombre, precio_venta, stock, costo FROM productos", conn)
    conn.close()

    if not df_prod.empty:
        producto = st.selectbox("Seleccioná un producto", df_prod['nombre'].tolist())
        datos_p = df_prod[df_prod['nombre'] == producto].iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Stock Disponible", int(datos_p['stock']))
        with col2:
            st.metric("Precio Venta", f"${datos_p['precio_venta']:,.0f}")

        with st.form("form_venta"):
            cantidad = st.number_input("Cantidad", min_value=1, value=1, step=1)
            precio_manual = st.number_input("Precio ($)", value=float(datos_p['precio_venta']), step=100.0)
            metodo = st.selectbox("Método de Pago", ["efectivo", "transferencia"])
            
            submit_venta = st.form_submit_button("Registrar Venta", type="primary")

            if submit_venta:
                if cantidad <= datos_p['stock']:
                    total_venta = cantidad * precio_manual
                    total_costo = cantidad * datos_p['costo']
                    vta_id = f"VTA-{datetime.now().strftime('%H%M%S')}"
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO ventas (id, timestamp, producto_nombre, cantidad, precio_unitario, total, metodo_pago, costo_total) VALUES (?,?,?,?,?,?,?,?)", 
                                   (vta_id, timestamp, producto, cantidad, precio_manual, total_venta, metodo, total_costo))
                    cursor.execute("UPDATE productos SET stock = stock - ? WHERE nombre = ?", (cantidad, producto))
                    conn.commit()
                    conn.close()
                    st.success(f"¡Venta registrada por ${total_venta:,.0f}!")
                    st.rerun()
                else:
                    st.error("No hay stock suficiente.")

# ==========================================
# 2. HISTORIAL DE VENTAS
# ==========================================
elif choice == "💰 Historial Ventas":
    st.markdown("### Historial de Ventas")
    
    conn = get_connection()
    df_ventas = pd.read_sql("SELECT id, timestamp, producto_nombre, cantidad, total, metodo_pago FROM ventas ORDER BY timestamp DESC", conn)
    conn.close()

    if not df_ventas.empty:
        st.dataframe(df_ventas, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("#### Anular Venta")
        venta_a_eliminar = st.selectbox("Selecciona el ID de la venta para anularla:", df_ventas['id'].tolist())
        
        st.markdown('<div class="btn-peligro">', unsafe_allow_html=True)
        if st.button("Anular Venta y Devolver Stock"):
            # Obtener datos de la venta para devolver stock
            detalles_venta = df_ventas[df_ventas['id'] == venta_a_eliminar].iloc[0]
            cant_devolver = int(detalles_venta['cantidad'])
            prod_devolver = detalles_venta['producto_nombre']
            
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ventas WHERE id = ?", (venta_a_eliminar,))
            cursor.execute("UPDATE productos SET stock = stock + ? WHERE nombre = ?", (cant_devolver, prod_devolver))
            conn.commit()
            conn.close()
            st.success(f"Venta {venta_a_eliminar} anulada. Stock devuelto.")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("No hay ventas registradas.")

# ==========================================
# 3. INVENTARIO
# ==========================================
elif choice == "📦 Inventario":
    st.markdown("### Gestión de Inventario")
    
    tab1, tab2, tab3 = st.tabs(["Listado", "Agregar Producto", "Editar / Eliminar"])
    
    conn = get_connection()
    df_inv = pd.read_sql("SELECT id, nombre, costo, precio_venta, stock FROM productos", conn)
    conn.close()

    with tab1:
        st.dataframe(df_inv, use_container_width=True, hide_index=True)

    with tab2:
        with st.form("form_add_prod"):
            nom_nuevo = st.text_input("Nombre del Producto")
            costo_nuevo = st.number_input("Costo ($)", min_value=0.0, step=100.0)
            precio_nuevo = st.number_input("Precio de Venta ($)", min_value=0.0, step=100.0)
            stock_nuevo = st.number_input("Cantidad en Stock", min_value=0, step=1)
            
            if st.form_submit_button("Añadir Producto", type="primary"):
                if nom_nuevo:
                    nuevo_id = f"P{str(datetime.now().timestamp())[-4:]}"
                    try:
                        conn = get_connection()
                        conn.execute("INSERT INTO productos (id, nombre, costo, precio_venta, stock) VALUES (?,?,?,?,?)", 
                                     (nuevo_id, nom_nuevo, costo_nuevo, precio_nuevo, stock_nuevo))
                        conn.commit()
                        conn.close()
                        st.success("Producto agregado exitosamente.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("El nombre de este producto ya existe.")
                else:
                    st.warning("El nombre no puede estar vacío.")

    with tab3:
        if not df_inv.empty:
            prod_edit = st.selectbox("Seleccioná el producto a modificar:", df_inv['nombre'].tolist())
            datos_edit = df_inv[df_inv['nombre'] == prod_edit].iloc[0]
            id_edit = datos_edit['id']
            
            with st.form("form_edit_prod"):
                costo_edit = st.number_input("Costo ($)", value=float(datos_edit['costo']), step=100.0)
                precio_edit = st.number_input("Precio de Venta ($)", value=float(datos_edit['precio_venta']), step=100.0)
                stock_edit = st.number_input("Stock", value=int(datos_edit['stock']), step=1)
                
                if st.form_submit_button("Guardar Cambios", type="primary"):
                    conn = get_connection()
                    conn.execute("UPDATE productos SET costo=?, precio_venta=?, stock=? WHERE id=?", 
                                 (costo_edit, precio_edit, stock_edit, id_edit))
                    conn.commit()
                    conn.close()
                    st.success("Producto actualizado.")
                    st.rerun()
            
            st.markdown("---")
            st.markdown('<div class="btn-peligro">', unsafe_allow_html=True)
            if st.button("Eliminar Producto Definitivamente"):
                conn = get_connection()
                conn.execute("DELETE FROM productos WHERE id = ?", (id_edit,))
                conn.commit()
                conn.close()
                st.success("Producto eliminado.")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 4. CAJA HOY - RANKING Y MÁRGENES
# ==========================================
elif choice == "🏧 Caja (Hoy)":
    import plotly.express as px
    
    st.markdown("### Análisis de Rentabilidad (Hoy)")
    hoy = datetime.now().strftime("%Y-%m-%d")
    
    conn = get_connection()
    df_hoy = pd.read_sql(f"SELECT producto_nombre, total, costo_total, cantidad FROM ventas WHERE timestamp LIKE '{hoy}%'", conn)
    conn.close()

    if not df_hoy.empty:
        # --- CÁLCULOS CLAVE ---
        total_ventas = df_hoy['total'].sum()
        total_costos = df_hoy['costo_total'].sum()
        total_ganancia = total_ventas - total_costos
        
        # Columnas de métricas rápidas
        c1, c2, c3 = st.columns(3)
        c1.metric("Ventas Brutas", f"${total_ventas:,.0f}")
        c2.metric("Costo Mercadería", f"-${total_costos:,.0f}", delta_color="inverse")
        c3.metric("Ganancia Neta", f"${total_ganancia:,.0f}")

        st.markdown("---")

        # --- DISTRIBUCIÓN DE COLUMNAS PARA GRÁFICOS ---
        col_rank, col_margen = st.columns([1.2, 1]) # El ranking suele necesitar un poco más de ancho

        with col_rank:
            st.markdown("##### 🏆 ¿Qué es lo que más se vende?")
            # Agrupamos por producto para el ranking
            df_ranking = df_hoy.groupby('producto_nombre')['cantidad'].sum().reset_index().sort_values('cantidad', ascending=True)
            
            fig_rank = px.bar(
                df_ranking, 
                x='cantidad', 
                y='producto_nombre',
                orientation='h',
                text='cantidad',
                color_discrete_sequence=['#5ECFA0']
            )
            fig_rank.update_traces(textposition='outside')
            fig_rank.update_layout(
                margin=dict(l=0, r=40, t=10, b=10),
                height=300,
                xaxis_visible=False, # Limpiamos el eje X porque ya tenemos el texto en las barras
                yaxis_title=None,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_rank, use_container_width=True, config={'displayModeBar': False})

        with col_margen:
            st.markdown("##### 📈 Margen de Ganancia")
            # Datos para la torta
            df_pie = pd.DataFrame({
                "Tipo": ["Costo", "Ganancia"],
                "Valor": [total_costos, total_ganancia]
            })
            
            fig_pie = px.pie(
                df_pie, 
                values='Valor', 
                names='Tipo',
                hole=0.6, # Estilo "Donut" más moderno
                color_discrete_map={"Costo": "#3B3B3B", "Ganancia": "#5ECFA0"}
            )
            fig_pie.update_traces(textinfo='percent')
            fig_pie.update_layout(
                margin=dict(l=20, r=20, t=10, b=10),
                height=300,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})

        # --- TIP DE NEGOCIO ---
        if total_ventas > 0:
            margen_p = (total_ganancia / total_ventas) * 100
            st.info(f"💡 Por cada $1.000 vendidos hoy, te quedan **${int(margen_p * 10)}** de ganancia real.")

    else:
        st.info("Todavía no hay ventas registradas para hoy.")
