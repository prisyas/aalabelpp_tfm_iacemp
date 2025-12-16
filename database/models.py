"""
AALabelPP - Modelos de Base de Datos
Sistema de Gestión de Normativas Farmacéuticas con RAG

Modelos SQLAlchemy para interacción con PostgreSQL + pgvector
Fecha: 2025-12-14
Versión: 1.0
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Date, 
    Float, ForeignKey, ARRAY, CheckConstraint, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import uuid

Base = declarative_base()


# ============================================================================
# MODELO: País
# ============================================================================

class Pais(Base):
    """Modelo para países de la zona andina"""
    __tablename__ = 'paises'
    
    id = Column(Integer, primary_key=True)
    codigo_iso = Column(String(2), unique=True, nullable=False)
    nombre = Column(String(100), nullable=False)
    nombre_oficial = Column(String(200))
    autoridad_sanitaria = Column(String(200))
    acronimo_autoridad = Column(String(20))
    activo = Column(Boolean, default=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    fecha_actualizacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    documentos = relationship("DocumentoNormativo", back_populates="pais", cascade="all, delete-orphan")
    requisitos = relationship("RequisitoPorSeccion", back_populates="pais")
    
    def __repr__(self):
        return f"<Pais(codigo={self.codigo_iso}, nombre={self.nombre}, autoridad={self.acronimo_autoridad})>"


# ============================================================================
# MODELO: Documento Normativo
# ============================================================================

class DocumentoNormativo(Base):
    """Modelo para documentos normativos oficiales"""
    __tablename__ = 'documentos_normativos'
    
    id = Column(Integer, primary_key=True)
    pais_id = Column(Integer, ForeignKey('paises.id', ondelete='CASCADE'), nullable=False)
    
    # Identificación
    tipo_documento = Column(String(50), nullable=False)
    numero_documento = Column(String(100), nullable=False)
    titulo = Column(Text, nullable=False)
    
    # Información oficial
    fecha_publicacion = Column(Date)
    fecha_vigencia = Column(Date)
    diario_oficial = Column(String(200))
    estado = Column(String(20), default='vigente')
    
    # Ubicación
    url_oficial = Column(Text)
    ruta_archivo_pdf = Column(Text)
    hash_archivo = Column(String(64))
    
    # Metadatos
    descripcion = Column(Text)
    ambito_aplicacion = Column(Text)
    num_articulos = Column(Integer)
    num_paginas = Column(Integer)
    
    # Control de versiones
    version = Column(Integer, default=1)
    documento_padre_id = Column(Integer, ForeignKey('documentos_normativos.id'))
    notas_version = Column(Text)
    
    # Auditoría
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    fecha_actualizacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    usuario_creacion = Column(String(100))
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('pais_id', 'numero_documento', 'version', name='uq_doc_pais_numero_version'),
        CheckConstraint("estado IN ('vigente', 'derogado', 'modificado')", name='ck_estado_valido'),
    )
    
    # Relaciones
    pais = relationship("Pais", back_populates="documentos")
    articulos = relationship("ArticuloNormativo", back_populates="documento", cascade="all, delete-orphan")
    versiones_hijas = relationship("DocumentoNormativo", remote_side=[documento_padre_id])
    
    def __repr__(self):
        return f"<DocumentoNormativo(pais={self.pais_id}, numero={self.numero_documento}, estado={self.estado})>"


# ============================================================================
# MODELO: Artículo Normativo
# ============================================================================

class ArticuloNormativo(Base):
    """Modelo para artículos/secciones de documentos normativos"""
    __tablename__ = 'articulos_normativos'
    
    id = Column(Integer, primary_key=True)
    documento_id = Column(Integer, ForeignKey('documentos_normativos.id', ondelete='CASCADE'), nullable=False)
    
    # Identificación
    numero_articulo = Column(String(50))
    titulo_articulo = Column(Text)
    
    # Jerarquía
    capitulo = Column(String(100))
    seccion = Column(String(100))
    subseccion = Column(String(100))
    orden_jerarquico = Column(Integer)
    
    # Contenido
    texto_completo = Column(Text, nullable=False)
    texto_normalizado = Column(Text)
    num_palabras = Column(Integer)
    
    # Clasificación semántica
    tema_principal = Column(String(100))
    temas_relacionados = Column(ARRAY(Text))
    
    # Referencias
    articulos_relacionados = Column(ARRAY(Integer))
    
    # Auditoría
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    fecha_actualizacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    documento = relationship("DocumentoNormativo", back_populates="articulos")
    embeddings = relationship("EmbeddingVectorial", back_populates="articulo", cascade="all, delete-orphan")
    requisitos = relationship("RequisitoPorSeccion", back_populates="articulo")
    
    def __repr__(self):
        return f"<ArticuloNormativo(id={self.id}, numero={self.numero_articulo}, tema={self.tema_principal})>"


# ============================================================================
# MODELO: Embedding Vectorial
# ============================================================================

class EmbeddingVectorial(Base):
    """Modelo para embeddings vectoriales de artículos"""
    __tablename__ = 'embeddings_vectoriales'
    
    id = Column(Integer, primary_key=True)
    articulo_id = Column(Integer, ForeignKey('articulos_normativos.id', ondelete='CASCADE'), nullable=False)
    
    # Modelo utilizado
    modelo_embedding = Column(String(100), nullable=False)
    dimension_vector = Column(Integer, nullable=False)
    
    # Vector
    embedding = Column(Vector(1536))  # Ajustar dimensión según modelo
    
    # Metadatos
    fecha_generacion = Column(DateTime, default=datetime.utcnow)
    version_modelo = Column(String(50))
    confianza_embedding = Column(Float)
    
    __table_args__ = (
        UniqueConstraint('articulo_id', 'modelo_embedding', name='uq_articulo_modelo'),
    )
    
    # Relaciones
    articulo = relationship("ArticuloNormativo", back_populates="embeddings")
    
    def __repr__(self):
        return f"<EmbeddingVectorial(articulo_id={self.articulo_id}, modelo={self.modelo_embedding}, dim={self.dimension_vector})>"


# ============================================================================
# MODELO: Sección de Etiqueta
# ============================================================================

class SeccionEtiqueta(Base):
    """Modelo para secciones estándar de etiquetas farmacéuticas"""
    __tablename__ = 'secciones_etiqueta'
    
    id = Column(Integer, primary_key=True)
    codigo = Column(String(50), unique=True, nullable=False)
    nombre_seccion = Column(String(200), nullable=False)
    descripcion = Column(Text)
    orden_visualizacion = Column(Integer)
    obligatoria = Column(Boolean, default=True)
    categoria = Column(String(50))
    activa = Column(Boolean, default=True)
    
    # Relaciones
    requisitos = relationship("RequisitoPorSeccion", back_populates="seccion")
    
    def __repr__(self):
        return f"<SeccionEtiqueta(codigo={self.codigo}, nombre={self.nombre_seccion}, orden={self.orden_visualizacion})>"


# ============================================================================
# MODELO: Requisito por Sección
# ============================================================================

class RequisitoPorSeccion(Base):
    """Modelo para requisitos normativos por país y sección"""
    __tablename__ = 'requisitos_por_seccion'
    
    id = Column(Integer, primary_key=True)
    articulo_id = Column(Integer, ForeignKey('articulos_normativos.id', ondelete='CASCADE'), nullable=False)
    seccion_id = Column(Integer, ForeignKey('secciones_etiqueta.id', ondelete='CASCADE'), nullable=False)
    pais_id = Column(Integer, ForeignKey('paises.id', ondelete='CASCADE'), nullable=False)
    
    # Descripción
    requisito_texto = Column(Text, nullable=False)
    tipo_requisito = Column(String(50))  # obligatorio, opcional, condicional
    condiciones = Column(Text)
    
    # Prioridad
    nivel_restrictividad = Column(Integer)  # 1-5
    
    # Validación
    patron_validacion = Column(Text)
    ejemplo = Column(Text)
    
    # Auditoría
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('articulo_id', 'seccion_id', name='uq_articulo_seccion'),
        CheckConstraint("tipo_requisito IN ('obligatorio', 'opcional', 'condicional')", name='ck_tipo_requisito'),
        CheckConstraint("nivel_restrictividad BETWEEN 1 AND 5", name='ck_nivel_restrictividad'),
    )
    
    # Relaciones
    articulo = relationship("ArticuloNormativo", back_populates="requisitos")
    seccion = relationship("SeccionEtiqueta", back_populates="requisitos")
    pais = relationship("Pais", back_populates="requisitos")
    
    def __repr__(self):
        return f"<RequisitoPorSeccion(pais_id={self.pais_id}, seccion_id={self.seccion_id}, tipo={self.tipo_requisito})>"


# ============================================================================
# MODELO: Historial de Procesamiento
# ============================================================================

class HistorialProcesamiento(Base):
    """Modelo para log de etiquetas procesadas"""
    __tablename__ = 'historial_procesamiento'
    
    id = Column(Integer, primary_key=True)
    uuid_proceso = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True)
    
    # Información producto
    nombre_producto = Column(String(300))
    codigo_producto = Column(String(100))
    
    # Archivos
    archivo_entrada_path = Column(Text)
    archivo_salida_path = Column(Text)
    archivo_analisis_path = Column(Text)
    
    # Estado
    estado = Column(String(50), default='iniciado')
    fecha_inicio = Column(DateTime, default=datetime.utcnow)
    fecha_fin = Column(DateTime)
    tiempo_procesamiento_seg = Column(Integer)
    
    # Métricas
    num_secciones_procesadas = Column(Integer)
    num_articulos_recuperados = Column(Integer)
    
    # Usuario
    usuario_proceso = Column(String(100))
    
    # Errores
    errores_detectados = Column(ARRAY(Text))
    warnings = Column(ARRAY(Text))
    
    __table_args__ = (
        CheckConstraint("estado IN ('iniciado', 'procesando', 'completado', 'error')", name='ck_estado_proceso'),
    )
    
    # Relaciones
    metricas = relationship("MetricaCalidad", back_populates="proceso", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<HistorialProcesamiento(uuid={self.uuid_proceso}, producto={self.nombre_producto}, estado={self.estado})>"


# ============================================================================
# MODELO: Métrica de Calidad
# ============================================================================

class MetricaCalidad(Base):
    """Modelo para métricas de calidad de documentos generados"""
    __tablename__ = 'metricas_calidad'
    
    id = Column(Integer, primary_key=True)
    proceso_id = Column(Integer, ForeignKey('historial_procesamiento.id', ondelete='CASCADE'), nullable=False)
    
    # Métricas técnicas
    precision_segmentacion = Column(Float)
    relevancia_evidencia = Column(Float)
    tiempo_respuesta_seg = Column(Float)
    
    # Métricas de calidad
    concordancia_checklist = Column(Float)
    num_errores_factuales = Column(Integer, default=0)
    trazabilidad_completa = Column(Boolean)
    indice_flesch_kincaid = Column(Float)
    
    # Validación humana
    validado_por = Column(String(100))
    fecha_validacion = Column(DateTime)
    aprobado = Column(Boolean)
    comentarios_validacion = Column(Text)
    
    # Retrabajo
    requiere_retrabajo = Column(Boolean, default=False)
    porcentaje_modificaciones = Column(Float)
    
    fecha_registro = Column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    proceso = relationship("HistorialProcesamiento", back_populates="metricas")
    
    def __repr__(self):
        return f"<MetricaCalidad(proceso_id={self.proceso_id}, aprobado={self.aprobado}, validado_por={self.validado_por})>"


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def crear_todas_tablas(engine):
    """Crear todas las tablas en la base de datos"""
    Base.metadata.create_all(engine)
    print("✓ Todas las tablas creadas exitosamente")


def eliminar_todas_tablas(engine):
    """Eliminar todas las tablas (¡CUIDADO!)"""
    Base.metadata.drop_all(engine)
    print("✓ Todas las tablas eliminadas")


def obtener_info_tablas():
    """Obtener información sobre todas las tablas definidas"""
    tablas_info = []
    for table in Base.metadata.sorted_tables:
        tablas_info.append({
            'nombre': table.name,
            'num_columnas': len(table.columns),
            'columnas': [col.name for col in table.columns]
        })
    return tablas_info


if __name__ == "__main__":
    # Imprimir información de las tablas definidas
    print("="*80)
    print("AALabelPP - Modelos de Base de Datos")
    print("="*80)
    
    info_tablas = obtener_info_tablas()
    for tabla in info_tablas:
        print(f"\nTabla: {tabla['nombre']}")
        print(f"  Columnas ({tabla['num_columnas']}): {', '.join(tabla['columnas'])}")
    
    print("\n" + "="*80)
    print(f"Total de tablas definidas: {len(info_tablas)}")
    print("="*80)
