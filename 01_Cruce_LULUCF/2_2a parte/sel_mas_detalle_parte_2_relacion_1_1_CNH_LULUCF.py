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
    76: [('V', 80), ('T',20)], # Mosaico de cultivo con arbolado (FccArb <20%)
    77: [('V', 50), ('R', 25), ('S', 25)],
    8: [('J', 100)],
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


class metodologia_2a_parte:
    def __init__(self, df=None):
        """
        Inicializa la clase con el DataFrame de trabajo (self.df).
        """
        self.df = df

    # =========================================================================
    # FUNCIÓN 1: Procesamiento individual de una fila
    # =========================================================================
    def procesar_fila_pasarela(self, row, pasarela_dict):
        """
        Procesa una fila individual:
        1. Identifica coberturas 'V' y 'J' directas y acumula el % restante (No-V/J).
        2. Transforma el % No-V/J aplicando la pasarela según la columna 'tipestr'.
        3. Fusiona y suma porcentajes si coinciden códigos tras la pasarela.
        """
        conteo_lpeh = {}
        total_no_v_j = 0.0

        for i in range(1, 11):
            col_lpeh = f"LPEH_{i}"
            col_per = f"PER_{i}"

            val_lpeh = row.get(col_lpeh)
            val_per = row.get(col_per)

            if pd.isna(val_lpeh) or pd.isna(val_per):
                continue

            val_lpeh = str(val_lpeh).strip()
            try:
                val_per = float(val_per)
            except (ValueError, TypeError):
                continue

            if val_per <= 0 or val_lpeh == "":
                continue

            if "V" in val_lpeh or "J" in val_lpeh:
                conteo_lpeh[val_lpeh] = val_per
            else:
                total_no_v_j += val_per

        if "id_tipestr" not in row:
            sys.exit("El campo 'id_tipestr' no existe.")

        if total_no_v_j > 0:
            tipestr_val = row.get("id_tipestr")

            if pd.notna(tipestr_val):
                try:
                    tipestr_key = int(float(tipestr_val))
                except (ValueError, TypeError):
                    tipestr_key = tipestr_val

                if tipestr_key in pasarela_dict:
                    reglas_reparto = pasarela_dict[tipestr_key]

                    for cod_destino, proporcion in reglas_reparto:
                        porcentaje_ajustado = total_no_v_j * (proporcion / 100)
                        conteo_lpeh[cod_destino] = conteo_lpeh.get(cod_destino, 0.0) + porcentaje_ajustado

        return conteo_lpeh

    # =========================================================================
    # FUNCIÓN 2: Aplicación sobre DataFrame
    # =========================================================================
    def aplicar_pasarela_df(self, pasarela_dict):
        """
        Aplica la pasarela a todos los registros del DataFrame self.df.
        """
        print("Procesando coberturas y aplicando pasarela a todos los registros...")
        listas_lpeh = []
        listas_per = []

        for _, row in self.df.iterrows():
            res_dict = self.procesar_fila_pasarela(row, pasarela_dict)

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
            self.df[f"LPEH_{i}"] = [fila[i - 1] for fila in listas_lpeh]
            self.df[f"PER_{i}"] = [fila[i - 1] for fila in listas_per]

        return self.df

    # =========================================================================
    # FUNCIÓN 3: Eliminación de filas donde Origen == Destino
    # =========================================================================
    def eliminar_duplicados_binomios(self, zona, output_folder):
        """
        Compara para cada fila si origen y destino son exactamente iguales.
        """
        print('\nIniciando comprobación de duplicados (Origen == Destino en la misma fila)...')

        total_inicial = len(self.df)
        indices_duplicados = []

        for idx, row in self.df.iterrows():
            es_duplicado = True

            for i in range(1, 11):
                col_lpeh_orig = f"lpeh{i}"
                col_p_orig = f"p{i}" if f"p{i}" in row else f"per{i}"
                col_lpeh_dest = f"LPEH_{i}"
                col_p_dest = f"PER_{i}"

                val_lpeh_o = str(row.get(col_lpeh_orig, '')).strip() if pd.notna(row.get(col_lpeh_orig)) else ''
                val_lpeh_d = str(row.get(col_lpeh_dest, '')).strip() if pd.notna(row.get(col_lpeh_dest)) else ''

                try:
                    val_p_o = int(round(float(row.get(col_p_orig, 0)))) if pd.notna(row.get(col_p_orig)) else 0
                except (ValueError, TypeError):
                    val_p_o = 0

                try:
                    val_p_d = int(round(float(row.get(col_p_dest, 0)))) if pd.notna(row.get(col_p_dest)) else 0
                except (ValueError, TypeError):
                    val_p_d = 0

                if val_lpeh_o != val_lpeh_d or val_p_o != val_p_d:
                    es_duplicado = False
                    break

            if es_duplicado:
                indices_duplicados.append(idx)

        df_duplicados = self.df.loc[indices_duplicados].copy()

        if not df_duplicados.empty:
            path_duplicados = os.path.join(output_folder, f'REVISION_duplicados_lpehx_LPEH_X_{zona}.csv')
            df_duplicados.to_csv(path_duplicados, index=False, sep=';', encoding='utf-8-sig')
            print(f"  -> 📄 Archivo de revisión guardado en:\n     {path_duplicados}")
        else:
            print("  -> 📄 No se encontraron filas con Origen == Destino. No se genera archivo de revisión.")

        self.df = self.df.drop(index=indices_duplicados).copy()
        total_final = len(self.df)

        print(f'  -> Registros antes de limpiar: {total_inicial}')
        print(f'  -> Registros después de limpiar: {total_final}')
        print(f'  -> Filas eliminadas (lpehx == LPEH_X): {total_inicial - total_final}')

        return self.df

    # =========================================================================
    # FUNCIÓN 4: Separación de casos por número de columnas lpehx-LPEH_X
    # =========================================================================
    def separar_registros_por_binomios(self, zona, output_folder):
        """
        Separa en 3 CSVs (1:1, 1:N, N:M) y actualiza self.df únicamente con los registros 1:1.
        """
        print('\nIniciando separación de los registros procesados en 3 CSVs...')

        cols_lpeh_resto = [c for c in self.df.columns if c.startswith('lpeh') and c != 'lpeh1']
        cond_lpeh1_notna = self.df['lpeh1'].notna() & (self.df['lpeh1'].astype(str).str.strip() != '')

        if cols_lpeh_resto:
            cond_resto_lpeh_nulo = self.df[cols_lpeh_resto].replace(r'^\s*$', pd.NA, regex=True).isna().all(axis=1)
        else:
            cond_resto_lpeh_nulo = pd.Series(True, index=self.df.index)

        mascara_1_lpeh = cond_lpeh1_notna & cond_resto_lpeh_nulo

        df_1_lpeh = self.df[mascara_1_lpeh].copy()
        df_varios_lpeh = self.df[~mascara_1_lpeh].copy()

        cols_LPEH_resto = [c for c in df_1_lpeh.columns if c.startswith('LPEH_') and c != 'LPEH_1']

        if cols_LPEH_resto:
            cond_resto_LPEH_nulo = df_1_lpeh[cols_LPEH_resto].replace(r'^\s*$', pd.NA, regex=True).isna().all(axis=1)
        else:
            cond_resto_LPEH_nulo = pd.Series(True, index=df_1_lpeh.index)

        df_solo_lpeh1_LPEH_1 = df_1_lpeh[cond_resto_LPEH_nulo].copy()
        df_solo_lpeh1_varios_LPEH = df_1_lpeh[~cond_resto_LPEH_nulo].copy()

        path_caso1 = os.path.join(output_folder, f'registros_lpeh1_LPEH_1_{zona}.csv')
        path_caso2 = os.path.join(output_folder, f'registros_lpeh1_varios_LPEH_X_{zona}.csv')
        path_caso3 = os.path.join(output_folder, f'registros_varios_binomios_lpehx_{zona}.csv')

        df_solo_lpeh1_LPEH_1.to_csv(path_caso1, index=False, sep=';', encoding='utf-8-sig')
        df_solo_lpeh1_varios_LPEH.to_csv(path_caso2, index=False, sep=';', encoding='utf-8-sig')
        df_varios_lpeh.to_csv(path_caso3, index=False, sep=';', encoding='utf-8-sig')

        print(f'  -> CSV 1 (1 lpeh origen -> 1 LPEH destino) guardado: {len(df_solo_lpeh1_LPEH_1)} registros.')
        print(f'  -> CSV 2 (1 lpeh origen -> varios LPEH destino) guardado: {len(df_solo_lpeh1_varios_LPEH)} registros.')
        print(f'  -> CSV 3 (Varios lpeh origen) guardado: {len(df_varios_lpeh)} registros.')

        total_inicial = len(self.df)
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

        # Almacena únicamente el DataFrame 1:1 en self.df para la evaluación de detalle posterior
        self.df = df_solo_lpeh1_LPEH_1
        return self.df

# =========================================================================
    # FUNCIÓN 5: Comparación de detalle en casos 1:1 (lpeh1 vs LPEH_1)
    # =========================================================================
    def evaluar_mejora_detalle_1_1(self, zona, output_folder):
        """
        Filtra y separa los registros 1:1 en dos CSVs:
        1. Mejora de detalle: LPEH_1 ofrece mayor longitud que lpeh1.
        2. Sin mejora (revisión): LPEH_1 tiene igual o menor longitud que lpeh1.
        Limpia puntos y cuenta 'ES' como un único carácter antes de medir.
        """
        print('Iniciando evaluación de mejora de detalle en registros 1:1 (lpeh1 vs LPEH_1)...')

        if self.df is None or self.df.empty:
            print("  -> ⚠️ No hay registros 1:1 para evaluar.")
            return None

        def _longitud_codigo(val):
            if pd.isna(val):
                return 0
            # 1. Quitar puntos y espacios
            s = str(val).strip().replace('.', '')
            # 2. Contar 'ES' como 1 solo carácter
            s = s.replace('ES', 'X')
            return len(s)

        len_origen = self.df['lpeh1'].apply(_longitud_codigo)
        len_destino = self.df['LPEH_1'].apply(_longitud_codigo)

        # Máscaras de filtrado
        mascara_mejora = len_destino > len_origen

        df_mejora = self.df[mascara_mejora].copy()
        df_sin_mejora = self.df[~mascara_mejora].copy()

        # Bifurcación: Mismo prefijo vs Distinto prefijo
        def _es_mismo_prefijo(row):
            orig = str(row['lpeh1']).strip().replace('.', '')
            dest = str(row['LPEH_1']).strip().replace('.', '')
            return orig in dest

        if not df_mejora.empty:
            mascara_mismo_prefijo = df_mejora.apply(_es_mismo_prefijo, axis=1)
            df_mismo_prefijo = df_mejora[mascara_mismo_prefijo].copy()
            df_distinto_prefijo = df_mejora[~mascara_mismo_prefijo].copy()
        else:
            df_mismo_prefijo = pd.DataFrame(columns=self.df.columns)
            df_distinto_prefijo = pd.DataFrame(columns=self.df.columns)

        # Guardar CSVs con mejora
        path_mejora_mismo = os.path.join(output_folder, f'mejora_detalle_LPEH_1_lpeh1_{zona}_mismo_prefijo.csv')
        df_mismo_prefijo.to_csv(path_mejora_mismo, index=False, sep=';', encoding='utf-8-sig')

        path_mejora_distinto = os.path.join(output_folder,
                                            f'revision_mejora_detalle_LPEH_1_lpeh1_{zona}_distinto_prefijo.csv')
        df_distinto_prefijo.to_csv(path_mejora_distinto, index=False, sep=';', encoding='utf-8-sig')

        # Guardar CSVs sin mejora
        path_sin_mejora = os.path.join(output_folder, f'revision_detalle_lpeh1_LPEH_1_{zona}.csv')
        df_sin_mejora.to_csv(path_sin_mejora, index=False, sep=';', encoding='utf-8-sig')

        print(f'  -> Registros 1:1 evaluados: {len(self.df)}')
        print(f'  -> Registros con mejora (LPEH_1 > lpeh1): {len(df_mejora)}')
        print(f'     ├── Mismo prefijo (lpeh1 contenido en LPEH_1): {len(df_mismo_prefijo)}')
        print(f'     │   📄 Archivo guardado en: {path_mejora_mismo}')
        print(f'     └── Distinto prefijo: {len(df_distinto_prefijo)}')
        print(f'         📄 Archivo guardado en: {path_mejora_distinto}')
        print(f'  -> Registros sin mejora (LPEH_1 <= lpeh1): {len(df_sin_mejora)}')
        print(f'  -> 📄 Archivo guardado en: {path_sin_mejora}\n')

        return df_mejora

# =============================================================================
# BLOQUE PRINCIPAL DE EJECUCIÓN
# =============================================================================
if __name__ == "__main__":
    output_folder = r"C:\Users\ihormigo\Desktop\resultados_cruce\3 Resultados Atlas y 2a parte metod\2 Resultados a procesar\2a parte metodologia (binomios 1_1)\2a parte metodologia\PB mejora detalle 1_1"
    archivo_entrada = r"C:\Users\ihormigo\Desktop\resultados_cruce\3 Resultados Atlas y 2a parte metod\2 Resultados a procesar\2a parte metodologia (binomios 1_1)\Datos 1a parte\PB_caso3_no_muestreado_2a_parte.xlsx"

    nombre_archivo = os.path.basename(archivo_entrada)

    if "PB" in nombre_archivo:
        zona_codigo = "PB"
    elif "C" in nombre_archivo:
        zona_codigo = "C"
    else:
        sys.exit("❌ Error: No se encontró ni 'PB' ni 'C' en el nombre del archivo de entrada.")

    ZONA = f"ZONA_{zona_codigo}"

    archivo_salida_final = os.path.normpath(
        os.path.join(output_folder, f"{zona_codigo}_caso3_no_muestreado_2a_parte_MAPEADO_tipestr.xlsx")
    )

    print(f"Cargando archivo: {nombre_archivo}...")
    print(f"Zona: {ZONA}")
    df_origen = pd.read_excel(archivo_entrada)

    # Instanciación de la clase
    procesador = metodologia_2a_parte(df_origen)

    # Flujo de trabajo secuencial
    procesador.aplicar_pasarela_df(PASARELA_TIPESTR)
    procesador.eliminar_duplicados_binomios(ZONA, output_folder)

    # Guardar Excel procesado completo
    print(f"\nGuardando Excel resultado final en: {archivo_salida_final}...")
    procesador.df.to_excel(archivo_salida_final, index=False)
    print("¡Proceso de guardado finalizado con éxito!")

    # Separar en CSVs (actualiza self.df al grupo 1:1)
    procesador.separar_registros_por_binomios(ZONA, output_folder)

    # Evaluar mejora de detalle sobre los casos 1:1
    procesador.evaluar_mejora_detalle_1_1(ZONA, output_folder)

    print("¡Flujo completo finalizado!")