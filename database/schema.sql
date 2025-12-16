-- ============================================================================
-- AALabelPP - Esquema de Base de Datos
-- Sistema de Gestión de Normativas Farmacéuticas con Búsqueda Vectorial
-- ============================================================================
-- Fecha: 2025-12-14
-- Versión: 1.0
-- PostgreSQL 14+ con extensión pgvector
-- ============================================================================

-- Habilitar extensión para búsqueda vectorial
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- TABLA 1: PAÍSES
-- ============================================================================
-- Catálogo de países de la zona andina incluidos en el sistema

CREATE TABLE paises (
    id SERIAL PRIMARY KEY,
    codigo_iso CHAR(2) UNIQUE NOT NULL,  -- CO, EC, PE, BO
    nombre VARCHAR(100) NOT NULL,
    nombre_oficial VARCHAR(200),
    autoridad_sanitaria VARCHAR(200),     -- INVIMA, ARCSA, DIGEMID, AGEMED
    acronimo_autoridad VARCHAR(20),
    activo BOOLEAN DEFAULT true,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices
CREATE INDEX idx_paises_codigo ON paises(codigo_iso);
CREATE INDEX idx_paises_activo ON paises(activo);

-- Datos iniciales
INSERT INTO paises (codigo_iso, nombre, nombre_oficial, autoridad_sanitaria, acronimo_autoridad) VALUES
    ('CO', 'Colombia', 'República de Colombia', 
     'Instituto Nacional de Vigilancia de Medicamentos y Alimentos', 'INVIMA'),
    ('EC', 'Ecuador', 'República del Ecuador', 
     'Agencia Nacional de Regulación, Control y Vigilancia Sanitaria', 'ARCSA'),
    ('PE', 'Perú', 'República del Perú', 
     'Dirección General de Medicamentos, Insumos y Drogas', 'DIGEMID'),
    ('BO', 'Bolivia', 'Estado Plurinacional de Bolivia', 
     'Agencia Estatal de Medicamentos y Tecnologías en Salud', 'AGEMED');

-- ============================================================================
-- TABLA 2: DOCUMENTOS_NORMATIVOS
-- ============================================================================
-- Registro de normativas oficiales (decretos, resoluciones, acuerdos)

CREATE TABLE documentos_normativos (
    id SERIAL PRIMARY KEY,
    pais_id INTEGER REFERENCES paises(id) ON DELETE CASCADE,
    
    -- Identificación del documento
    tipo_documento VARCHAR(50) NOT NULL,   -- Decreto, Resolución, Acuerdo, Manual
    numero_documento VARCHAR(100) NOT NULL,
    titulo TEXT NOT NULL,
    
    -- Información oficial
    fecha_publicacion DATE,
    fecha_vigencia DATE,
    diario_oficial VARCHAR(200),           -- Ej: Diario Oficial 41827
    estado VARCHAR(20) DEFAULT 'vigente',  -- vigente, derogado, modificado
    
    -- Ubicación del documento
    url_oficial TEXT,                      -- URL fuente oficial
    ruta_archivo_pdf TEXT,                 -- Ruta local del PDF
    hash_archivo VARCHAR(64),              -- SHA-256 del archivo
    
    -- Metadatos de contenido
    descripcion TEXT,
    ambito_aplicacion TEXT,                -- Medicamentos, Dispositivos, etc.
    num_articulos INTEGER,
    num_paginas INTEGER,
    
    -- Control de versiones
    version INTEGER DEFAULT 1,
    documento_padre_id INTEGER REFERENCES documentos_normativos(id),
    notas_version TEXT,
    
    -- Auditoría
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    usuario_creacion VARCHAR(100),
    
    -- Constraint único
    UNIQUE(pais_id, numero_documento, version)
);

-- Índices
CREATE INDEX idx_docs_pais ON documentos_normativos(pais_id);
CREATE INDEX idx_docs_tipo ON documentos_normativos(tipo_documento);
CREATE INDEX idx_docs_estado ON documentos_normativos(estado);
CREATE INDEX idx_docs_vigencia ON documentos_normativos(fecha_vigencia);
CREATE INDEX idx_docs_hash ON documentos_normativos(hash_archivo);

-- ============================================================================
-- TABLA 3: ARTICULOS_NORMATIVOS
-- ============================================================================
-- Fragmentación de documentos en artículos/secciones específicas

CREATE TABLE articulos_normativos (
    id SERIAL PRIMARY KEY,
    documento_id INTEGER REFERENCES documentos_normativos(id) ON DELETE CASCADE,
    
    -- Identificación del artículo
    numero_articulo VARCHAR(50),           -- "Art. 72", "Sección 3.1"
    titulo_articulo TEXT,
    
    -- Jerarquía dentro del documento
    capitulo VARCHAR(100),
    seccion VARCHAR(100),
    subseccion VARCHAR(100),
    orden_jerarquico INTEGER,              -- Para ordenamiento
    
    -- Contenido
    texto_completo TEXT NOT NULL,
    texto_normalizado TEXT,                -- Limpio, sin formato
    num_palabras INTEGER,
    
    -- Clasificación semántica
    tema_principal VARCHAR(100),           -- Etiquetado, Composición, Advertencias
    temas_relacionados TEXT[],             -- Array de temas secundarios
    
    -- Referencias cruzadas
    articulos_relacionados INTEGER[],      -- Array de IDs de artículos relacionados
    
    -- Auditoría
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices
CREATE INDEX idx_articulos_doc ON articulos_normativos(documento_id);
CREATE INDEX idx_articulos_num ON articulos_normativos(numero_articulo);
CREATE INDEX idx_articulos_tema ON articulos_normativos(tema_principal);
CREATE INDEX idx_articulos_orden ON articulos_normativos(orden_jerarquico);

-- Índice GIN para búsqueda en arrays
CREATE INDEX idx_articulos_temas_array ON articulos_normativos USING GIN(temas_relacionados);

-- ============================================================================
-- TABLA 4: EMBEDDINGS_VECTORIALES
-- ============================================================================
-- Representaciones vectoriales de artículos para búsqueda semántica

CREATE TABLE embeddings_vectoriales (
    id SERIAL PRIMARY KEY,
    articulo_id INTEGER REFERENCES articulos_normativos(id) ON DELETE CASCADE,
    
    -- Modelo de embeddings utilizado
    modelo_embedding VARCHAR(100) NOT NULL,  -- sentence-transformers, openai-ada-002
    dimension_vector INTEGER NOT NULL,        -- 384, 768, 1536, etc.
    
    -- Vector de representación
    embedding vector(1536),                   -- Ajustar dimensión según modelo
    
    -- Metadatos del embedding
    fecha_generacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version_modelo VARCHAR(50),
    
    -- Métricas de calidad
    confianza_embedding FLOAT,
    
    UNIQUE(articulo_id, modelo_embedding)
);

-- Índice HNSW para búsqueda de vecinos más cercanos (FAST)
CREATE INDEX idx_embeddings_hnsw ON embeddings_vectoriales 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Índice IVFFlat alternativo (menos memoria)
CREATE INDEX idx_embeddings_ivfflat ON embeddings_vectoriales 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX idx_embeddings_articulo ON embeddings_vectoriales(articulo_id);
CREATE INDEX idx_embeddings_modelo ON embeddings_vectoriales(modelo_embedding);

-- ============================================================================
-- TABLA 5: SECCIONES_ETIQUETA
-- ============================================================================
-- Catálogo de secciones estándar de etiquetas farmacéuticas

CREATE TABLE secciones_etiqueta (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,    -- NOMBRE, COMPOSICION, INDICACIONES
    nombre_seccion VARCHAR(200) NOT NULL,
    descripcion TEXT,
    orden_visualizacion INTEGER,
    obligatoria BOOLEAN DEFAULT true,
    categoria VARCHAR(50),                  -- Identificación, Información Técnica, Advertencias
    activa BOOLEAN DEFAULT true
);

-- Datos iniciales de secciones
INSERT INTO secciones_etiqueta (codigo, nombre_seccion, descripcion, orden_visualizacion, categoria) VALUES
    ('NOMBRE', 'Denominación del Producto', 'Nombre comercial y DCI', 1, 'Identificación'),
    ('COMPOSICION', 'Composición Cuali-Cuantitativa', 'Principios activos y excipientes', 2, 'Identificación'),
    ('FORMA_FARMACEUTICA', 'Forma Farmacéutica', 'Presentación física del medicamento', 3, 'Identificación'),
    ('INDICACIONES', 'Indicaciones Terapéuticas', 'Usos aprobados del medicamento', 4, 'Información Técnica'),
    ('CONTRAINDICACIONES', 'Contraindicaciones', 'Situaciones donde no debe usarse', 5, 'Advertencias'),
    ('ADVERTENCIAS', 'Advertencias y Precauciones', 'Información de seguridad', 6, 'Advertencias'),
    ('INTERACCIONES', 'Interacciones Medicamentosas', 'Interacciones con otros fármacos', 7, 'Información Técnica'),
    ('POSOLOGIA', 'Posología y Vía de Administración', 'Dosis y forma de uso', 8, 'Información Técnica'),
    ('REACCIONES_ADVERSAS', 'Reacciones Adversas', 'Efectos secundarios conocidos', 9, 'Advertencias'),
    ('SOBREDOSIS', 'Sobredosis', 'Manejo de intoxicación', 10, 'Advertencias'),
    ('ALMACENAMIENTO', 'Condiciones de Almacenamiento', 'Conservación del producto', 11, 'Información Técnica'),
    ('PRESENTACION', 'Presentación Comercial', 'Formato de venta', 12, 'Identificación'),
    ('FABRICANTE', 'Fabricante y Titular', 'Datos del responsable', 13, 'Identificación');

-- ============================================================================
-- TABLA 6: REQUISITOS_POR_SECCION
-- ============================================================================
-- Requisitos normativos específicos por país y sección de etiqueta

CREATE TABLE requisitos_por_seccion (
    id SERIAL PRIMARY KEY,
    articulo_id INTEGER REFERENCES articulos_normativos(id) ON DELETE CASCADE,
    seccion_id INTEGER REFERENCES secciones_etiqueta(id) ON DELETE CASCADE,
    pais_id INTEGER REFERENCES paises(id) ON DELETE CASCADE,
    
    -- Descripción del requisito
    requisito_texto TEXT NOT NULL,
    tipo_requisito VARCHAR(50),            -- obligatorio, opcional, condicional
    condiciones TEXT,                      -- Si es condicional, bajo qué condiciones
    
    -- Prioridad para armonización
    nivel_restrictividad INTEGER,         -- 1-5, donde 5 es más restrictivo
    
    -- Validación
    patron_validacion TEXT,               -- Regex o patrón de validación
    ejemplo TEXT,
    
    -- Auditoría
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(articulo_id, seccion_id)
);

CREATE INDEX idx_requisitos_seccion ON requisitos_por_seccion(seccion_id);
CREATE INDEX idx_requisitos_pais ON requisitos_por_seccion(pais_id);
CREATE INDEX idx_requisitos_tipo ON requisitos_por_seccion(tipo_requisito);

-- ============================================================================
-- TABLA 7: HISTORIAL_PROCESAMIENTO
-- ============================================================================
-- Log de etiquetas procesadas por el sistema

CREATE TABLE historial_procesamiento (
    id SERIAL PRIMARY KEY,
    uuid_proceso UUID DEFAULT uuid_generate_v4() UNIQUE,
    
    -- Información del producto
    nombre_producto VARCHAR(300),
    codigo_producto VARCHAR(100),
    
    -- Archivos
    archivo_entrada_path TEXT,
    archivo_salida_path TEXT,
    archivo_analisis_path TEXT,
    
    -- Estado del procesamiento
    estado VARCHAR(50) DEFAULT 'iniciado',  -- iniciado, procesando, completado, error
    fecha_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_fin TIMESTAMP,
    tiempo_procesamiento_seg INTEGER,
    
    -- Métricas
    num_secciones_procesadas INTEGER,
    num_articulos_recuperados INTEGER,
    
    -- Usuario
    usuario_proceso VARCHAR(100),
    
    -- Errores
    errores_detectados TEXT[],
    warnings TEXT[]
);

CREATE INDEX idx_historial_uuid ON historial_procesamiento(uuid_proceso);
CREATE INDEX idx_historial_estado ON historial_procesamiento(estado);
CREATE INDEX idx_historial_fecha ON historial_procesamiento(fecha_inicio);
CREATE INDEX idx_historial_usuario ON historial_procesamiento(usuario_proceso);

-- ============================================================================
-- TABLA 8: METRICAS_CALIDAD
-- ============================================================================
-- Métricas de calidad y validación de documentos generados

CREATE TABLE metricas_calidad (
    id SERIAL PRIMARY KEY,
    proceso_id INTEGER REFERENCES historial_procesamiento(id) ON DELETE CASCADE,
    
    -- Métricas técnicas
    precision_segmentacion FLOAT,
    relevancia_evidencia FLOAT,
    tiempo_respuesta_seg FLOAT,
    
    -- Métricas de calidad
    concordancia_checklist FLOAT,
    num_errores_factuales INTEGER DEFAULT 0,
    trazabilidad_completa BOOLEAN,
    indice_flesch_kincaid FLOAT,
    
    -- Validación humana
    validado_por VARCHAR(100),
    fecha_validacion TIMESTAMP,
    aprobado BOOLEAN,
    comentarios_validacion TEXT,
    
    -- Retrabajo
    requiere_retrabajo BOOLEAN DEFAULT false,
    porcentaje_modificaciones FLOAT,
    
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_metricas_proceso ON metricas_calidad(proceso_id);
CREATE INDEX idx_metricas_validado ON metricas_calidad(validado_por);
CREATE INDEX idx_metricas_aprobado ON metricas_calidad(aprobado);

-- ============================================================================
-- VISTAS ÚTILES
-- ============================================================================

-- Vista: Normativas vigentes por país
CREATE VIEW v_normativas_vigentes AS
SELECT 
    p.nombre as pais,
    p.acronimo_autoridad,
    dn.tipo_documento,
    dn.numero_documento,
    dn.titulo,
    dn.fecha_vigencia,
    dn.url_oficial,
    COUNT(an.id) as num_articulos
FROM documentos_normativos dn
JOIN paises p ON dn.pais_id = p.id
LEFT JOIN articulos_normativos an ON dn.id = an.documento_id
WHERE dn.estado = 'vigente'
GROUP BY p.nombre, p.acronimo_autoridad, dn.tipo_documento, 
         dn.numero_documento, dn.titulo, dn.fecha_vigencia, dn.url_oficial;

-- Vista: Requisitos por sección y país
CREATE VIEW v_requisitos_por_pais_seccion AS
SELECT 
    p.nombre as pais,
    se.nombre_seccion,
    se.codigo as codigo_seccion,
    COUNT(rps.id) as num_requisitos,
    SUM(CASE WHEN rps.tipo_requisito = 'obligatorio' THEN 1 ELSE 0 END) as requisitos_obligatorios,
    AVG(rps.nivel_restrictividad) as nivel_promedio_restrictividad
FROM paises p
CROSS JOIN secciones_etiqueta se
LEFT JOIN requisitos_por_seccion rps ON p.id = rps.pais_id AND se.id = rps.seccion_id
WHERE se.activa = true
GROUP BY p.nombre, se.nombre_seccion, se.codigo, se.orden_visualizacion
ORDER BY p.nombre, se.orden_visualizacion;

-- Vista: Estadísticas de procesamiento
CREATE VIEW v_estadisticas_procesamiento AS
SELECT 
    DATE(fecha_inicio) as fecha,
    COUNT(*) as total_procesos,
    SUM(CASE WHEN estado = 'completado' THEN 1 ELSE 0 END) as completados,
    SUM(CASE WHEN estado = 'error' THEN 1 ELSE 0 END) as con_errores,
    AVG(tiempo_procesamiento_seg) as tiempo_promedio_seg,
    AVG(num_articulos_recuperados) as articulos_promedio
FROM historial_procesamiento
GROUP BY DATE(fecha_inicio)
ORDER BY fecha DESC;

-- ============================================================================
-- FUNCIONES AUXILIARES
-- ============================================================================

-- Función para buscar artículos similares por embedding
CREATE OR REPLACE FUNCTION buscar_articulos_similares(
    query_embedding vector(1536),
    limite INTEGER DEFAULT 5,
    modelo VARCHAR(100) DEFAULT 'sentence-transformers'
)
RETURNS TABLE (
    articulo_id INTEGER,
    numero_articulo VARCHAR,
    texto_completo TEXT,
    pais VARCHAR,
    documento VARCHAR,
    similitud FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.id,
        a.numero_articulo,
        a.texto_completo,
        p.nombre,
        d.numero_documento,
        1 - (e.embedding <=> query_embedding) as similitud
    FROM embeddings_vectoriales e
    JOIN articulos_normativos a ON e.articulo_id = a.id
    JOIN documentos_normativos d ON a.documento_id = d.id
    JOIN paises p ON d.pais_id = p.id
    WHERE e.modelo_embedding = modelo
    ORDER BY e.embedding <=> query_embedding
    LIMIT limite;
END;
$$ LANGUAGE plpgsql;

-- Función para actualizar timestamp de modificación
CREATE OR REPLACE FUNCTION actualizar_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.fecha_actualizacion = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers para auto-actualizar timestamps
CREATE TRIGGER trigger_actualizar_paises
    BEFORE UPDATE ON paises
    FOR EACH ROW EXECUTE FUNCTION actualizar_timestamp();

CREATE TRIGGER trigger_actualizar_documentos
    BEFORE UPDATE ON documentos_normativos
    FOR EACH ROW EXECUTE FUNCTION actualizar_timestamp();

CREATE TRIGGER trigger_actualizar_articulos
    BEFORE UPDATE ON articulos_normativos
    FOR EACH ROW EXECUTE FUNCTION actualizar_timestamp();

-- ============================================================================
-- COMENTARIOS EN TABLAS Y COLUMNAS
-- ============================================================================

COMMENT ON TABLE paises IS 'Catálogo de países de la zona andina incluidos en AALabelPP';
COMMENT ON TABLE documentos_normativos IS 'Registro de normativas oficiales (decretos, resoluciones, acuerdos)';
COMMENT ON TABLE articulos_normativos IS 'Fragmentación de documentos normativos en artículos específicos';
COMMENT ON TABLE embeddings_vectoriales IS 'Representaciones vectoriales para búsqueda semántica RAG';
COMMENT ON TABLE secciones_etiqueta IS 'Catálogo de secciones estándar de etiquetas farmacéuticas';
COMMENT ON TABLE requisitos_por_seccion IS 'Requisitos normativos específicos por país y sección';
COMMENT ON TABLE historial_procesamiento IS 'Log de etiquetas procesadas por el sistema';
COMMENT ON TABLE metricas_calidad IS 'Métricas de calidad y validación de documentos generados';

-- ============================================================================
-- FIN DEL SCHEMA
-- ============================================================================
