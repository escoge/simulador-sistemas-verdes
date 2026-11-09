# Simulador de ahorro · Comunidades energéticas (Sistemas Verdes)

App en Streamlit con dos perfiles:
- **Cliente:** consumo, tipo de cliente, transformador y plazo. Descuento según la tabla por consumo (no editable).
- **Asesor:** todos los parámetros. Descuento editable y panel de parámetros técnicos.

## Contenido
| Archivo | Para qué sirve |
|---|---|
| `app.py` | Interfaz (Streamlit). |
| `simulador.py` | Motor de cálculo. Validado contra el Excel de referencia. |
| `data/Tarifas_EPM_CU_Consolidado_Proyectado.csv` | CU histórico y proyectado por transformador y escenario. Es la única fuente de datos de la app. |
| `tests/test_simulador.py` | Pruebas del motor (incluye la comparación con el Excel). |
| `.streamlit/config.toml` | Colores de la marca. |
| `requirements.txt` | Librerías necesarias. |

## Requisitos
- Python 3.10 o superior.
- Conexión a internet sólo para instalar las librerías (la app no consulta internet).

## Instalación y ejecución (Windows, macOS o Linux)
```bash
cd App_Simulador
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
La app abre en el navegador en `http://localhost:8501`.

## Pruebas
```bash
python -m pytest -q tests
```

## Publicar para clientes y asesores
- **Interno (red de la empresa):** ejecutar `streamlit run app.py --server.address 0.0.0.0` en un servidor y compartir la dirección.
- **En la nube:** subir la carpeta a un repositorio y desplegar en Streamlit Community Cloud (archivo principal `app.py`). Revisar antes las políticas de datos.

## Reglas que implementa
- CU de la fecha de negociación desde la base de datos según transformador (EPM, Compartido, Cliente) y escenario.
- Contribución 20 % derivada del tipo de cliente (Comercial, Industrial, Estrato 5-6 = 1.20; Estrato 4 y Oficial = 1.00).
- Cuota comunitaria = CU × (1 − descuento). Comercialización EPM (14.11 %, 13.59 %, 13.10 % del CU según transformador) siempre.
- Energía no cubierta a CU del tipo. Tasa de seguridad sólo sobre la energía no cubierta.
- Días de ahorro = ahorro ÷ costo diario (31 días). Meses de ahorro al año = 0.4 × días.
