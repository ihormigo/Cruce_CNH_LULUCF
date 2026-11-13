import os
import pandas as pd
import sys

# -----------------------------------------------------------------------------
# 1. PASARELA DICCIONARIO (Cargada directamente en código)
# -----------------------------------------------------------------------------
PASARELA_TIPESTR = {
    71: [('V1', 100)],
    72: [('V', 100)],
    73: [('R', 100)],
    74: [('V63', 50), ('R', 50)],
    75: [('V', 50), ('J', 50)],
    76: [('V', 80), ('T',20)], # <-- Nuevo tipestr-LPEH (Mosaico de cultivo con arbolado (FccArb <20%) --> Quedarán aquí incluidas las superficies formadas por la combinación de
                                                        # áreas agrícolas en yuxtaposición con zonas arboladas, que se reparten en el terreno de forma irregular pero repitiendo
                                                        # unas ciertas pautas de distribución. La FCC del arbolado será siempre menor del 20%.
    77: [('V', 50), ('R', 25), ('S', 25)],
    8: [('J', 100)],           # <-- Nuevo tipestr-LPEH
    82: [('J', 100)],
    83: [('J', 100)],
    84: [('J', 100)],
    85: [('J', 100)],
    87: [('J', 100)],
    88: [('J', 80), ('T', 20)],
    811: [('J1', 100)],
    812: [('J2', 100)],
    861: [('J4', 100)],
    862: [('J', 100)],
    863: [('J5.4', 100)],
    864: [('J', 100)],
    865: [('J6', 100)],
}

# =============================================================================
# FUNCIÓN 1: Procesamiento individual de una fila
# =============================================================================
def procesar_fila_pasarela(row, pasarela_dict):
    """
    Procesa una fila individual:
    1. Identifica coberturas 'V' y 'J' directas y acumula el % restante (No-V/J).
    2. Transforma el % No-V/J aplicando la pasarela según la columna 'tipestr'.
    3. Fusiona y suma porcentajes si coinciden códigos tras la pasarela.
    """
    conteo_lpeh = {}
    total_no_v_j = 0.0

    # -------------------------------------------------------------------------
    # PASO 1: Identificar V/J originales y sumar el porcentaje total No-V/J
    # -------------------------------------------------------------------------
    for i in range(1, 11):
        col_lpeh = f"LPEH_{i}"
        col_per = f"PER_{i}"

        val_lpeh = row.get(col_lpeh)
        val_per = row.get(col_per)

        # Ignorar celdas nulas o vacías
        if pd.isna(val_lpeh) or pd.isna(val_per):
            continue

        val_lpeh = str(val_lpeh).strip()
        try:
            val_per = float(val_per)
        except (ValueError, TypeError):
            continue

        if val_per <= 0 or val_lpeh == "":
            continue

        # Clasificación
        if "V" in val_lpeh or "J" in val_lpeh:
            # Asignación directa (en el origen no hay duplicados)
            conteo_lpeh[val_lpeh] = val_per
        else:
            # Acumulamos el porcentaje sobrante para transformar
            total_no_v_j += val_per

    # -------------------------------------------------------------------------
    # PASOS 2 y 3: Mapear con la pasarela y consolidar porcentajes
    # -------------------------------------------------------------------------
    # 1. Comprobación de existencia del campo
    if "id_tipestr" not in row:
        sys.exit(f"El campo 'id_tipestr' no existe.")

    if total_no_v_j > 0:
        # Lectura directa (siempre en minúsculas)
        tipestr_val = row.get("id_tipestr")

        if pd.notna(tipestr_val):
            try:
                # Convertir a entero si viene como float (ej. 71.0 -> 71)
                tipestr_key = int(float(tipestr_val))
            except (ValueError, TypeError):
                tipestr_key = tipestr_val

            if tipestr_key in pasarela_dict:
                reglas_reparto = pasarela_dict[tipestr_key]

                for cod_destino, proporcion in reglas_reparto:
                    # PASO 2: Calcular nuevo porcentaje
                    porcentaje_ajustado = total_no_v_j * (proporcion/100)

                    # PASO 3: Sumar en el diccionario final (fusiona si ya existía)
                    # Si el código no existía en la fila, lo crea como un nuevo código dentro del diccionario.
                    # ES EN LA SEGUNDA FUNCIÓN DONDE un nuevo codigo pasa a ocupar el LPEH_X que corresponda.
                    # Si hay LPEH_1,2,3 = V/J el nuevo codigo pasa directamente a LPEH_4
                    conteo_lpeh[cod_destino] = conteo_lpeh.get(cod_destino, 0.0) + porcentaje_ajustado

    return conteo_lpeh


# =============================================================================
# FUNCIÓN 2: Aplicación sobre DataFrame (Optimizada para memoria)
# =============================================================================
def aplicar_pasarela_df(df, pasarela_dict):
    """
    Recibe un DataFrame directamente (en lugar de ruta Excel) para agilizar.
    Aplica la pasarela a todos los registros del DataFrame.
    """
    listas_lpeh = []
    listas_per = []

    for _, row in df.iterrows():
        res_dict = procesar_fila_pasarela(row, pasarela_dict)

        if res_dict:
            cod_mayor = max(res_dict, key=res_dict.get)
            codigos_menores_5 = [cod for cod, per in res_dict.items() if per < 5.0]
            for cod in codigos_menores_5:
                res_dict[cod_mayor] += res_dict[cod]
                del res_dict[cod]

        items_ordenados = sorted(res_dict.items(), key=lambda x: x[1], reverse=True)

        fila_lpeh = []
        fila_per = []

        for cod, per in items_ordenados[:10]:
            fila_lpeh.append(cod)
            fila_per.append(int(round(per, 0)))

        while len(fila_lpeh) < 10:
            fila_lpeh.append(None)
            fila_per.append(None)

        listas_lpeh.append(fila_lpeh)
        listas_per.append(fila_per)

    for i in range(1, 11):
        df[f"LPEH_{i}"] = [fila[i - 1] for fila in listas_lpeh]
        df[f"PER_{i}"] = [fila[i - 1] for fila in listas_per]

    return df

# =============================================================================
# FUNCIÓN 3: Eliminación de duplicados lpeh-LPEH
# =============================================================================
def eliminar_duplicados_binomios(df):
    """
    Elimina los registros duplicados basándose exclusivamente en las combinaciones
    de coberturas y porcentajes de origen (lpeh, per) y destino (LPEH_, PER_).
    """
    print('\nIniciando eliminación de duplicados lpehx-LPEH_X...')

    # Identificar columnas de origen y destino dinámicamente
    cols_lpeh_origen = [c for c in df.columns if c.startswith('lpeh')]
    cols_per_origen = [c for c in df.columns if c.startswith('per')]
    cols_LPEH_destino = [c for c in df.columns if c.startswith('LPEH_')]
    cols_PER_destino = [c for c in df.columns if c.startswith('PER_')]

    # Unir todas las columnas que definen el binomio
    cols_subset = cols_lpeh_origen + cols_per_origen + cols_LPEH_destino + cols_PER_destino
    cols_subset = [c for c in cols_subset if c in df.columns]  # Asegurar que existen

    total_inicial = len(df)
    # Eliminar duplicados basados en estas columnas
    df_sin_duplicados = df.drop_duplicates(subset=cols_subset).copy()
    total_final = len(df_sin_duplicados)

    print(f'  -> Registros antes de limpiar: {total_inicial}')
    print(f'  -> Registros después de limpiar: {total_final}')
    print(f'  -> Duplicados eliminados: {total_inicial - total_final}')

    return df_sin_duplicados

# =============================================================================
# --- FUNCIÓN DE SEPARACIÓN DE CASOS POR NUMERO DE COLUMNAS lpehx-LPEH_X
# =============================================================================
def separar_registros_por_binomios(df, zona, output_folder):

    print('\nIniciando separación de los registros procesados en 3 CSVs...')

    # 1. Separar según lpeh de origen
    cols_lpeh_resto = [c for c in df.columns if c.startswith('lpeh') and c != 'lpeh1']

    cond_lpeh1_notna = df['lpeh1'].notna() & (df['lpeh1'].astype(str).str.strip() != '')

    if cols_lpeh_resto:
        cond_resto_lpeh_nulo = df[cols_lpeh_resto].replace(r'^\s*$', pd.NA, regex=True).isna().all(axis=1)
    else:
        cond_resto_lpeh_nulo = pd.Series(True, index=df.index)

    mascara_1_lpeh = cond_lpeh1_notna & cond_resto_lpeh_nulo # lpeh1 tiene valores y el resto de lpehx NO

    df_1_lpeh = df[mascara_1_lpeh].copy()
    df_varios_lpeh = df[~mascara_1_lpeh].copy()  # ---> CASO 3 (N:M)

    # 2. Separar según LPEH de destino (sobre el grupo de 1 lpeh de origen)
    cols_LPEH_resto = [c for c in df_1_lpeh.columns if c.startswith('LPEH_') and c != 'LPEH_1']

    if cols_LPEH_resto:
        cond_resto_LPEH_nulo = df_1_lpeh[cols_LPEH_resto].replace(r'^\s*$', pd.NA, regex=True).isna().all(axis=1)
    else:
        cond_resto_LPEH_nulo = pd.Series(True, index=df_1_lpeh.index)

    df_solo_lpeh1_LPEH_1 = df_1_lpeh[cond_resto_LPEH_nulo].copy()  # ---> CASO 1 (1:1)
    df_solo_lpeh1_varios_LPEH = df_1_lpeh[~cond_resto_LPEH_nulo].copy()  # ---> CASO 2 (1:N)

    # 3. Guardar los 3 archivos
    path_caso1 = os.path.join(output_folder, f'registros_lpeh1_LPEH_1_{zona}.csv')
    path_caso2 = os.path.join(output_folder, f'revisar_lpeh1_varios_LPEH_X_{zona}.csv')
    path_caso3 = os.path.join(output_folder, f'registros_varios_binomios_lpehx_{zona}.csv')

    df_solo_lpeh1_LPEH_1.to_csv(path_caso1, index=False, sep=';', encoding='utf-8-sig')
    df_solo_lpeh1_varios_LPEH.to_csv(path_caso2, index=False, sep=';', encoding='utf-8-sig')
    df_varios_lpeh.to_csv(path_caso3, index=False, sep=';', encoding='utf-8-sig')

    print(f'  -> CSV 1 (1 lpeh origen -> 1 LPEH destino) guardado: {len(df_solo_lpeh1_LPEH_1)} registros.')
    print(f'  -> CSV 2 (1 lpeh origen -> varios LPEH destino) guardado: {len(df_solo_lpeh1_varios_LPEH)} registros.')
    print(f'  -> CSV 3 (Varios lpeh origen) guardado: {len(df_varios_lpeh)} registros.')

    # 4. COMPROBACIÓN DE REGISTROS
    total_inicial = len(df)
    total_separados = len(df_solo_lpeh1_LPEH_1) + len(df_solo_lpeh1_varios_LPEH) + len(df_varios_lpeh)

    print("\n" + "=" * 60)
    print("📊 RESUMEN Y COMPROBACIÓN DE REGISTROS")
    print("=" * 60)
    print(f"Total de registros iniciales procesados : {total_inicial}")
    print(f"Total de registros sumados en los 3 CSV : {total_separados}")

    if total_inicial == total_separados:
        print("\n✅ ¡Coincidencia exacta! Ningún registro se ha perdido en la separación.")
    else:
        print("\n❌ ¡ATENCIÓN! Hay un descuadre en el número de registros. Revisa los datos de entrada.")
    print("=" * 60 + "\n")


# =============================================================================
# BLOQUE PRINCIPAL DE EJECUCIÓN (Flujo corregido)
# =============================================================================
if __name__ == "__main__":
    # Rutas
    output_folder = r"C:\Users\ihormigo\Desktop\resultados_cruce\3 Resultados Atlas y 2a parte metod\2 Resultados a procesar\2a parte metodologia (binomios 1_1)\PB mejora detalle 1_1"
    archivo_entrada = r"C:\Users\ihormigo\Desktop\resultados_cruce\3 Resultados Atlas y 2a parte metod\2 Resultados a procesar\2a parte metodologia (binomios 1_1)\0 Datos brutos de las revisiones\PB_caso3_no_muestreado_2a_parte.xlsx"

    # --- BÚSQUEDA DIRECTA DE PB O C EN EL NOMBRE ---
    nombre_archivo = os.path.basename(archivo_entrada)

    if "PB" in nombre_archivo:
        zona_codigo = "PB"
    elif "C" in nombre_archivo:
        zona_codigo = "C"
    else:
        sys.exit("❌ Error: No se encontró ni 'PB' ni 'C' en el nombre del archivo de entrada.")

    ZONA = f"ZONA_{zona_codigo}"

    # Construcción dinámica del archivo de salida
    archivo_salida_final = os.path.normpath(
        os.path.join(output_folder, f"{zona_codigo}_caso3_no_muestreado_2a_parte_MAPEADO_tipestr.xlsx")
    )

    # 1. Leer Excel (Memoria)
    print(f"Cargando archivo: {nombre_archivo}...")
    print(f"Zona: {ZONA}")
    df_origen = pd.read_excel(archivo_entrada)

    # 2. Aplicar pasarela a todo el DataFrame
    print("Procesando coberturas y aplicando pasarela a todos los registros...")
    df_procesado = aplicar_pasarela_df(df_origen, PASARELA_TIPESTR)

    # 3. AÑADIDO: Eliminar duplicados antes de guardar y separar
    df_procesado = eliminar_duplicados_binomios(df_procesado)

    # 4. Guardar el archivo Excel global con la pasarela aplicada y sin duplicados
    print(f"\nGuardando Excel resultado final en: {archivo_salida_final}...")
    df_procesado.to_excel(archivo_salida_final, index=False)
    print("¡Proceso de guardado finalizado con éxito!")

    # 5. Ejecutar la separación usando el DataFrame limpio
    separar_registros_por_binomios(df_procesado, ZONA, output_folder)
    print("\n¡Flujo completo finalizado!")