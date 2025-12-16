"""
AALabelPP - Descarga de Normativas Oficiales
Script para descargar PDFs de normativas de los 4 países andinos

Fecha: 2025-12-14
Versión: 1.0
"""

import os
import hashlib
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import json
from tqdm import tqdm

# Configuración de directorios
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "normativas"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# NORMATIVAS OFICIALES - URLs y Metadatos
# ============================================================================

NORMATIVAS = {
    "colombia": {
        "pais": "Colombia",
        "codigo_iso": "CO",
        "autoridad": "INVIMA",
        "documentos": [
            {
                "tipo": "Decreto",
                "numero": "677/1995",
                "titulo": "Régimen de Registros y Licencias, Control de Calidad y Vigilancia Sanitaria",
                "fecha_publicacion": "1995-04-26",
                "url": "https://www.invima.gov.co/documents/20143/442916/Decreto-677-de-1995.pdf",
                "archivo_local": "colombia_decreto_677_1995.pdf",
                "articulos_relevantes": ["72", "73", "74"],
                "descripcion": "Reglamenta el etiquetado de medicamentos en Colombia"
            }
        ]
    },
    
    "ecuador": {
        "pais": "Ecuador",
        "codigo_iso": "EC",
        "autoridad": "ARCSA",
        "documentos": [
            {
                "tipo": "Acuerdo Ministerial",
                "numero": "586",
                "titulo": "Reglamento sustitutivo para el registro sanitario de medicamentos",
                "fecha_publicacion": "2016-12-09",
                "url": "https://www.controlsanitario.gob.ec/wp-content/uploads/downloads/2017/03/AM_586_2016_RSM_ARCSA.pdf",
                "archivo_local": "ecuador_am_586_2016.pdf",
                "descripcion": "Normativa sobre registro sanitario y etiquetado en Ecuador"
            }
        ]
    },
    
    "peru": {
        "pais": "Perú",
        "codigo_iso": "PE",
        "autoridad": "DIGEMID",
        "documentos": [
            {
                "tipo": "Decreto Supremo",
                "numero": "016-2011-SA",
                "titulo": "Reglamento para el Registro, Control y Vigilancia Sanitaria",
                "fecha_publicacion": "2011-07-27",
                "url": "http://www.digemid.minsa.gob.pe/UpLoad/UpLoaded/PDF/DS016-2011-SA.pdf",
                "archivo_local": "peru_ds_016_2011_sa.pdf",
                "descripcion": "Marco regulatorio de productos farmacéuticos en Perú"
            }
        ]
    },
    
    "bolivia": {
        "pais": "Bolivia",
        "codigo_iso": "BO",
        "autoridad": "AGEMED",
        "documentos": [
            {
                "tipo": "Manual",
                "numero": "AGEMED-2005",
                "titulo": "Manual para Registro Sanitario de Productos Farmacéuticos",
                "fecha_publicacion": "2005-01-01",
                "url": "https://www.agemed.gob.bo/documentos/manual_registro_sanitario.pdf",
                "archivo_local": "bolivia_manual_registro_2005.pdf",
                "descripcion": "Manual de procedimientos para registro sanitario en Bolivia",
                "nota": "URL genérica - verificar disponibilidad"
            }
        ]
    }
}


# ============================================================================
# FUNCIONES DE DESCARGA
# ============================================================================

def calcular_hash_archivo(filepath: Path) -> str:
    """Calcular SHA-256 de un archivo"""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def descargar_pdf(url: str, destino: Path, timeout: int = 30) -> bool:
    """Descargar PDF desde URL con barra de progreso"""
    try:
        print(f"\n📥 Descargando: {url}")
        
        # Headers para simular navegador
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=timeout, stream=True)
        response.raise_for_status()
        
        # Obtener tamaño total
        total_size = int(response.headers.get('content-length', 0))
        
        # Descargar con barra de progreso
        with open(destino, 'wb') as f, tqdm(
            total=total_size,
            unit='B',
            unit_scale=True,
            desc=destino.name
        ) as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))
        
        print(f"✓ Descargado: {destino.name}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error descargando {url}: {str(e)}")
        return False
    except Exception as e:
        print(f"✗ Error inesperado: {str(e)}")
        return False


def crear_estructura_directorios():
    """Crear estructura de directorios para normativas"""
    for pais in NORMATIVAS.keys():
        pais_dir = DATA_DIR / pais
        pais_dir.mkdir(exist_ok=True)
        print(f"✓ Directorio creado: {pais_dir}")


def descargar_todas_normativas(force: bool = False) -> Dict[str, Dict]:
    """Descargar todas las normativas configuradas
    
    Args:
        force: Si True, descarga incluso si el archivo ya existe
        
    Returns:
        Diccionario con resultados de descarga
    """
    resultados = {
        "exitosas": [],
        "fallidas": [],
        "omitidas": [],
        "metadatos": {}
    }
    
    print("="*80)
    print("DESCARGA DE NORMATIVAS OFICIALES - AALabelPP")
    print("="*80)
    
    crear_estructura_directorios()
    
    for pais_key, pais_data in NORMATIVAS.items():
        print(f"\n{'='*80}")
        print(f"PAÍS: {pais_data['pais']} ({pais_data['autoridad']})")
        print(f"{'='*80}")
        
        pais_dir = DATA_DIR / pais_key
        
        for doc in pais_data["documentos"]:
            archivo_destino = pais_dir / doc["archivo_local"]
            
            # Verificar si ya existe
            if archivo_destino.exists() and not force:
                print(f"\n⏭  Ya existe: {doc['archivo_local']}")
                resultados["omitidas"].append({
                    "pais": pais_data["pais"],
                    "documento": doc["numero"],
                    "archivo": str(archivo_destino)
                })
                continue
            
            # Descargar
            exito = descargar_pdf(doc["url"], archivo_destino)
            
            if exito:
                # Calcular hash
                file_hash = calcular_hash_archivo(archivo_destino)
                file_size = archivo_destino.stat().st_size
                
                metadata = {
                    "pais": pais_data["pais"],
                    "codigo_iso": pais_data["codigo_iso"],
                    "autoridad": pais_data["autoridad"],
                    "tipo_documento": doc["tipo"],
                    "numero_documento": doc["numero"],
                    "titulo": doc["titulo"],
                    "fecha_publicacion": doc["fecha_publicacion"],
                    "url_original": doc["url"],
                    "archivo_local": str(archivo_destino),
                    "hash_sha256": file_hash,
                    "tamano_bytes": file_size,
                    "fecha_descarga": datetime.now().isoformat(),
                    "descripcion": doc.get("descripcion", "")
                }
                
                resultados["exitosas"].append(metadata)
                resultados["metadatos"][doc["numero"]] = metadata
                
                print(f"  Hash: {file_hash[:16]}...")
                print(f"  Tamaño: {file_size / 1024:.1f} KB")
                
            else:
                resultados["fallidas"].append({
                    "pais": pais_data["pais"],
                    "documento": doc["numero"],
                    "url": doc["url"],
                    "error": "No se pudo descargar"
                })
    
    return resultados


def guardar_metadatos(resultados: Dict, output_file: Path = None):
    """Guardar metadatos de descarga en JSON"""
    if output_file is None:
        output_file = DATA_DIR / "metadatos_descarga.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Metadatos guardados: {output_file}")


def imprimir_resumen(resultados: Dict):
    """Imprimir resumen de descarga"""
    print("\n" + "="*80)
    print("RESUMEN DE DESCARGA")
    print("="*80)
    
    total = len(resultados["exitosas"]) + len(resultados["fallidas"]) + len(resultados["omitidas"])
    
    print(f"\n📊 Estadísticas:")
    print(f"  • Total de documentos: {total}")
    print(f"  • ✓ Descargados: {len(resultados['exitosas'])}")
    print(f"  • ⏭  Omitidos (ya existían): {len(resultados['omitidas'])}")
    print(f"  • ✗ Fallidos: {len(resultados['fallidas'])}")
    
    if resultados["exitosas"]:
        print(f"\n✓ Documentos descargados exitosamente:")
        for doc in resultados["exitosas"]:
            print(f"  • {doc['pais']}: {doc['tipo_documento']} {doc['numero_documento']}")
            print(f"    → {doc['archivo_local']}")
    
    if resultados["fallidas"]:
        print(f"\n✗ Documentos fallidos:")
        for doc in resultados["fallidas"]:
            print(f"  • {doc['pais']}: {doc['documento']}")
            print(f"    URL: {doc['url']}")
    
    if resultados["omitidas"]:
        print(f"\n⏭  Documentos omitidos (ya existían):")
        for doc in resultados["omitidas"]:
            print(f"  • {doc['pais']}: {doc['documento']}")


def verificar_descargas() -> Dict[str, bool]:
    """Verificar qué documentos ya están descargados"""
    estado = {}
    
    for pais_key, pais_data in NORMATIVAS.items():
        pais_dir = DATA_DIR / pais_key
        
        for doc in pais_data["documentos"]:
            archivo = pais_dir / doc["archivo_local"]
            clave = f"{pais_data['codigo_iso']}_{doc['numero']}"
            estado[clave] = archivo.exists()
    
    return estado


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Descargar normativas farmacéuticas de países andinos"
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Forzar descarga incluso si los archivos ya existen'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Solo verificar qué documentos están descargados'
    )
    
    args = parser.parse_args()
    
    if args.verify:
        print("\n🔍 Verificando documentos descargados...\n")
        estado = verificar_descargas()
        
        for clave, descargado in estado.items():
            simbolo = "✓" if descargado else "✗"
            print(f"{simbolo} {clave}: {'Descargado' if descargado else 'Pendiente'}")
        
        total = len(estado)
        descargados = sum(estado.values())
        print(f"\nTotal: {descargados}/{total} documentos descargados")
        
    else:
        # Descargar documentos
        resultados = descargar_todas_normativas(force=args.force)
        
        # Guardar metadatos
        guardar_metadatos(resultados)
        
        # Imprimir resumen
        imprimir_resumen(resultados)
        
        print("\n" + "="*80)
        print("✓ DESCARGA COMPLETADA")
        print("="*80)


if __name__ == "__main__":
    main()
