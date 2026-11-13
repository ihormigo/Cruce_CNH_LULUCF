import os
import pandas as pd

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
# FUNCIÓN 2: Aplicación sobre todo el DataFrame y formateo de salida
# =============================================================================
def aplicar_pasarela_df(archivo_entrada, pasarela_dict):
    """
    Aplica la función procesar_fila_pasarela a cada fila del DataFrame,
    ordena las coberturas de mayor a menor porcentaje y actualiza las columnas
    LPEH_1...10 y PER_1...10 de forma rápida usando listas temporales.
    """
    df = pd.read_excel(archivo_entrada)

    listas_lpeh = []
    listas_per = []

    for _, row in df.iterrows():
        # Obtener el diccionario resuelto para la fila
        res_dict = procesar_fila_pasarela(row, pasarela_dict)

        # --- NUEVA REGLA: Trasvasar porcentajes < 5% al mayor ---
        if res_dict:
            cod_mayor = max(res_dict, key=res_dict.get)
            codigos_menores_5 = [cod for cod, per in res_dict.items() if per < 5.0]
            for cod in codigos_menores_5:
                res_dict[cod_mayor] += res_dict[cod]
                del res_dict[cod]
        # --------------------------------------------------------

        # Ordenar coberturas por porcentaje (key=lambda x: x[1] indica que debe ordenar tomando como referencia el
        # segundo elemento de la tupla (el porcentaje)) de forma descendente.
        items_ordenados = sorted(res_dict.items(), key=lambda x: x[1], reverse=True)

        fila_lpeh = []
        fila_per = []

        # Extraer hasta un máximo de 10 coberturas
        for cod, per in items_ordenados[:10]:
            fila_lpeh.append(cod)
            fila_per.append(int(round(per, 0)))

        # Rellenar con None / 0.0 hasta completar las 10 columnas si hay menos de 10
        while len(fila_lpeh) < 10:
            fila_lpeh.append(None)
            fila_per.append(None)

        listas_lpeh.append(fila_lpeh)
        listas_per.append(fila_per)

    # Actualizar las columnas objetivo en el DataFrame (asignación masiva y rápida)
    for i in range(1, 11):
        df[f"LPEH_{i}"] = [fila[i - 1] for fila in listas_lpeh]
        df[f"PER_{i}"] = [fila[i - 1] for fila in listas_per]

    return df


# =============================================================================
# BLOQUE PRINCIPAL DE EJECUCIÓN
# =============================================================================
if __name__ == "__main__":
    # 1. Cargar el archivo Excel original
    output_folder = r"C:\Users\ihormigo\Desktop\resultados_cruce\3 Resultados Atlas y 2a parte metod\2 Resultados a procesar\2a parte metodologia (binomios 1_1)\C mejora detalle 1_1"

    archivo_entrada = r"C:\Users\ihormigo\Desktop\resultados_cruce\3 Resultados Atlas y 2a parte metod\2 Resultados a procesar\2a parte metodologia (binomios 1_1)\0 Datos brutos de las revisiones\C_caso3_no_muestreado_2a_parte.xlsx"
    archivo_salida = os.path.normpath(os.path.join(output_folder,"C_caso3_no_muestreado_2a_parte_MAPEADO_tipestr.xlsx"))

    print(f"Cargando archivo: {os.path.basename(archivo_entrada)}...")

    # 2. Aplicar el proceso de pasarela
    print("Procesando coberturas y aplicando pasarela...")
    df_resultado = aplicar_pasarela_df(archivo_entrada, PASARELA_TIPESTR)

    # 3. Guardar el archivo Excel procesado
    print(f"Guardando resultado en: {archivo_salida}...")
    df_resultado.to_excel(archivo_salida, index=False)
    print("¡Proceso finalizado con éxito!")


#
# def seleccion_1binomio_multibinomio(self):
#     print('\nIniciando selección de los registros con 1 binomio...')
#
#     if self.csv_limpio is None:
#         print("❌ Error: No hay datos en memoria. Asegúrate de que el Join se ha ejecutado.")
#         return
#
#     df_csv_limpio = self.csv_limpio.copy()
#
#     cols_lpeh_resto = [c for c in df_csv_limpio.columns if
#                        c.startswith('lpeh') and c != 'lpeh1' and c.replace('lpeh', '').isdigit()]
#
#     cond_lpeh1 = df_csv_limpio['lpeh1'].notna() & (df_csv_limpio['lpeh1'] != '')
#
#     if cols_lpeh_resto:
#         cond_resto = df_csv_limpio[cols_lpeh_resto].replace('', pd.NA).isna().all(axis=1)
#     else:
#         cond_resto = pd.Series(True, index=df_csv_limpio.index)
#
#     mascara_final = cond_lpeh1 & cond_resto # 1 binomio y el resto de binomios tienen valores nulos
#     conteo = mascara_final.value_counts()
#     print(
#         f"📊 Reporte 1-Binomio -> Seleccionados: {conteo.get(True, 0)} | Descartados: {conteo.get(False, 0)} | Total: {len(mascara_final)}")
#
#     # =========================================================================
#     # SE USA MÁS ADELANTE EN LA FUNCIÓN "seleccion_mas_detalle_multibinomio"
#     # =========================================================================
#     self.df_varios_binomios = df_csv_limpio[~mascara_final].copy()
#     path_varios_binomios = os.path.normpath(
#         os.path.join(self.folder_output, f'registros_varios_binomios_lpehx_{self.zona}.csv')
#     )
#     self.df_varios_binomios.to_csv(path_varios_binomios, index=False, sep=';', encoding='utf-8-sig')
#     print(
#         f"✅ CSV de registros con varios binomios de origen exportado en: {path_varios_binomios} | {len(self.df_varios_binomios)} registros "
#         f"de un total de {len(df_csv_limpio)} registros.")
#     # =========================================================================
#
#     self.df_1binomio = df_csv_limpio[mascara_final].copy()
#
#     path_output = os.path.join(self.folder_output, f'cruce_solo_1binomio_{self.zona}_art_y_cult.csv')
#     self.df_1binomio.to_csv(path_output, index=False, sep=';', encoding='utf-8-sig')
#     print(f'✅ Registros con 1 binomio exportados correctamente en: {path_output}')
#
# def seleccion_mas_detalle_1_binomio(self):
#     print('\nIniciando clasificación y exportación de registros por nivel de detalle...')
#
#     if self.df_1binomio is None or self.df_1binomio.empty:
#         print("⚠️ Aviso: No hay registros para analizar.")
#         return
#
#     # 1. Identificar si existen columnas LPEH adicionales (LPEH_2, LPEH_3, etc.)
#     lpeh_extras = [col for col in self.df_1binomio.columns if col.startswith('LPEH_') and col != 'LPEH_1']
#
#     # Función de limpieza para medir longitudes de forma justa
#     def limpiar_para_conteo(col):
#         return col.fillna('').astype(str).str.replace('.', '', regex=False).str.replace('ES', 'X', regex=False)
#
#     len_original = limpiar_para_conteo(self.df_1binomio['lpeh1']).str.len()
#     len_nuevo = limpiar_para_conteo(self.df_1binomio['LPEH_1']).str.len()
#
#     # 2. Detectar si alguna de las otras columnas LPEH_X tiene texto (2 o más binomios)
#     tiene_otros_lpeh = False
#     if lpeh_extras:
#         tiene_otros_lpeh = self.df_1binomio[lpeh_extras].fillna('').astype(str).apply(
#             lambda x: x.str.strip() != '').any(axis=1)
#
#     # Condición base: Solo existen datos en lpeh1 y LPEH_1 (las demás LPEH_X están vacías)
#     cond_solo_1_y_1 = ~tiene_otros_lpeh
#
#     # 3. Segmentación según tus nuevas directrices
#
#     # CSV 1: lpeh1 tiene MAYOR o IGUAL nivel de detalle que LPEH_1 (Casos a revisar)
#     cond_lpeh1_mas_o_igual = cond_solo_1_y_1 & (len_original >= len_nuevo)
#     df_lpeh1_mas = self.df_1binomio[cond_lpeh1_mas_o_igual].copy()
#
#     # CSV 2: LPEH_1 tiene MAYOR nivel de detalle que lpeh1 (Casos listos para volcar)
#     cond_LPEH1_mas_detalle = cond_solo_1_y_1 & (len_nuevo > len_original)
#     self.df_LPEH1_mas = self.df_1binomio[cond_LPEH1_mas_detalle].copy()
#
#     # CSV 3: El resto de los casos (Principalmente registros con lpeh1 y 2 o más LPEH_X)
#     cond_resto_casos = ~(cond_lpeh1_mas_o_igual | cond_LPEH1_mas_detalle)
#     df_resto_temporal = self.df_1binomio[cond_resto_casos].copy()
#
#     # CSV 4: Del resto de casos aislamos aquellos con "asigna_lpeh = 5"
#     cond_asigna_5 = pd.to_numeric(df_resto_temporal['asigna_lpeh1'], errors='coerce') == 5
#     df_resto_asigna_5 = df_resto_temporal[cond_asigna_5].copy()
#
#     # CSV 3 (El Resto Real): Nos quedamos con lo que NO tenía asigna_lpeh1 == 5
#     self.df_resto = df_resto_temporal[~cond_asigna_5].copy()
#
#     # 4. Definición de rutas con los nombres exactos solicitados
#     # A REVISAR:
#     #   * Registros lpeh1 > LPEH_1 (1:1)
#     #   * Registros lpeh1 y LPEH_1,2,3...X (1:X) CON "asigna = 5"
#     # SE VUELCAN:
#     #   * Registros lpeh1 < LPEH_1 (1:1)
#     #   * Registros lpeh1 y LPEH_1,2,3...X (1:X) SIN "asigna = 5"
#
#     path_lpeh1_mas = os.path.join(self.folder_output, f'revision_lpeh1_mas_detalle_LPEH1_{self.zona}.csv')
#     path_LPEH1_mas = os.path.join(self.folder_output, f'volcar_LPEH1_mas_detalle_lpeh1_{self.zona}.csv')
#     path_resto = os.path.join(self.folder_output, f'volcar_lpeh1_VARIOS_LPEH_X_NO_asigna_5_{self.zona}.csv')
#     path_resto_asigna_5 = os.path.join(self.folder_output, f'revision_lpeh1_varios_LPEH_X_asigna_5_{self.zona}.csv')
#
#     # 5. Exportación a CSV
#     df_lpeh1_mas.to_csv(path_lpeh1_mas, index=False, sep=';', encoding='utf-8-sig')
#     self.df_LPEH1_mas.to_csv(path_LPEH1_mas, index=False, sep=';', encoding='utf-8-sig')
#     self.df_resto.to_csv(path_resto, index=False, sep=';', encoding='utf-8-sig')
#     df_resto_asigna_5.to_csv(path_resto_asigna_5, index=False, sep=';', encoding='utf-8-sig')
#
#     # 6. Reporte por consola para control
#     print(f'✅ CSV 1 Guardado (Revisar: lpeh1 >= LPEH_1) -> {path_lpeh1_mas} | {len(df_lpeh1_mas)} reg.')
#     print(f'✅ CSV 2 Guardado (Volcar: LPEH_1 > lpeh1)  -> {path_LPEH1_mas} | {len(self.df_LPEH1_mas)} reg.')
#     print(f'✅ CSV 3 Guardado (Bloque Depuración: 2+ LPEH) -> {path_resto} | {len(self.df_resto)} reg.')
#     print \
#         (f'📂 CSV 4 Guardado (Filtro Varios LPEH con asigna 5) -> {path_resto_asigna_5} | {len(df_resto_asigna_5)} reg.')
#
#     print \
#         (f"\n📊 [RESUMEN ] Total procesados: {len(df_lpeh1_mas) + len(self.df_LPEH1_mas) + len(self.df_resto) + len(df_resto_asigna_5)} registros.")
#     # HASTA AQUI

# region MULTIBINOMIO (MÁS ADELANTE)
# def seleccion_mas_detalle_multibinomio(self):
#     print('\nIniciando clasificación de registros multibinómicos (2 o más binomios)...')
#
#     # 1. 🟢 Control de entrada optimizado: validamos la existencia de la tabla ya segmentada
#     if not hasattr(self, 'df_varios_binomios') or self.df_varios_binomios is None or self.df_varios_binomios.empty:
#         print("⚠️ Aviso: No existen registros con 2 o más binomios para analizar o falta ejecutar el paso previo.")
#         return
#
#     # 🟢 Clonamos y procesamos directamente el subset precalculado
#     df_multibinomio = self.df_varios_binomios.copy()
#
#     # ==========================================================================================
#     # Extraer registros con "5" en columnas asigna_lpehX antes de continuar
#     # ==========================================================================================
#     # Identificar dinámicamente las columnas asigna_lpeh1, asigna_lpeh2, etc.
#     cols_asigna = [c for c in df_multibinomio.columns if
#                    c.startswith('asigna_lpeh') and c.replace('asigna_lpeh', '').isdigit()]
#
#     if cols_asigna:
#         # Buscamos el carácter '5' en cualquiera de estas columnas (equivalente al HALLAR de Excel)
#         # Convertimos a string y rellenamos vacíos para evitar falsos positivos con 'nan'
#         filtro_contiene_5 = df_multibinomio[cols_asigna].fillna('').astype(str).apply(
#             lambda col: col.str.contains('5')
#         ).any(axis=1)
#
#         # Separamos los registros que cumplen la condición
#         df_asigna_con_5 = df_multibinomio[filtro_contiene_5].copy()
#
#         # Dejamos en el DataFrame principal SOLO los registros restantes (la mayoría)
#         df_multibinomio = df_multibinomio[~filtro_contiene_5].copy()
#
#         # Exportamos los registros extraídos con "5"
#         path_asigna_5 = os.path.normpath(
#             os.path.join(self.folder_output, f'revision_mas2binomios_asigna_lpeh_con_5_{self.zona}.csv'))
#         df_asigna_con_5.to_csv(path_asigna_5, index=False, sep=';', encoding='utf-8-sig')
#
#         print(
#             f'⚠️ CSV Especial Guardado (Contienen "5" en asigna_lpeh) -> {path_asigna_5} | {len(df_asigna_con_5)} registros '
#             f'de un total de {len(df_multibinomio)} registros. ')
#     else:
#         print("⚠️ Aviso: No se encontraron columnas que empiecen por 'asigna_lpehX'.")
#     # ==========================================================================================
#
#     # 3. Identificar dinámicamente todas las columnas de conteo lpeh y LPEH_
#     cols_lpeh_origen = [c for c in df_multibinomio.columns if
#                         c.startswith('lpeh') and c.replace('lpeh', '').isdigit()]
#     cols_LPEH_destino = [c for c in df_multibinomio.columns if
#                          c.startswith('LPEH_') and c.replace('LPEH_', '').isdigit()]
#
#     # 4. Contar fila por fila cuántas columnas tienen valores reales
#     conteo_origen = df_multibinomio[cols_lpeh_origen].replace('', pd.NA).notna().sum(axis=1)
#     conteo_destino = df_multibinomio[cols_LPEH_destino].replace('', pd.NA).notna().sum(axis=1)
#
#     # 5. Calcular la diferencia (Destino - Origen)
#     df_multibinomio['diferencia_binomios'] = conteo_destino - conteo_origen
#
#     # 6. Segmentar según la diferencia
#     df_mas_detalle = df_multibinomio[df_multibinomio['diferencia_binomios'] > 0].copy()
#     df_igual_detalle = df_multibinomio[df_multibinomio['diferencia_binomios'] == 0].copy()
#     df_menos_detalle = df_multibinomio[df_multibinomio['diferencia_binomios'] < 0].copy()
#
#     # 7. Definición de rutas de salida
#     path_mas = os.path.normpath(
#         os.path.join(self.folder_output, f'revision_mas2binomios_mas_detalle_LPEH_X_{self.zona}.csv'))
#     path_igual = os.path.normpath(
#         os.path.join(self.folder_output, f'revisar_mas2binomios_igual_nivel_detalle_{self.zona}.csv'))
#     path_menos = os.path.normpath(
#         os.path.join(self.folder_output, f'descartes_mas2binomios_menos_detalle_LPEH_X_{self.zona}.csv'))
#
#     # 8. Exportación a CSV
#     df_mas_detalle.to_csv(path_mas, index=False, sep=';', encoding='utf-8-sig')
#     df_igual_detalle.to_csv(path_igual, index=False, sep=';', encoding='utf-8-sig')
#     df_menos_detalle.to_csv(path_menos, index=False, sep=';', encoding='utf-8-sig')
#
#     # 9. Reporte por consola
#     print(f'✅ CSV 1 Guardado (Diferencia > 0: Más detalle)   -> {path_mas} | {len(df_mas_detalle)} reg.')
#     print(f'✅ CSV 2 Guardado (Diferencia = 0: Igual detalle) -> {path_igual} | {len(df_igual_detalle)} reg.')
#     print(f'❌ CSV 3 Guardado (Diferencia < 0: Menos detalle) -> {path_menos} | {len(df_menos_detalle)} reg.')
#     print(f'📊 [RESUMEN MULTIBINOMIO] Total procesados: {len(df_multibinomio)} registros.')
# endregion  ()