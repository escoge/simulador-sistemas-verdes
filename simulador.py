"""Motor del simulador de ahorro para comunidades energéticas (reglas confirmadas por el cliente).

Entradas
  E        energía del cliente (kWh/mes)
  cu       CU base del transformador en la fecha de negociación ($/kWh, sin contribución)
  tipo     Estrato 4 | Oficial | Estrato 5-6 | Industrial | Comercial
  d        descuento sobre el CU (0, 10, 15, 20, 25, 30 %)
  c        cobertura: fracción de E suministrada por la comunidad (0–100 %)
  seg_on   tasa de seguridad SI/NO
  cvm_pct  participación de la comercialización (CVm) en el CU (%)

Reglas
  f_tipo      Estrato 4 y Oficial = 1.00 ; Estrato 5-6, Industrial y Comercial = 1.20 (contribución 20 %)
  CU_tipo     = cu * f_tipo
  Tradicional = E * CU_tipo + seguridad(E)
  Comunidad   = cubierta * cu * (1 - d)            [energía cubierta, CU con descuento]
              + cubierta * CVm                      [comercialización, siempre]
              + no_cubierta * CU_tipo               [energía no cubierta, cobrada por EPM]
              + seguridad(no_cubierta)
  seguridad(x)= x * UVT * factor_tipo   (factor por tipo: tabla del Excel, pág. "Tasa de Seguridad")
  Ahorro      = Tradicional - Comunidad
  Días de ahorro/mes = Ahorro / (E*CU_tipo/31)       (como la celda M40 del Excel)
  Meses de ahorro/año = 0.4 * días                   (como la celda M42 del Excel)
"""
from dataclasses import dataclass

UVT_2026 = 52374
FACTOR_CONTRIB = {"Estrato 4": 1.00, "Oficial": 1.00, "Estrato 5-6": 1.20, "Industrial": 1.20, "Comercial": 1.20}
# Factor de seguridad (kWh por UVT) por tipo, tomado de la tabla del Excel
FACTOR_SEGURIDAD = {"Estrato 4": 0.0017, "Estrato 5-6": 0.0017, "Industrial": 0.0013,
                    "Comercial": 0.0015, "Oficial": 0.0012}
DESCUENTOS = [0, 10, 15, 20, 25, 30]


@dataclass
class Resultado:
    cu_tipo: float
    trad_energia: float
    trad_seguridad: float
    trad_total: float
    com_cubierta: float
    com_cvm: float
    com_no_cubierta: float
    com_seguridad: float
    com_total: float
    ahorro: float
    ahorro_pct: float
    dias_ahorro: float
    meses_ahorro_anio: float
    ahorro_anual: float


def simular(E, cu, tipo, d_pct, c_pct, seg_on=True, cvm_pct=12.3, factor_seg_override=None):
    if tipo not in FACTOR_CONTRIB:
        raise ValueError(f"Tipo no reconocido: {tipo}")
    if d_pct not in DESCUENTOS:
        raise ValueError("Descuento no válido")
    if not 0 <= c_pct <= 100:
        raise ValueError("Cobertura fuera de rango")
    f = FACTOR_CONTRIB[tipo]
    cu_t = cu * f
    fac_seg = factor_seg_override if factor_seg_override is not None else FACTOR_SEGURIDAD[tipo]
    cob = E * c_pct / 100
    no_cob = E - cob
    d = d_pct / 100
    cvm = cu * cvm_pct / 100                     # comercialización en pesos/kWh (proporción del CU base)

    seg_t = E * UVT_2026 * fac_seg if seg_on else 0.0
    trad_e = E * cu_t
    trad_total = trad_e + seg_t

    com_cub = cob * cu * (1 - d)
    com_cvm = cob * cvm
    com_nocub = no_cob * cu_t
    com_seg = no_cob * UVT_2026 * fac_seg if seg_on else 0.0
    com_total = com_cub + com_cvm + com_nocub + com_seg

    ahorro = trad_total - com_total
    dias = ahorro / (trad_e / 31) if trad_e else 0.0
    return Resultado(
        cu_tipo=cu_t, trad_energia=trad_e, trad_seguridad=seg_t, trad_total=trad_total,
        com_cubierta=com_cub, com_cvm=com_cvm, com_no_cubierta=com_nocub, com_seguridad=com_seg,
        com_total=com_total, ahorro=ahorro, ahorro_pct=(ahorro / trad_total * 100) if trad_total else 0.0,
        dias_ahorro=dias, meses_ahorro_anio=0.4 * dias, ahorro_anual=ahorro * 12,
    )


# ---------------------------------------------------------------------------
# Contrato multianual
# ---------------------------------------------------------------------------
import pandas as pd

# Participación de la comercialización (CVm) en el CU, promedio 2024–2026 (fuente: análisis de margen)
CVM_PCT = {"EPM": 13.10, "Compartido": 13.59, "Cliente": 14.11}
MODALIDAD_BASE = {"EPM": "EPM", "Compartido": "Compartido", "Cliente": "Cliente"}
TRANSFORMADORES = list(MODALIDAD_BASE.keys())
MESES_PLAZO = {3: 36, 5: 60, 10: 120}


def trayectoria_cu(base_csv, modalidad, escenario, fecha_neg, cu_neg):
    """CU mensual del contrato. Histórico hasta oct-2026, luego el escenario elegido.
    El CU de la fecha de negociación se escala con la trayectoria (cu_neg = valor de esa fecha)."""
    prop = MODALIDAD_BASE[modalidad]
    df = pd.read_csv(base_csv, encoding="utf-8-sig", usecols=["Fecha", "Escenario", "Propiedad", "Tipo_Precio", "Precio_nominal_$kWh"])
    df = df[(df.Propiedad == prop) & (df.Tipo_Precio == "CU base")].copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    hist = df[df.Escenario == "Histórico"].set_index("Fecha")["Precio_nominal_$kWh"]
    proy = df[df.Escenario == escenario].set_index("Fecha")["Precio_nominal_$kWh"]
    serie = pd.concat([hist[hist.index <= "2026-10-01"], proy[proy.index > "2026-10-01"]]).sort_index()
    f0 = pd.Timestamp(fecha_neg)
    p0 = serie.loc[f0]
    return cu_neg * serie / p0            # CU en cada mes, escalado al valor de negociación


def simular_contrato(base_csv, E, cu_neg, fecha_neg, plazo_anios, tipo, d_pct, c_pct,
                     seg_on, modalidad, escenario):
    cu_serie = trayectoria_cu(base_csv, modalidad, escenario, fecha_neg, cu_neg)
    f0 = pd.Timestamp(fecha_neg)
    fechas = pd.date_range(f0 + pd.DateOffset(months=1), periods=MESES_PLAZO[plazo_anios], freq="MS")
    filas = []
    for f in fechas:
        cu_m = float(cu_serie.loc[f]) if f in cu_serie.index else float(cu_serie.iloc[-1])
        r = simular(E, cu_m, tipo, d_pct, c_pct, seg_on, CVM_PCT[modalidad])
        filas.append({"Fecha": f, "CU ($/kWh)": round(cu_m, 2), "Sin comunidad ($)": round(r.trad_total),
                      "Con comunidad ($)": round(r.com_total), "Ahorro ($)": round(r.ahorro),
                      "Ahorro (%)": round(r.ahorro_pct, 2), "Días de ahorro": round(r.dias_ahorro, 2)})
    m = pd.DataFrame(filas)
    resumen = {
        "Meses de contrato": len(m),
        "Costo total sin comunidad ($)": int(m["Sin comunidad ($)"].sum()),
        "Costo total con comunidad ($)": int(m["Con comunidad ($)"].sum()),
        "Ahorro total ($)": int(m["Ahorro ($)"].sum()),
        "Ahorro promedio mensual ($)": round(m["Ahorro ($)"].mean()),
        "Ahorro promedio anual ($)": round(m["Ahorro ($)"].mean() * 12),
        "Ahorro promedio (%)": round(m["Ahorro (%)"].mean(), 2),
        "Días de ahorro promedio al mes": round(m["Días de ahorro"].mean(), 2),
        "Meses de ahorro al año (promedio)": round(0.4 * m["Días de ahorro"].mean(), 2),
    }
    return m, resumen
