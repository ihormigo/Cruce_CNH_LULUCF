import os
import ast
import re
import csv
import pandas as pd
from collections import defaultdict

# -------------------------------------------------------------------------
# DICCIONARIO DE PASARELA TIPEST - LPEH
# (Excluye el código 98 y el 621 "Pendiente")
# -------------------------------------------------------------------------
PASARELA_TIPEST_LPEH = {
    6: [("P", 1.0)],
    8: [("J", 1.0)],
    11: [("T", 1.0)],
    12: [("T", 1.0)],
    14: [("T1", 1.0)],
    15: [("T", 1.0)],
    22: [("S9", 1.0)],
    25: [("S", 0.50), ("V", 0.25), ("R", 0.25)],
    26: [("S", 0.50), ("R", 0.50)],
    31: [("R", 1.0)],
    33: [("Q5", 1.0)],
    41: [("N", 1.0)],
    61: [("P", 1.0)],
    71: [("V1", 1.0)],
    72: [("V", 1.0)],
    73: [("R", 1.0)],
    74: [("V63", 0.50), ("R", 0.50)],
    75: [("V", 0.50), ("J", 0.50)],
    76: [("V", 1.0)],
    77: [("V", 0.50), ("R", 0.25), ("S", 0.25)],
    82: [("J", 1.0)],
    83: [("J", 1.0)],
    84: [("J", 1.0)],
    85: [("J", 1.0)],
    87: [("J", 1.0)],
    88: [("J", 0.80), ("T", 0.20)],
    89: [("J", 1.0)],
    101: [("T43", 1.0)],
    102: [("T43", 1.0)],
    103: [("T43", 1.0)],
    171: [("T", 0.80), ("V", 0.20)],
    172: [("T", 0.80), ("J", 0.20)],
    432: [("U54.ES", 1.0)],
    441: [("N3", 1.0)],
    442: [("U3", 1.0)],
    443: [("U2", 1.0)],
    444: [("U62", 1.0)],
    452: [("U54.ES", 1.0)],
    511: [("P1", 0.50), ("Q5", 0.50)],
    512: [("Q", 1.0)],
    513: [("J5.12", 1.0)],
    521: [("MA2", 1.0)],
    522: [("J5.12", 1.0)],
    611: [("P2", 1.0)],
    613: [("P2", 1.0)],
    62: [("M", 1.0)],
    623: [("M", 1.0)],
    811: [("J1", 1.0)],
    812: [("J2", 1.0)],
    861: [("J4", 1.0)],
    862: [("J", 1.0)],
    863: [("J5.4", 1.0)],
    864: [("J", 1.0)],
    865: [("J6", 1.0)],
    4541: [("U54.ES", 1.0)],
    4542: [("U54.ES", 1.0)],
    6121: [("P1", 1.0)],
    6122: [("J5.35.ES", 1.0)],
    6123: [("P1", 1.0)]
}


def procesar_campo_otras_sup(val):
    """
    Parsea de forma robusta la celda otras_sup ([[codigo1, pct1], ...]),
    aplica la pasarela, suma porcentajes de LPEH coincidentes
    y los devuelve ordenados de mayor a menor porcentaje.
    """
    if pd.isna(val) or not str(val).strip():
        return []

    s = str(val).strip()
    items = None

    # Intentar evaluarlo como lista Python literal
    try:
        items = ast.literal_eval(s)
    except Exception:
        pass

    # Si falla, usar expresión regular para capturar pares numéricos [código, porcentaje]
    if not isinstance(items, list):
        matches = re.findall(r'\[\s*(\d+)\s*[\s,]+\s*([\d.]+)\s*\]', s)
        items = [(int(m[0]), float(m[1])) for m in matches]

    lpeh_totales = defaultdict(float)

    for item in items:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            try:
                tipest_code = int(item[0])
                pct = float(item[1])
            except (ValueError, TypeError):
                continue

            if tipest_code in PASARELA_TIPEST_LPEH:
                for lpeh_code, ratio in PASARELA_TIPEST_LPEH[tipest_code]:
                    lpeh_totales[str(lpeh_code)] += pct * ratio

    # Ordenar de mayor a menor porcentaje acumulado
    return sorted(lpeh_totales.items(), key=lambda x: x[1], reverse=True)


def detectar_delimitador(ruta_archivo):
    """
    Detecta automáticamente si el CSV utiliza ';' o ',' como separador.
    """
    with open(ruta_archivo, 'r', encoding='utf-8-sig', errors='ignore') as f:
        primera_linea = f.readline()
        if ';' in primera_linea:
            return ';'
        elif ',' in primera_linea:
            return ','
    return ';'


def main():
    ruta_entrada = input("Introduce la ruta del archivo de entrada (CSV o Excel): ").strip('"\'')
    carpeta_salida = input("Introduce la ruta de la carpeta de salida: ").strip('"\'')

    if not os.path.exists(ruta_entrada):
        print(f"Error: El archivo de entrada '{ruta_entrada}' no existe.")
        return

    os.makedirs(carpeta_salida, exist_ok=True)

    delimitador = ';'
    if ruta_entrada.lower().endswith(('.xlsx', '.xls')):
        df = pd.read_excel(ruta_entrada, dtype=str)
    else:
        delimitador = detectar_delimitador(ruta_entrada)
        df = pd.read_csv(ruta_entrada, sep=delimitador, dtype=str, engine='python')

    # Columnas a generar
    corr_lpeh_cols = [f'lpeh{i}_corr' for i in range(1, 11)]
    corr_p_cols = [f'p{i}_corr' for i in range(1, 11)]

    for col in corr_lpeh_cols + corr_p_cols:
        df[col] = ""

    # Rellenar valores corregidos desde otras_sup
    if 'otras_sup' in df.columns:
        for idx, row in df.iterrows():
            resultado_lpeh = procesar_campo_otras_sup(row['otras_sup'])
            for i, (lpeh_code, pct) in enumerate(resultado_lpeh[:10], start=1):
                df.at[idx, f'lpeh{i}_corr'] = str(lpeh_code)
                val_pct = int(pct) if pct.is_integer() else round(pct, 2)
                df.at[idx, f'p{i}_corr'] = str(val_pct)

    # Reordenar columnas para posicionar cada _corr inmediatamente a la derecha
    nuevas_columnas = []
    for col in df.columns:
        if col in corr_lpeh_cols or col in corr_p_cols:
            continue

        nuevas_columnas.append(col)

        if col in [f'lpeh{i}' for i in range(1, 11)]:
            corr_col = f'{col}_corr'
            if corr_col in df.columns and corr_col not in nuevas_columnas:
                nuevas_columnas.append(corr_col)

        if col in [f'p{i}' for i in range(1, 11)]:
            corr_col = f'{col}_corr'
            if corr_col in df.columns and corr_col not in nuevas_columnas:
                nuevas_columnas.append(corr_col)

    # Añadir al final cualquier _corr sin columna base equivalente
    for i in range(1, 11):
        if f'lpeh{i}_corr' in df.columns and f'lpeh{i}_corr' not in nuevas_columnas:
            nuevas_columnas.append(f'lpeh{i}_corr')
        if f'p{i}_corr' in df.columns and f'p{i}_corr' not in nuevas_columnas:
            nuevas_columnas.append(f'p{i}_corr')

    df_resultado = df[nuevas_columnas]

    # Guardar manteniendo el separador correcto (;)
    nombre_base = os.path.splitext(os.path.basename(ruta_entrada))[0]
    ruta_salida = os.path.join(carpeta_salida, f"{nombre_base}_equivalencias.csv")

    df_resultado.to_csv(ruta_salida, index=False, sep=delimitador, encoding='utf-8-sig')
    print(f"\nProceso completado. Archivo guardado correctamente en la ruta:\n{ruta_salida}")


if __name__ == '__main__':
    main()