"""Simulador de ahorro con comunidades energéticas · Sistemas Verdes.

Fecha de negociación: mes y año (por defecto oct-2026; puede ser futura hasta dic-2036).

Dos perfiles:
  Cliente  -> pocas preguntas: consumo, tipo de cliente, transformador y plazo.
              Descuento según la tabla por consumo (no editable), escenario medio.
  Asesor   -> todos los parámetros. El descuento es editable y se muestra el detalle técnico.

El CU de la fecha de negociación se toma de la base de datos según transformador y escenario.
"""
from pathlib import Path
import pandas as pd
import streamlit as st

from simulador import (simular, simular_contrato, FACTOR_CONTRIB, TRANSFORMADORES, CVM_PCT,
                       UVT_2026, FACTOR_SEGURIDAD, DESCUENTOS)

BASE = Path(__file__).parent / "data" / "Tarifas_EPM_CU_Consolidado_Proyectado.csv"
ESCENARIOS = ["Bajo (Holt amortiguado)", "Medio (caminata con deriva)", "Alto (tendencia histórica nominal)"]
MESES_ES = {1:"ene",2:"feb",3:"mar",4:"abr",5:"may",6:"jun",7:"jul",8:"ago",9:"sep",10:"oct",11:"nov",12:"dic"}


def descuento_por_consumo(kwh: float) -> int:
    """Tabla de descuento por nivel de consumo (kWh/mes)."""
    if kwh < 2000:   return 0
    if kwh <= 2500:  return 5
    if kwh <= 3500:  return 10
    if kwh <= 5000:  return 15
    if kwh <= 8000:  return 20
    if kwh <= 10000: return 25
    return 30


@st.cache_data
def cu_negociacion(transformador: str, escenario: str, fecha: pd.Timestamp) -> float:
    df = pd.read_csv(BASE, encoding="utf-8-sig", usecols=["Fecha", "Escenario", "Propiedad", "Tipo_Precio", "Precio_nominal_$kWh"])
    df = df[(df.Propiedad == transformador) & (df.Tipo_Precio == "CU base") & (df.Escenario.isin(["Histórico", escenario]))]
    df["Fecha"] = pd.to_datetime(df.Fecha)
    serie = df.drop_duplicates("Fecha").set_index("Fecha")["Precio_nominal_$kWh"]
    return float(serie.loc[fecha])


MESES_OPCIONES = list(range(1, 13))
ANIOS_OPCIONES = list(range(2016, 2037))
FECHA_DEFECTO = pd.Timestamp("2026-10-01")   # valor por defecto: octubre de 2026 (último dato real)
MESES_NOMBRE = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}


def selector_fecha(etiqueta: str, clave: str) -> pd.Timestamp:
    """Selector de mes y año para la fecha de negociación (desde nov-2026 hasta dic-2036)."""
    st.sidebar.markdown(f"**{etiqueta}**  \n_por defecto: oct-2026_")
    c1, c2 = st.sidebar.columns(2)
    anio = c2.selectbox("Año", ANIOS_OPCIONES, index=ANIOS_OPCIONES.index(FECHA_DEFECTO.year), key=f"{clave}_anio")
    mes = c1.selectbox("Mes", MESES_OPCIONES, index=FECHA_DEFECTO.month - 1,
                       format_func=lambda m: MESES_NOMBRE[m], key=f"{clave}_mes")
    return pd.Timestamp(year=anio, month=mes, day=1)


def fmt_m(x):  return f"${x/1e6:,.2f} M"
def fmt_p(x):  return f"{x:,.0f}"


def main():
    st.set_page_config(page_title="Simulador de ahorro · Sistemas Verdes", layout="wide")
    st.title("Simulador de ahorro con comunidades energéticas")
    st.caption("Valores en pesos nominales. El CU de la fecha de negociación viene de la base de datos según transformador y escenario.")

    perfil = st.sidebar.radio("Perfil", ["Cliente", "Asesor"], horizontal=True)
    st.sidebar.header("Tus datos" if perfil == "Cliente" else "Parámetros de la simulación")

    consumo = st.sidebar.number_input("Consumo mensual (kWh)", min_value=0.0, value=15000.0, step=100.0)
    tipo = st.sidebar.selectbox("Tipo de cliente", list(FACTOR_CONTRIB.keys()), index=4)
    transformador = st.sidebar.selectbox("Transformador", TRANSFORMADORES, index=2)

    if perfil == "Cliente":
        fecha = selector_fecha("Fecha de negociación", "fecha_cliente")
        plazo = st.sidebar.radio("Plazo del contrato (años)", [3, 5, 10], index=1, horizontal=True)
        escenario = ESCENARIOS[1]
        descuento = descuento_por_consumo(consumo)
        cobertura = 100
        seg_on = True
        st.sidebar.info(f"Descuento según tu consumo: **{descuento} %** (no editable).")
    else:
        fecha = selector_fecha("Fecha de negociación", "fecha_asesor")
        plazo = st.sidebar.selectbox("Plazo del contrato (años)", [3, 5, 10], index=1)
        escenario = st.sidebar.selectbox("Escenario de CU", ESCENARIOS, index=1)
        sugerido = descuento_por_consumo(consumo)
        descuento = st.sidebar.selectbox("Descuento sobre el CU (editable)", DESCUENTOS,
                                         index=DESCUENTOS.index(sugerido), help=f"Sugerido por consumo: {sugerido} %")
        cobertura = st.sidebar.slider("Cobertura (%)", 0, 100, 100, 5)
        seg_on = st.sidebar.radio("Tasa de seguridad", ["SI", "NO"], index=0, horizontal=True) == "SI"

    cu = cu_negociacion(transformador, escenario, fecha)
    cvm = CVM_PCT[transformador]

    m, res = simular_contrato(BASE, consumo, cu, fecha, plazo, tipo, descuento, cobertura, seg_on, transformador, escenario)
    r = simular(consumo, cu, tipo, descuento, cobertura, seg_on, cvm)

    st.subheader(f"Con la comunidad pagarías {fmt_m(r.com_total)} al mes y ahorrarías {fmt_m(r.ahorro)} ({r.ahorro_pct:.1f} %).")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ahorro mensual (al negociar)", fmt_m(r.ahorro), f"{r.ahorro_pct:.1f} %")
    c2.metric("Ahorro anual (primer año)", fmt_m(m["Ahorro ($)"].iloc[:12].sum()))
    c3.metric("Días de ahorro al mes", f"{r.dias_ahorro:.1f}")
    c4.metric("Meses de ahorro al año", f"{r.meses_ahorro_anio:.1f}")

    st.subheader("Comparación mensual: sin comunidad frente a con comunidad")
    cob_kwh = consumo * cobertura / 100
    no_cob_kwh = consumo - cob_kwh
    comp = pd.DataFrame({
        "Concepto": ["Energía cubierta por la comunidad", "Comercialización EPM (siempre)",
                     "Energía no cubierta (CU del tipo)", "Tasa de seguridad", "Total mensual"],
        "Sin comunidad ($)": [cob_kwh * r.cu_tipo, 0.0, no_cob_kwh * r.cu_tipo, r.trad_seguridad, r.trad_total],
        "Con comunidad ($)": [r.com_cubierta, r.com_cvm, r.com_no_cubierta, r.com_seguridad, r.com_total],
    })
    comp["Diferencia ($)"] = comp["Sin comunidad ($)"] - comp["Con comunidad ($)"]
    st.dataframe(comp.style.format({"Sin comunidad ($)": fmt_p, "Con comunidad ($)": fmt_p, "Diferencia ($)": fmt_p}),
                 hide_index=True, width="stretch")

    st.subheader("Flujo por año del contrato")
    anual = m.assign(Año=[f"Año {k // 12 + 1}" for k in range(len(m))]).groupby("Año", sort=False).agg(
        **{"Sin comunidad ($)": ("Sin comunidad ($)", "sum"), "Con comunidad ($)": ("Con comunidad ($)", "sum"),
           "Ahorro ($)": ("Ahorro ($)", "sum")}).reset_index()
    anual["Ahorro (%)"] = (anual["Ahorro ($)"] / anual["Sin comunidad ($)"] * 100).round(1)
    st.dataframe(anual.style.format({"Sin comunidad ($)": fmt_p, "Con comunidad ($)": fmt_p, "Ahorro ($)": fmt_p, "Ahorro (%)": "{:.1f} %"}),
                 hide_index=True, width="stretch")
    st.bar_chart(anual.set_index("Año")[["Sin comunidad ($)", "Con comunidad ($)"]])

    with st.expander("Flujo mensual del contrato (primeros 12 meses)"):
        mm = m.head(12).copy()
        mm["Mes"] = pd.to_datetime(mm.Fecha).apply(lambda f: f"{MESES_ES[f.month]}-{str(f.year)[2:]}")
        st.dataframe(mm[["Mes", "CU ($/kWh)", "Sin comunidad ($)", "Con comunidad ($)", "Ahorro ($)", "Ahorro (%)"]]
                     .style.format({"Sin comunidad ($)": fmt_p, "Con comunidad ($)": fmt_p, "Ahorro ($)": fmt_p, "Ahorro (%)": "{:.1f} %"}),
                     hide_index=True, width="stretch")

    if perfil == "Asesor":
        with st.expander("Parámetros técnicos (para explicar el cálculo)", expanded=True):
            st.markdown(
                f"- **CU de la fecha de negociación** ({transformador}, {escenario}): **{cu:,.2f} $/kWh**\n"
                f"- **Factor del tipo** ({tipo}): **{FACTOR_CONTRIB[tipo]:.2f}** → CU del tipo **{r.cu_tipo:,.2f} $/kWh**\n"
                f"- **Descuento**: {descuento} % → cuota comunitaria **{cu*(1-descuento/100):,.2f} $/kWh**\n"
                f"- **Comercialización EPM**: {cvm:.2f} % del CU → **{cu*cvm/100:,.2f} $/kWh** (siempre)\n"
                f"- **Tasa de seguridad**: factor {FACTOR_SEGURIDAD[tipo]} × UVT {UVT_2026:,} → "
                f"**{FACTOR_SEGURIDAD[tipo]*UVT_2026:,.2f} $/kWh**, solo en la energía no cubierta\n"
                f"- **Cobertura**: {cobertura} %. Con 100 % no hay tasa de seguridad ni contribución en la energía cubierta.\n"
                f"- **Días de ahorro** = ahorro ÷ (energía del tipo ÷ 31). **Meses de ahorro al año** = 0.4 × días."
            )
        with st.expander("Tabla de descuento por consumo"):
            st.table(pd.DataFrame({"Consumo (kWh/mes)": ["< 2,000", "2,001–2,500", "2,501–3,500", "3,501–5,000", "5,001–8,000", "8,001–10,000", "10,001–15,000", "> 15,000"],
                                   "Descuento": ["0 %", "5 %", "10 %", "15 %", "20 %", "25 %", "30 %", "30 % (supuesto)"]}))
    else:
        st.info("Este resultado es orientativo. Para una oferta formal, consulte con su asesor comercial.")

    st.caption("Cálculo según el motor validado contra el simulador en Excel de referencia.")


if __name__ == "__main__":
    main()
