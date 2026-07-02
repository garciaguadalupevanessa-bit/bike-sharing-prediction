import pandas as pd
import numpy as np
from pathlib import Path

# CONFIGURACIÓN
dataset_path = Path("data/processed/station_status_history_2022_modeling_base.csv")
chunk_size = 500_000  # filas por chunk

print("=" * 60)
print("AUDITORÍA DE DATASET PROCESADO")
print("=" * 60)

# 1. INFORMACIÓN GENERAL
print("\n--- 1. INFORMACIÓN GENERAL ---")
file_size_mb = dataset_path.stat().st_size / (1024 * 1024)
print(f"Archivo: {dataset_path}")
print(f"Tamaño: {file_size_mb:.2f} MB")

# Leer solo header
header_df = pd.read_csv(dataset_path, nrows=0)
columns = header_df.columns.tolist()
print(f"Columnas ({len(columns)}): {columns}")

# 2. ANÁLISIS POR CHUNKS (nulos, tipos, memoria)
print("\n--- 2. ANÁLISIS DE NULOS POR CHUNKS ---")
null_counts = {col: 0 for col in columns}
total_rows = 0
dtype_samples = {}

for i, chunk in enumerate(pd.read_csv(dataset_path, chunksize=chunk_size)):
    total_rows += len(chunk)
    for col in columns:
        null_counts[col] += chunk[col].isna().sum()
    # Guardar tipos del primer chunk como referencia
    if i == 0:
        dtype_samples = chunk.dtypes.to_dict()
    print(f"  Chunk {i+1}: {len(chunk):,} filas (acumulado: {total_rows:,})")

print(f"\nTotal filas: {total_rows:,}")

# 3. PORCENTAJE DE NULOS POR COLUMNA
print("\n--- 3. PORCENTAJE DE NULOS POR COLUMNA ---")
null_report = []
for col in columns:
    pct = (null_counts[col] / total_rows) * 100
    null_report.append({
        "columna": col,
        "nulos": null_counts[col],
        "pct_nulos": round(pct, 2),
        "dtype": str(dtype_samples.get(col, "unknown"))
    })

null_report_df = pd.DataFrame(null_report).sort_values("pct_nulos", ascending=False)
print(null_report_df.to_string(index=False))

# 4. ANÁLISIS DE FECHAS
print("\n--- 4. ANÁLISIS DE FECHAS ---")
# Leer solo columnas de fecha para no cargar todo
date_sample = pd.read_csv(dataset_path, usecols=["snapshot_datetime"], parse_dates=["snapshot_datetime"])
print(f"snapshot_datetime nulos: {date_sample['snapshot_datetime'].isna().sum():,}")
print(f"Fecha mínima: {date_sample['snapshot_datetime'].min()}")
print(f"Fecha máxima: {date_sample['snapshot_datetime'].max()}")
print(f"Registros fuera de 2022: {(date_sample['snapshot_datetime'].dt.year != 2022).sum():,}")

# 5. ANÁLISIS DE VARIABLES CLAVE (sample)
print("\n--- 5. ANÁLISIS DE VARIABLES CLAVE ---")
sample_df = pd.read_csv(dataset_path, nrows=100_000)
numeric_cols = ["station_capacity", "num_bikes_available", "num_docks_available", "occupation_ratio"]
for col in numeric_cols:
    if col in sample_df.columns:
        print(f"\n{col}:")
        print(f"  nulos: {sample_df[col].isna().sum():,} ({sample_df[col].isna().mean()*100:.2f}%)")
        print(f"  min: {sample_df[col].min()}")
        print(f"  max: {sample_df[col].max()}")
        print(f"  mean: {sample_df[col].mean():.3f}")
        if col == "station_capacity":
            print(f"  capacidad == 0: {(sample_df[col] == 0).sum():,}")

# 6. ANÁLISIS DE DUPLICADOS (sample)
print("\n--- 6. DUPLICADOS (sample de 100k) ---")
dupes = sample_df.duplicated().sum()
print(f"Filas duplicadas en sample: {dupes:,}")

# 7. ANÁLISIS DE ESTACIONES
print("\n--- 7. ESTACIONES ---")
if "station_id_historical" in sample_df.columns:
    print(f"Estaciones únicas en sample: {sample_df['station_id_historical'].nunique()}")
    print(f"Estaciones con ID nulo: {sample_df['station_id_historical'].isna().sum():,}")

# 8. ANÁLISIS DE CLIMA
print("\n--- 8. CLIMA ---")
weather_cols = [c for c in columns if c.startswith("weather_")]
if weather_cols:
    for col in weather_cols:
        pct = null_report_df[null_report_df["columna"] == col]["pct_nulos"].values[0]
        print(f"  {col}: {pct:.2f}% nulos")
else:
    print("  No hay columnas weather_*")

# 9. COLUMNAS PROBLEMÁTICAS IDENTIFICADAS
print("\n--- 9. COLUMNAS PROBLEMÁTICAS SUGERIDAS ---")
problematic = [
    "source_month", "station_number", "station_name", "station_address",
    "station_light_status", "reservations_count", "is_active", "is_not_available"
]
for col in problematic:
    if col in columns:
        pct = null_report_df[null_report_df["columna"] == col]["pct_nulos"].values[0]
        print(f"  {col}: {pct:.2f}% nulos - considerar eliminar para modelado")

print("\n" + "=" * 60)
print("AUDITORÍA COMPLETADA")
print("=" * 60)