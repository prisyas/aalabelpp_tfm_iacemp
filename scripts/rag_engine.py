"""
AALabelPP - Motor RAG (Retrieval-Augmented Generation)
Sistema de armonización de etiquetas farmacéuticas con IA

Fecha: 2025-12-14
Versión: 1.0
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json

# ML/NLP
from sentence_transformers import SentenceTransformer
import numpy as np

# Database
sys.path.append(str(Path(__file__).parent.parent))
from database.db_config import get_db_session
from database.models import (
    ArticuloNormativo, EmbeddingVectorial, 
    DocumentoNormativo, Pais, SeccionEtiqueta
)

# LLM (condicional)
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class ArticuloRecuperado:
    """Artículo recuperado con score de relevancia"""
    articulo_id: int
    numero_articulo: str
    texto: str
    pais: str
    documento: str
    similitud: float
    capitulo: Optional[str] = None
    seccion: Optional[str] = None


@dataclass
class SeccionArmonizada:
    """Sección de etiqueta armonizada"""
    codigo_seccion: str
    nombre_seccion: str
    contenido_armonizado: str
    articulos_fuente: List[ArticuloRecuperado] = field(default_factory=list)
    justificacion: str = ""
    criterio_aplicado: str = "máxima restrictividad"


@dataclass
class EtiquetaArmonizada:
    """Etiqueta farmacéutica completa armonizada"""
    nombre_producto: str
    secciones: List[SeccionArmonizada]
    paises: List[str]
    fecha_generacion: datetime
    metadata: Dict = field(default_factory=dict)


# ============================================================================
# RECUPERADOR SEMÁNTICO
# ============================================================================

class SemanticRetriever:
    """Recuperador de artículos por similitud semántica"""
    
    def __init__(self, modelo_embedding: str = 'multilingual-mpnet'):
        """Inicializar recuperador
        
        Args:
            modelo_embedding: Nombre corto del modelo
        """
        # Mapeo de nombres cortos a paths completos
        MODELO_PATHS = {
            'multilingual-mpnet': 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2',
            'multilingual-minilm': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
            'spanish-roberta': 'hiiamsid/sentence_similarity_spanish_es'
        }
        
        self.modelo_path = MODELO_PATHS.get(
            modelo_embedding,
            'sentence-transformers/paraphrase-multilingual-mpnet-base-v2'
        )
        
        print(f"\n🔍 Cargando modelo de retrieval: {self.modelo_path}")
        self.modelo = SentenceTransformer(self.modelo_path)
        print(f"   ✓ Modelo cargado")
    
    def buscar_articulos_relevantes(
        self,
        query: str,
        paises: List[str],
        top_k: int = 5,
        umbral_similitud: float = 0.5
    ) -> List[ArticuloRecuperado]:
        """Buscar artículos relevantes por similitud semántica
        
        Args:
            query: Texto de consulta
            paises: Lista de códigos ISO de países
            top_k: Número de resultados
            umbral_similitud: Similitud mínima (0-1)
            
        Returns:
            Lista de artículos recuperados
        """
        # Generar embedding de la query
        query_embedding = self.modelo.encode(
            query,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        
        # Buscar en BD
        with get_db_session() as session:
            from sqlalchemy import func, and_
            
            # Subconsulta para filtrar por países
            paises_ids = session.query(Pais.id).filter(
                Pais.codigo_iso.in_(paises)
            ).subquery()
            
            # Query vectorial con pgvector
            query_sql = f"""
                SELECT 
                    a.id as articulo_id,
                    a.numero_articulo,
                    a.texto_completo,
                    a.capitulo,
                    a.seccion,
                    p.nombre as pais,
                    d.numero_documento,
                    1 - (e.embedding <=> ARRAY[{','.join(map(str, query_embedding))}]::vector) as similitud
                FROM embeddings_vectoriales e
                JOIN articulos_normativos a ON e.articulo_id = a.id
                JOIN documentos_normativos d ON a.documento_id = d.id
                JOIN paises p ON d.pais_id = p.id
                WHERE 
                    e.modelo_embedding = :modelo
                    AND d.pais_id IN :paises_ids
                    AND d.estado = 'vigente'
                    AND (1 - (e.embedding <=> ARRAY[{','.join(map(str, query_embedding))}]::vector)) >= :umbral
                ORDER BY e.embedding <=> ARRAY[{','.join(map(str, query_embedding))}]::vector
                LIMIT :limit
            """
            
            # Ejecutar (simplificado para demostración)
            # En producción, usar la función SQL o consulta ORM apropiada
            
            # Alternativa: Búsqueda in-memory (para desarrollo)
            articulos = self._buscar_articulos_fallback(
                session,
                query_embedding,
                paises,
                top_k,
                umbral_similitud
            )
            
            return articulos
    
    def _buscar_articulos_fallback(
        self,
        session,
        query_embedding: np.ndarray,
        paises: List[str],
        top_k: int,
        umbral: float
    ) -> List[ArticuloRecuperado]:
        """Búsqueda fallback in-memory (desarrollo)"""
        from sqlalchemy import and_
        
        # Obtener todos los embeddings de países objetivo
        paises_objs = session.query(Pais).filter(Pais.codigo_iso.in_(paises)).all()
        paises_ids = [p.id for p in paises_objs]
        
        embeddings = session.query(
            EmbeddingVectorial, ArticuloNormativo, DocumentoNormativo, Pais
        ).join(
            ArticuloNormativo, EmbeddingVectorial.articulo_id == ArticuloNormativo.id
        ).join(
            DocumentoNormativo, ArticuloNormativo.documento_id == DocumentoNormativo.id
        ).join(
            Pais, DocumentoNormativo.pais_id == Pais.id
        ).filter(
            and_(
                DocumentoNormativo.pais_id.in_(paises_ids),
                DocumentoNormativo.estado == 'vigente',
                EmbeddingVectorial.modelo_embedding == self.modelo_path
            )
        ).all()
        
        # Calcular similitudes
        resultados = []
        for emb, art, doc, pais in embeddings:
            # Convertir embedding de BD a numpy
            emb_vector = np.array(emb.embedding)
            
            # Similitud coseno (vectores ya normalizados)
            similitud = float(np.dot(query_embedding, emb_vector))
            
            if similitud >= umbral:
                resultados.append(ArticuloRecuperado(
                    articulo_id=art.id,
                    numero_articulo=art.numero_articulo,
                    texto=art.texto_completo,
                    pais=pais.nombre,
                    documento=doc.numero_documento,
                    similitud=similitud,
                    capitulo=art.capitulo,
                    seccion=art.seccion
                ))
        
        # Ordenar por similitud
        resultados.sort(key=lambda x: x.similitud, reverse=True)
        
        return resultados[:top_k]


# ============================================================================
# GENERADOR CON LLM
# ============================================================================

class LLMGenerator:
    """Generador de contenido usando LLMs"""
    
    def __init__(self, modelo: str = 'gpt-4', api_key: Optional[str] = None):
        """Inicializar generador
        
        Args:
            modelo: 'gpt-4', 'gpt-3.5-turbo', 'gemini-pro'
            api_key: API key (si no está en env)
        """
        self.modelo = modelo
        
        if modelo.startswith('gpt'):
            if not OPENAI_AVAILABLE:
                raise ImportError("openai no instalado: pip install openai")
            
            if api_key:
                openai.api_key = api_key
            elif os.getenv('OPENAI_API_KEY'):
                openai.api_key = os.getenv('OPENAI_API_KEY')
            else:
                raise ValueError("OPENAI_API_KEY no configurada")
            
            self.tipo = 'openai'
            print(f"\n🤖 Usando OpenAI: {modelo}")
            
        elif modelo.startswith('gemini'):
            if not GEMINI_AVAILABLE:
                raise ImportError("google-generativeai no instalado")
            
            if api_key:
                genai.configure(api_key=api_key)
            elif os.getenv('GOOGLE_API_KEY'):
                genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
            else:
                raise ValueError("GOOGLE_API_KEY no configurada")
            
            self.tipo = 'gemini'
            self.client = genai.GenerativeModel(modelo)
            print(f"\n🤖 Usando Google Gemini: {modelo}")
        
        else:
            raise ValueError(f"Modelo no soportado: {modelo}")
    
    def generar(
        self,
        prompt: str,
        temperatura: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """Generar texto con LLM
        
        Args:
            prompt: Prompt completo
            temperatura: Creatividad (0.0-1.0)
            max_tokens: Tokens máximos
            
        Returns:
            Texto generado
        """
        if self.tipo == 'openai':
            response = openai.ChatCompletion.create(
                model=self.modelo,
                messages=[
                    {"role": "system", "content": "Eres un experto en regulación farmacéutica de la región andina."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperatura,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        
        elif self.tipo == 'gemini':
            response = self.client.generate_content(
                prompt,
                generation_config={
                    'temperature': temperatura,
                    'max_output_tokens': max_tokens
                }
            )
            return response.text
        
        return ""


# ============================================================================
# SISTEMA DE PROMPTS
# ============================================================================

class PromptsArmonizacion:
    """Biblioteca de prompts para armonización"""
    
    @staticmethod
    def prompt_seccion(
        nombre_seccion: str,
        descripcion_seccion: str,
        articulos_relevantes: List[ArticuloRecuperado],
        paises: List[str]
    ) -> str:
        """Generar prompt para armonizar una sección
        
        Args:
            nombre_seccion: Nombre de la sección
            descripcion_seccion: Descripción de la sección
            articulos_relevantes: Artículos normativos recuperados
            paises: Países objetivo
            
        Returns:
            Prompt completo
        """
        # Construir contexto de evidencia
        evidencia = []
        for i, art in enumerate(articulos_relevantes, 1):
            evidencia.append(f"""
[ARTÍCULO {i} - {art.pais}]
Documento: {art.documento}
Artículo: {art.numero_articulo}
Relevancia: {art.similitud:.2%}

{art.texto}
""")
        
        prompt = f"""
TAREA: Armonizar la sección "{nombre_seccion}" de una etiqueta farmacéutica para los países: {', '.join(paises)}.

DESCRIPCIÓN DE LA SECCIÓN:
{descripcion_seccion}

OBJETIVO:
Generar el contenido de esta sección que cumpla con los requisitos normativos de TODOS los países especificados, aplicando el criterio de MÁXIMA RESTRICTIVIDAD cuando hay diferencias.

EVIDENCIA NORMATIVA:
{''.join(evidencia)}

INSTRUCCIONES:
1. Analiza los requisitos de cada país basándote ÚNICAMENTE en la evidencia proporcionada
2. Identifica diferencias entre países
3. Aplica el criterio de MÁXIMA RESTRICTIVIDAD (incluir el requisito más estricto)
4. Redacta el contenido armonizado en español claro y profesional
5. NO inventes requisitos que no aparezcan en la evidencia
6. Si la evidencia es insuficiente, indícalo claramente

FORMATO DE RESPUESTA:
### CONTENIDO ARMONIZADO
[Escribe aquí el texto armonizado]

### JUSTIFICACIÓN
[Explica brevemente qué requisitos de qué países se consideraron y por qué]

### FUENTES
[Lista los artículos específicos que respaldaron cada decisión]

NOTA: Sé preciso, profesional y apégate estrictamente a la evidencia normativa proporcionada.
"""
        
        return prompt
    
    @staticmethod
    def prompt_analisis_justificativo(
        etiqueta: EtiquetaArmonizada
    ) -> str:
        """Generar prompt para análisis justificativo completo"""
        
        secciones_resumen = []
        for seccion in etiqueta.secciones:
            fuentes = [f"{art.pais} - {art.documento} Art. {art.numero_articulo}" 
                      for art in seccion.articulos_fuente]
            
            secciones_resumen.append(f"""
**{seccion.nombre_seccion}**
- Fuentes: {'; '.join(fuentes[:3])}{'...' if len(fuentes) > 3 else ''}
- Criterio: {seccion.criterio_aplicado}
""")
        
        prompt = f"""
TAREA: Generar un análisis justificativo profesional para la etiqueta armonizada de "{etiqueta.nombre_producto}".

SECCIONES ARMONIZADAS:
{''.join(secciones_resumen)}

PAÍSES CONSIDERADOS: {', '.join(etiqueta.paises)}

OBJETIVO:
Crear un documento de análisis que justifique cada decisión de armonización con citas específicas a artículos normativos.

ESTRUCTURA REQUERIDA:

## 1. RESUMEN EJECUTIVO
- Producto armonizado
- Países incluidos
- Metodología aplicada (RAG + máxima restrictividad)

## 2. ANÁLISIS POR SECCIÓN
Para cada sección:
- Requisitos por país
- Diferencias identificadas
- Decisión de armonización
- Artículos normativos aplicados

## 3. TABLA DE TRAZABILIDAD
Tabla con columnas: Sección | País | Documento | Artículo | Requisito

## 4. CONCLUSIONES
- Nivel de armonización logrado
- Áreas de divergencia significativa
- Recomendaciones

FORMATO: Markdown profesional
EXTENSIÓN: 3-5 páginas
TONO: Técnico, preciso, regulatorio
"""
        
        return prompt


# ============================================================================
# MOTOR RAG PRINCIPAL
# ============================================================================

class RAGEngine:
    """Motor RAG completo para armonización"""
    
    def __init__(
        self,
        modelo_embedding: str = 'multilingual-mpnet',
        modelo_llm: str = 'gpt-4'
    ):
        """Inicializar motor RAG
        
        Args:
            modelo_embedding: Modelo para embeddings
            modelo_llm: Modelo LLM para generación
        """
        self.retriever = SemanticRetriever(modelo_embedding)
        self.generator = LLMGenerator(modelo_llm)
        self.prompts = PromptsArmonizacion()
        
        print(f"\n✅ Motor RAG inicializado")
    
    def armonizar_seccion(
        self,
        codigo_seccion: str,
        nombre_seccion: str,
        descripcion: str,
        paises: List[str],
        top_k: int = 5
    ) -> SeccionArmonizada:
        """Armonizar una sección de etiqueta
        
        Args:
            codigo_seccion: Código de la sección
            nombre_seccion: Nombre de la sección
            descripcion: Descripción de la sección
            paises: Códigos ISO de países
            top_k: Artículos a recuperar
            
        Returns:
            Sección armonizada
        """
        print(f"\n📝 Armonizando: {nombre_seccion}")
        
        # 1. RECUPERACIÓN (Retrieval)
        print(f"   🔍 Recuperando artículos relevantes...")
        query = f"{nombre_seccion}: {descripcion}"
        
        articulos = self.retriever.buscar_articulos_relevantes(
            query=query,
            paises=paises,
            top_k=top_k * len(paises)  # Más artículos para multi-país
        )
        
        print(f"   ✓ {len(articulos)} artículos recuperados")
        
        if not articulos:
            print(f"   ⚠ No se encontraron artículos relevantes")
            return SeccionArmonizada(
                codigo_seccion=codigo_seccion,
                nombre_seccion=nombre_seccion,
                contenido_armonizado="[Insuficiente evidencia normativa]",
                articulos_fuente=[],
                justificacion="No se encontraron artículos relevantes en la base de datos.",
                criterio_aplicado="N/A"
            )
        
        # 2. GENERACIÓN (Augmented Generation)
        print(f"   🤖 Generando contenido armonizado...")
        prompt = self.prompts.prompt_seccion(
            nombre_seccion=nombre_seccion,
            descripcion_seccion=descripcion,
            articulos_relevantes=articulos,
            paises=paises
        )
        
        respuesta = self.generator.generar(
            prompt=prompt,
            temperatura=0.1,  # Baja creatividad (adherencia a evidencia)
            max_tokens=2000
        )
        
        # 3. PARSING de respuesta
        contenido, justificacion = self._parsear_respuesta(respuesta)
        
        print(f"   ✓ Contenido generado ({len(contenido)} caracteres)")
        
        return SeccionArmonizada(
            codigo_seccion=codigo_seccion,
            nombre_seccion=nombre_seccion,
            contenido_armonizado=contenido,
            articulos_fuente=articulos[:top_k],  # Top K para metadata
            justificacion=justificacion,
            criterio_aplicado="máxima restrictividad"
        )
    
    def armonizar_etiqueta_completa(
        self,
        nombre_producto: str,
        paises: List[str],
        secciones: Optional[List[str]] = None
    ) -> EtiquetaArmonizada:
        """Armonizar etiqueta completa
        
        Args:
            nombre_producto: Nombre del producto
            paises: Códigos ISO de países
            secciones: Códigos de secciones (None = todas)
            
        Returns:
            Etiqueta armonizada completa
        """
        print("\n" + "="*80)
        print(f"ARMONIZACIÓN COMPLETA: {nombre_producto}")
        print(f"Países: {', '.join(paises)}")
        print("="*80)
        
        # Obtener secciones de BD
        with get_db_session() as session:
            query = session.query(SeccionEtiqueta).filter(
                SeccionEtiqueta.activa == True
            )
            
            if secciones:
                query = query.filter(SeccionEtiqueta.codigo.in_(secciones))
            
            secciones_db = query.order_by(SeccionEtiqueta.orden_visualizacion).all()
        
        # Armonizar cada sección
        secciones_armonizadas = []
        for seccion_db in secciones_db:
            seccion_arm = self.armonizar_seccion(
                codigo_seccion=seccion_db.codigo,
                nombre_seccion=seccion_db.nombre_seccion,
                descripcion=seccion_db.descripcion or "",
                paises=paises
            )
            secciones_armonizadas.append(seccion_arm)
        
        # Crear etiqueta completa
        etiqueta = EtiquetaArmonizada(
            nombre_producto=nombre_producto,
            secciones=secciones_armonizadas,
            paises=paises,
            fecha_generacion=datetime.now(),
            metadata={
                'modelo_embedding': self.retriever.modelo_path,
                'modelo_llm': self.generator.modelo,
                'num_secciones': len(secciones_armonizadas)
            }
        )
        
        print("\n✅ ARMONIZACIÓN COMPLETADA")
        
        return etiqueta
    
    def _parsear_respuesta(self, respuesta: str) -> Tuple[str, str]:
        """Parsear respuesta del LLM"""
        # Separar contenido y justificación
        partes = respuesta.split('### JUSTIFICACIÓN')
        
        contenido = partes[0].replace('### CONTENIDO ARMONIZADO', '').strip()
        justificacion = partes[1].split('### FUENTES')[0].strip() if len(partes) > 1 else ""
        
        return contenido, justificacion


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Motor RAG para armonización de etiquetas"
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Ejecutar test de armonización'
    )
    parser.add_argument(
        '--producto',
        default='Ejemplo Farmacéutico',
        help='Nombre del producto'
    )
    parser.add_argument(
        '--paises',
        default='CO,EC,PE,BO',
        help='Códigos ISO de países (separados por coma)'
    )
    parser.add_argument(
        '--secciones',
        help='Códigos de secciones a armonizar (separados por coma)'
    )
    parser.add_argument(
        '--modelo-llm',
        default='gpt-4',
        help='Modelo LLM (gpt-4, gpt-3.5-turbo, gemini-pro)'
    )
    
    args = parser.parse_args()
    
    # Inicializar BD
    DatabaseEngine.initialize()
    
    # Test básico
    if args.test:
        print("\n" + "="*80)
        print("TEST DE MOTOR RAG")
        print("="*80)
        
        try:
            # Crear motor
            engine = RAGEngine(modelo_llm=args.modelo_llm)
            
            # Test de armonización de una sección
            paises = args.paises.split(',')
            
            seccion_test = engine.armonizar_seccion(
                codigo_seccion='ADVERTENCIAS',
                nombre_seccion='Advertencias y Precauciones',
                descripcion='Información de seguridad sobre el uso del medicamento',
                paises=paises,
                top_k=5
            )
            
            print("\n" + "="*80)
            print("RESULTADO DEL TEST")
            print("="*80)
            print(f"\n📄 Sección: {seccion_test.nombre_seccion}")
            print(f"\n📝 Contenido Armonizado:")
            print(seccion_test.contenido_armonizado[:500] + "...")
            print(f"\n📚 Fuentes utilizadas: {len(seccion_test.articulos_fuente)}")
            
            print("\n✅ TEST COMPLETADO")
            
        except Exception as e:
            print(f"\n❌ ERROR EN TEST: {str(e)}")
            import traceback
            traceback.print_exc()
            return
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
