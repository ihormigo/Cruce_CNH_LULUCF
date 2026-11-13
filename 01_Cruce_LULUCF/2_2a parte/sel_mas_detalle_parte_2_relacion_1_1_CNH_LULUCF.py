import pandas as pd
import geopandas as gpd
import arcpy
import os
import sys
import time
from datetime import datetime

output_folder = r"C:\Users\ihormigo\Desktop\resultados_cruce\3 Resultados Atlas y 2a parte metod\2 Resultados a procesar\2a parte metodologia (binomios 1_1)\PB mejora detalle 1_1"
input_table = r"C:\Users\ihormigo\Desktop\resultados_cruce\3 Resultados Atlas y 2a parte metod\2 Resultados a procesar\2a parte metodologia (binomios 1_1)\0 Datos brutos de las revisiones\PB_caso3_no_muestreado_2a_parte.xlsx"

def seleccion_1binomio_multibinomio(self):
    print('\nIniciando selección de los registros con 1 binomio...')

    if self.csv_limpio is None:
        print("❌ Error: No hay datos en memoria. Asegúrate de que el Join se ha ejecutado.")
        return

    df_csv_limpio = self.csv_limpio.copy()

    cols_lpeh_resto = [c for c in df_csv_limpio.columns if
                       c.startswith('lpeh') and c != 'lpeh1' and c.replace('lpeh', '').isdigit()]

    cond_lpeh1 = df_csv_limpio['lpeh1'].notna() & (df_csv_limpio['lpeh1'] != '')

    if cols_lpeh_resto:
        cond_resto = df_csv_limpio[cols_lpeh_resto].replace('', pd.NA).isna().all(axis=1)
    else:
        cond_resto = pd.Series(True, index=df_csv_limpio.index)

    mascara_final = cond_lpeh1 & cond_resto # 1 binomio y el resto de binomios tienen valores nulos
    conteo = mascara_final.value_counts()
    print(
        f"📊 Reporte 1-Binomio -> Seleccionados: {conteo.get(True, 0)} | Descartados: {conteo.get(False, 0)} | Total: {len(mascara_final)}")

    # =========================================================================
    # SE USA MÁS ADELANTE EN LA FUNCIÓN "seleccion_mas_detalle_multibinomio"
    # =========================================================================
    self.df_varios_binomios = df_csv_limpio[~mascara_final].copy()
    path_varios_binomios = os.path.normpath(
        os.path.join(self.folder_output, f'registros_varios_binomios_lpehx_{self.zona}.csv')
    )
    self.df_varios_binomios.to_csv(path_varios_binomios, index=False, sep=';', encoding='utf-8-sig')
    print(
        f"✅ CSV de registros con varios binomios de origen exportado en: {path_varios_binomios} | {len(self.df_varios_binomios)} registros "
        f"de un total de {len(df_csv_limpio)} registros.")
    # =========================================================================

    self.df_1binomio = df_csv_limpio[mascara_final].copy()

    path_output = os.path.join(self.folder_output, f'cruce_solo_1binomio_{self.zona}_art_y_cult.csv')
    self.df_1binomio.to_csv(path_output, index=False, sep=';', encoding='utf-8-sig')
    print(f'✅ Registros con 1 binomio exportados correctamente en: {path_output}')

def seleccion_mas_detalle_1_binomio(self):
    print('\nIniciando clasificación y exportación de registros por nivel de detalle...')

    if self.df_1binomio is None or self.df_1binomio.empty:
        print("⚠️ Aviso: No hay registros para analizar.")
        return

    # 1. Identificar si existen columnas LPEH adicionales (LPEH_2, LPEH_3, etc.)
    lpeh_extras = [col for col in self.df_1binomio.columns if col.startswith('LPEH_') and col != 'LPEH_1']

    # Función de limpieza para medir longitudes de forma justa
    def limpiar_para_conteo(col):
        return col.fillna('').astype(str).str.replace('.', '', regex=False).str.replace('ES', 'X', regex=False)

    len_original = limpiar_para_conteo(self.df_1binomio['lpeh1']).str.len()
    len_nuevo = limpiar_para_conteo(self.df_1binomio['LPEH_1']).str.len()

    # 2. Detectar si alguna de las otras columnas LPEH_X tiene texto (2 o más binomios)
    tiene_otros_lpeh = False
    if lpeh_extras:
        tiene_otros_lpeh = self.df_1binomio[lpeh_extras].fillna('').astype(str).apply(
            lambda x: x.str.strip() != '').any(axis=1)

    # Condición base: Solo existen datos en lpeh1 y LPEH_1 (las demás LPEH_X están vacías)
    cond_solo_1_y_1 = ~tiene_otros_lpeh

    # 3. Segmentación según tus nuevas directrices

    # CSV 1: lpeh1 tiene MAYOR o IGUAL nivel de detalle que LPEH_1 (Casos a revisar)
    cond_lpeh1_mas_o_igual = cond_solo_1_y_1 & (len_original >= len_nuevo)
    df_lpeh1_mas = self.df_1binomio[cond_lpeh1_mas_o_igual].copy()

    # CSV 2: LPEH_1 tiene MAYOR nivel de detalle que lpeh1 (Casos listos para volcar)
    cond_LPEH1_mas_detalle = cond_solo_1_y_1 & (len_nuevo > len_original)
    self.df_LPEH1_mas = self.df_1binomio[cond_LPEH1_mas_detalle].copy()

    # CSV 3: El resto de los casos (Principalmente registros con lpeh1 y 2 o más LPEH_X)
    cond_resto_casos = ~(cond_lpeh1_mas_o_igual | cond_LPEH1_mas_detalle)
    df_resto_temporal = self.df_1binomio[cond_resto_casos].copy()

    # CSV 4: Del resto de casos aislamos aquellos con "asigna_lpeh = 5"
    cond_asigna_5 = pd.to_numeric(df_resto_temporal['asigna_lpeh1'], errors='coerce') == 5
    df_resto_asigna_5 = df_resto_temporal[cond_asigna_5].copy()

    # CSV 3 (El Resto Real): Nos quedamos con lo que NO tenía asigna_lpeh1 == 5
    self.df_resto = df_resto_temporal[~cond_asigna_5].copy()

    # 4. Definición de rutas con los nombres exactos solicitados
    # A REVISAR:
    #   * Registros lpeh1 > LPEH_1 (1:1)
    #   * Registros lpeh1 y LPEH_1,2,3...X (1:X) CON "asigna = 5"
    # SE VUELCAN:
    #   * Registros lpeh1 < LPEH_1 (1:1)
    #   * Registros lpeh1 y LPEH_1,2,3...X (1:X) SIN "asigna = 5"

    path_lpeh1_mas = os.path.join(self.folder_output, f'revision_lpeh1_mas_detalle_LPEH1_{self.zona}.csv')
    path_LPEH1_mas = os.path.join(self.folder_output, f'volcar_LPEH1_mas_detalle_lpeh1_{self.zona}.csv')
    path_resto = os.path.join(self.folder_output, f'volcar_lpeh1_VARIOS_LPEH_X_NO_asigna_5_{self.zona}.csv')
    path_resto_asigna_5 = os.path.join(self.folder_output, f'revision_lpeh1_varios_LPEH_X_asigna_5_{self.zona}.csv')

    # 5. Exportación a CSV
    df_lpeh1_mas.to_csv(path_lpeh1_mas, index=False, sep=';', encoding='utf-8-sig')
    self.df_LPEH1_mas.to_csv(path_LPEH1_mas, index=False, sep=';', encoding='utf-8-sig')
    self.df_resto.to_csv(path_resto, index=False, sep=';', encoding='utf-8-sig')
    df_resto_asigna_5.to_csv(path_resto_asigna_5, index=False, sep=';', encoding='utf-8-sig')

    # 6. Reporte por consola para control
    print(f'✅ CSV 1 Guardado (Revisar: lpeh1 >= LPEH_1) -> {path_lpeh1_mas} | {len(df_lpeh1_mas)} reg.')
    print(f'✅ CSV 2 Guardado (Volcar: LPEH_1 > lpeh1)  -> {path_LPEH1_mas} | {len(self.df_LPEH1_mas)} reg.')
    print(f'✅ CSV 3 Guardado (Bloque Depuración: 2+ LPEH) -> {path_resto} | {len(self.df_resto)} reg.')
    print \
        (f'📂 CSV 4 Guardado (Filtro Varios LPEH con asigna 5) -> {path_resto_asigna_5} | {len(df_resto_asigna_5)} reg.')

    print \
        (f"\n📊 [RESUMEN ] Total procesados: {len(df_lpeh1_mas) + len(self.df_LPEH1_mas) + len(self.df_resto) + len(df_resto_asigna_5)} registros.")
    # HASTA AQUI

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