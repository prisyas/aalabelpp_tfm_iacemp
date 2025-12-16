"""
AALabelPP - Pipeline de Ingestión de PDFs
Extracción, limpieza y segmentación de documentos normativos

Fecha: 2025-12-14
Versión: 1.0
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib

# PDF Processing
import PyPDF2
import pdfplumber
try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("⚠ OCR no disponible. Instale: pip install pytesseract pdf2image")

# Text Processing
from langdetect import detect
import unicodedata

# Database
sys.path.append(str(Path(__file__).parent.parent))
from database.db_config import get_db_session
from database.models import (
    Pais, DocumentoNormativo, ArticuloNormativo
)

# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class TextoExtraido:
    """Resultado de extracción de texto"""
    texto: str
    num_paginas: int
    metodo_extraccion: str  # pypdf2, pdfplumber, ocr
    confianza: float
    idioma_detectado: str


@dataclass
class ArticuloSegmentado:
    """Artículo segmentado del documento"""
    numero_articulo: str
    titulo: Optional[str]
    texto_completo: str
    capitulo: Optional[str]
    seccion: Optional[str]
    orden: int


# ============================================================================
# EXTRACCIÓN DE TEXTO DE PDFs
# ============================================================================

class PDFExtractor:
    """Extractor de texto de PDFs con múltiples métodos"""
    
    @staticmethod
    def extraer_con_pypdf2(pdf_path: Path) -> Optional[str]:
        """Extraer texto usando PyPDF2"""
        try:
            texto_completo = []
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    texto = page.extract_text()
                    if texto:
                        texto_completo.append(texto)
            
            return "\n".join(texto_completo) if texto_completo else None
        except Exception as e:
            print(f"Error con PyPDF2: {str(e)}")
            return None
    
    @staticmethod
    def extraer_con_pdfplumber(pdf_path: Path) -> Optional[str]:
        """Extraer texto usando pdfplumber (más robusto)"""
        try:
            texto_completo = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    texto = page.extract_text()
                    if texto:
                        texto_completo.append(texto)
            
            return "\n".join(texto_completo) if texto_completo else None
        except Exception as e:
            print(f"Error con pdfplumber: {str(e)}")
            return None
    
    @staticmethod
    def extraer_con_ocr(pdf_path: Path) -> Optional[str]:
        """Extraer texto usando OCR (para PDFs escaneados)"""
        if not OCR_AVAILABLE:
            print("⚠ OCR no disponible")
            return None
        
        try:
            print("  🔍 Ejecutando OCR (puede tomar varios minutos)...")
            
            # Convertir PDF a imágenes
            images = convert_from_path(str(pdf_path), dpi=300)
            
            # OCR en cada imagen
            texto_completo = []
            for i, image in enumerate(images, 1):
                print(f"    Procesando página {i}/{len(images)}...")
                texto = pytesseract.image_to_string(image, lang='spa')
                if texto:
                    texto_completo.append(texto)
            
            return "\n".join(texto_completo) if texto_completo else None
        except Exception as e:
            print(f"Error con OCR: {str(e)}")
            return None
    
    @classmethod
    def extraer_texto(cls, pdf_path: Path) -> TextoExtraido:
        """Extraer texto usando el mejor método disponible"""
        print(f"\n📄 Procesando: {pdf_path.name}")
        
        # Intentar PyPDF2 primero (más rápido)
        print("  Intentando PyPDF2...")
        texto = cls.extraer_con_pypdf2(pdf_path)
        metodo = "pypdf2"
        
        # Si falla o texto muy corto, intentar pdfplumber
        if not texto or len(texto.strip()) < 100:
            print("  Intentando pdfplumber...")
            texto = cls.extraer_con_pdfplumber(pdf_path)
            metodo = "pdfplumber"
        
        # Si aún falla, intentar OCR
        if not texto or len(texto.strip()) < 100:
            print("  Texto insuficiente, intentando OCR...")
            texto = cls.extraer_con_ocr(pdf_path)
            metodo = "ocr"
        
        if not texto:
            raise ValueError(f"No se pudo extraer texto de {pdf_path}")
        
        # Detectar idioma
        try:
            idioma = detect(texto[:1000])  # Detectar con primeras 1000 chars
        except:
            idioma = "es"  # Asumir español
        
        # Calcular confianza (heurística)
        palabras = texto.split()
        confianza = min(1.0, len(palabras) / 1000) if palabras else 0.0
        
        # Contar páginas
        try:
            with open(pdf_path, 'rb') as f:
                pdf = PyPDF2.PdfReader(f)
                num_paginas = len(pdf.pages)
        except:
            num_paginas = texto.count('\f') + 1  # Contar page breaks
        
        print(f"  ✓ Extraído: {len(palabras)} palabras, {num_paginas} páginas")
        print(f"  Método: {metodo}, Idioma: {idioma}, Confianza: {confianza:.2f}")
        
        return TextoExtraido(
            texto=texto,
            num_paginas=num_paginas,
            metodo_extraccion=metodo,
            confianza=confianza,
            idioma_detectado=idioma
        )


# ============================================================================
# LIMPIEZA Y NORMALIZACIÓN DE TEXTO
# ============================================================================

class TextoNormalizador:
    """Normaliza y limpia texto extraído"""
    
    @staticmethod
    def limpiar_texto(texto: str) -> str:
        """Limpieza básica de texto"""
        # Normalizar unicode
        texto = unicodedata.normalize('NFKC', texto)
        
        # Eliminar saltos de página
        texto = texto.replace('\f', '\n\n')
        
        # Normalizar espacios en blanco
        texto = re.sub(r'\s+', ' ', texto)
        
        # Normalizar saltos de línea múltiples
        texto = re.sub(r'\n\s*\n', '\n\n', texto)
        
        # Eliminar guiones de división de palabras al final de línea
        texto = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', texto)
        
        return texto.strip()
    
    @staticmethod
    def normalizar_articulos(texto: str) -> str:
        """Normalizar formato de artículos"""
        # Estandarizar "Artículo", "Art.", "ART", etc.
        texto = re.sub(
            r'\b(ART[ÍI]CULO|ART\.|ARTÍCULO|ARTICULO)\s*(\d+)',
            r'Artículo \2',
            texto,
            flags=re.IGNORECASE
        )
        
        return texto
    
    @classmethod
    def normalizar_completo(cls, texto: str) -> str:
        """Aplicar todas las normalizaciones"""
        texto = cls.limpiar_texto(texto)
        texto = cls.normalizar_articulos(texto)
        return texto


# ============================================================================
# SEGMENTACIÓN DE ARTÍCULOS
# ============================================================================

class ArticuloSegmentador:
    """Segmenta documentos en artículos individuales"""
    
    # Patrones de artículos
    PATRON_ARTICULO = re.compile(
        r'(?:^|\n)\s*(?:Artículo|ARTÍCULO|Art\.)\s+(\d+[a-zA-Z]?)\s*[.:-]?\s*(.{0,200}?)?(?=\n|$)',
        re.MULTILINE | re.IGNORECASE
    )
    
    # Patrones de capítulos y secciones
    PATRON_CAPITULO = re.compile(
        r'(?:^|\n)\s*(?:CAPÍTULO|CAPITULO|CAP\.)\s+([IVX0-9]+)\s*[.:-]?\s*(.+?)(?=\n)',
        re.MULTILINE | re.IGNORECASE
    )
    
    PATRON_SECCION = re.compile(
        r'(?:^|\n)\s*(?:SECCIÓN|SECCION|SEC\.)\s+([IVX0-9]+)\s*[.:-]?\s*(.+?)(?=\n)',
        re.MULTILINE | re.IGNORECASE
    )
    
    @classmethod
    def extraer_estructura(cls, texto: str) -> Dict:
        """Extraer estructura de capítulos y secciones"""
        capitulos = []
        for match in cls.PATRON_CAPITULO.finditer(texto):
            capitulos.append({
                'numero': match.group(1),
                'titulo': match.group(2).strip(),
                'posicion': match.start()
            })
        
        secciones = []
        for match in cls.PATRON_SECCION.finditer(texto):
            secciones.append({
                'numero': match.group(1),
                'titulo': match.group(2).strip(),
                'posicion': match.start()
            })
        
        return {
            'capitulos': capitulos,
            'secciones': secciones
        }
    
    @classmethod
    def segmentar_articulos(cls, texto: str) -> List[ArticuloSegmentado]:
        """Segmentar texto en artículos individuales"""
        articulos = []
        estructura = cls.extraer_estructura(texto)
        
        # Encontrar todos los artículos
        matches = list(cls.PATRON_ARTICULO.finditer(texto))
        
        if not matches:
            print("  ⚠ No se encontraron artículos con patrón estándar")
            return []
        
        print(f"  📑 Encontrados {len(matches)} artículos")
        
        for i, match in enumerate(matches):
            numero = match.group(1)
            titulo = match.group(2).strip() if match.group(2) else None
            
            # Extraer texto del artículo (hasta el siguiente artículo)
            inicio = match.end()
            fin = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
            texto_articulo = texto[inicio:fin].strip()
            
            # Determinar capítulo y sección
            posicion = match.start()
            capitulo = cls._encontrar_contexto(posicion, estructura['capitulos'])
            seccion = cls._encontrar_contexto(posicion, estructura['secciones'])
            
            articulo = ArticuloSegmentado(
                numero_articulo=numero,
                titulo=titulo,
                texto_completo=texto_articulo,
                capitulo=capitulo,
                seccion=seccion,
                orden=i + 1
            )
            articulos.append(articulo)
        
        return articulos
    
    @staticmethod
    def _encontrar_contexto(posicion: int, elementos: List[Dict]) -> Optional[str]:
        """Encontrar el capítulo/sección que contiene una posición"""
        for elem in reversed(elementos):
            if elem['posicion'] < posicion:
                return f"{elem['numero']} - {elem['titulo']}"
        return None


# ============================================================================
# CARGADOR A BASE DE DATOS
# ============================================================================

class DocumentoCargador:
    """Carga documentos y artículos en la base de datos"""
    
    @staticmethod
    def calcular_hash(pdf_path: Path) -> str:
        """Calcular hash SHA-256 del archivo"""
        sha256 = hashlib.sha256()
        with open(pdf_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    @classmethod
    def cargar_documento(
        cls,
        pdf_path: Path,
        metadata: Dict,
        texto_extraido: TextoExtraido,
        articulos: List[ArticuloSegmentado]
    ) -> int:
        """Cargar documento completo en BD"""
        
        with get_db_session() as session:
            # Buscar país
            pais = session.query(Pais).filter(
                Pais.codigo_iso == metadata['codigo_iso']
            ).first()
            
            if not pais:
                raise ValueError(f"País no encontrado: {metadata['codigo_iso']}")
            
            # Crear documento
            doc = DocumentoNormativo(
                pais_id=pais.id,
                tipo_documento=metadata['tipo_documento'],
                numero_documento=metadata['numero_documento'],
                titulo=metadata['titulo'],
                fecha_publicacion=datetime.fromisoformat(metadata['fecha_publicacion']),
                url_oficial=metadata.get('url_original'),
                ruta_archivo_pdf=str(pdf_path),
                hash_archivo=cls.calcular_hash(pdf_path),
                descripcion=metadata.get('descripcion'),
                num_articulos=len(articulos),
                num_paginas=texto_extraido.num_paginas,
                estado='vigente',
                usuario_creacion='sistema'
            )
            
            session.add(doc)
            session.flush()  # Para obtener doc.id
            
            # Crear artículos
            for art in articulos:
                articulo_db = ArticuloNormativo(
                    documento_id=doc.id,
                    numero_articulo=art.numero_articulo,
                    titulo_articulo=art.titulo,
                    texto_completo=art.texto_completo,
                    texto_normalizado=TextoNormalizador.normalizar_completo(art.texto_completo),
                    capitulo=art.capitulo,
                    seccion=art.seccion,
                    orden_jerarquico=art.orden,
                    num_palabras=len(art.texto_completo.split())
                )
                session.add(articulo_db)
            
            session.commit()
            print(f"  ✓ Documento cargado: ID={doc.id}")
            print(f"  ✓ {len(articulos)} artículos cargados")
            
            return doc.id


# ============================================================================
# PIPELINE COMPLETO
# ============================================================================

class PipelineIngestion:
    """Pipeline completo de ingestión de PDFs"""
    
    def __init__(self):
        self.extractor = PDFExtractor()
        self.normalizador = TextoNormalizador()
        self.segmentador = ArticuloSegmentador()
        self.cargador = DocumentoCargador()
    
    def procesar_documento(
        self,
        pdf_path: Path,
        metadata: Dict
    ) -> Dict:
        """Procesar un documento completo"""
        
        print("="*80)
        print(f"PROCESANDO: {metadata['pais']} - {metadata['numero_documento']}")
        print("="*80)
        
        resultado = {
            'exito': False,
            'pdf_path': str(pdf_path),
            'metadata': metadata,
            'errores': []
        }
        
        try:
            # 1. Extraer texto
            texto_extraido = self.extractor.extraer_texto(pdf_path)
            
            # 2. Normalizar
            texto_normalizado = self.normalizador.normalizar_completo(
                texto_extraido.texto
            )
            
            # 3. Segmentar artículos
            articulos = self.segmentador.segmentar_articulos(texto_normalizado)
            
            if not articulos:
                resultado['errores'].append("No se pudieron segmentar artículos")
                return resultado
            
            # 4. Cargar en BD
            doc_id = self.cargador.cargar_documento(
                pdf_path,
                metadata,
                texto_extraido,
                articulos
            )
            
            resultado['exito'] = True
            resultado['documento_id'] = doc_id
            resultado['num_articulos'] = len(articulos)
            resultado['num_paginas'] = texto_extraido.num_paginas
            resultado['metodo_extraccion'] = texto_extraido.metodo_extraccion
            
            print("\n✅ DOCUMENTO PROCESADO EXITOSAMENTE")
            
        except Exception as e:
            resultado['errores'].append(str(e))
            print(f"\n❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return resultado


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    import json
    
    parser = argparse.ArgumentParser(
        description="Pipeline de ingestión de PDFs normativos"
    )
    parser.add_argument(
        '--pdf',
        type=Path,
        help='Ruta al PDF a procesar'
    )
    parser.add_argument(
        '--metadata',
        type=Path,
        help='Ruta al JSON con metadatos'
    )
    parser.add_argument(
        '--process-all',
        action='store_true',
        help='Procesar todos los PDFs en data/normativas/'
    )
    
    args = parser.parse_args()
    
    pipeline = PipelineIngestion()
    
    if args.process_all:
        # Procesar todos los documentos
        data_dir = Path(__file__).parent.parent / "data" / "normativas"
        metadata_file = data_dir / "metadatos_descarga.json"
        
        if not metadata_file.exists():
            print("❌ No se encontró metadatos_descarga.json")
            print("   Ejecute primero: python scripts/download_normatives.py")
            return
        
        with open(metadata_file) as f:
            metadatos = json.load(f)
        
        resultados = []
        for metadata in metadatos.get('metadatos', {}).values():
            pdf_path = Path(metadata['archivo_local'])
            if pdf_path.exists():
                resultado = pipeline.procesar_documento(pdf_path, metadata)
                resultados.append(resultado)
        
        # Resumen
        print("\n" + "="*80)
        print("RESUMEN DE PROCESAMIENTO")
        print("="*80)
        exitosos = sum(1 for r in resultados if r['exito'])
        print(f"✓ Exitosos: {exitosos}/{len(resultados)}")
        
    elif args.pdf and args.metadata:
        # Procesar un documento específico
        with open(args.metadata) as f:
            metadata = json.load(f)
        
        resultado = pipeline.procesar_documento(args.pdf, metadata)
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
