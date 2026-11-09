"""Pruebas del motor. Validan contra el Excel de referencia y las reglas confirmadas."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from simulador import simular, simular_contrato

BASE = Path(__file__).resolve().parents[1] / "data" / "Tarifas_EPM_CU_Consolidado_Proyectado.csv"


def test_coincide_con_excel_de_referencia():
    # Mismas condiciones del Excel: CU de componentes 927.73, Estrato 4, cobertura 100 %, factor seguridad 0.0015
    r = simular(4500, 927.73, "Estrato 4", 25, 100, seg_on=True, cvm_pct=114.28 / 927.73 * 100, factor_seg_override=0.0015)
    assert r.trad_total == pytest.approx(4528309.5, abs=1)
    assert r.com_total == pytest.approx(3645348.75, abs=1)
    assert r.ahorro == pytest.approx(882960.75, abs=1)
    assert r.dias_ahorro == pytest.approx(6.5565, abs=1e-3)
    assert r.meses_ahorro_anio == pytest.approx(2.6226, abs=1e-3)


def test_cobertura_100_sin_seguridad_ni_contribucion_en_cubierta():
    r = simular(15000, 960, "Comercial", 30, 100, seg_on=True, cvm_pct=14.11)
    assert r.com_seguridad == 0.0
    assert r.com_no_cubierta == 0.0
    assert r.com_cubierta == pytest.approx(15000 * 960 * 0.70)      # cuota = CU x (1 - d), sin contribución
    assert r.com_cvm == pytest.approx(15000 * 960 * 0.1411)          # comercialización siempre


def test_contribucion_derivada_del_tipo():
    assert simular(1000, 1000, "Estrato 4", 0, 0, False, 10).cu_tipo == 1000
    assert simular(1000, 1000, "Comercial", 0, 0, False, 10).cu_tipo == pytest.approx(1200)


def test_contrato_tres_plazos():
    for anios, meses in [(3, 36), (5, 60), (10, 120)]:
        m, res = simular_contrato(BASE, 15000, 960, "2026-12-01", anios, "Comercial", 30, 100, True, "EPM", "Medio (caminata con deriva)")
        assert len(m) == meses
        assert (m["Ahorro ($)"] > 0).all()


def test_trayectoria_sigue_escenario():
    m, _ = simular_contrato(BASE, 15000, 960, "2026-12-01", 5, "Comercial", 30, 100, True, "EPM", "Alto (tendencia histórica nominal)")
    assert m["CU ($/kWh)"].iloc[-1] > m["CU ($/kWh)"].iloc[0]
