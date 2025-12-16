"""
AALabelPP - Configuración de Base de Datos
Gestión de conexiones y utilidades para PostgreSQL + pgvector

Fecha: 2025-12-14
Versión: 1.0
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURACIÓN DE BASE DE DATOS
# ============================================================================

class DatabaseConfig:
    """Configuración centralizada de base de datos"""
    
    # Configuración por defecto (desarrollo)
    DEFAULT_CONFIG = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'aalabelpp_db'),
        'username': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres'),
        'pool_size': int(os.getenv('DB_POOL_SIZE', '5')),
        'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', '10')),
        'pool_timeout': int(os.getenv('DB_POOL_TIMEOUT', '30')),
        'echo': os.getenv('DB_ECHO', 'False').lower() == 'true'
    }
    
    @classmethod
    def get_connection_string(cls, config=None):
        """Generar string de conexión PostgreSQL"""
        cfg = config or cls.DEFAULT_CONFIG
        return (
            f"postgresql://{cfg['username']}:{cfg['password']}@"
            f"{cfg['host']}:{cfg['port']}/{cfg['database']}"
        )
    
    @classmethod
    def get_connection_string_async(cls, config=None):
        """Generar string de conexión asíncrona (asyncpg)"""
        cfg = config or cls.DEFAULT_CONFIG
        return (
            f"postgresql+asyncpg://{cfg['username']}:{cfg['password']}@"
            f"{cfg['host']}:{cfg['port']}/{cfg['database']}"
        )


# ============================================================================
# MOTOR DE BASE DE DATOS
# ============================================================================

class DatabaseEngine:
    """Gestor del motor de base de datos"""
    
    _engine = None
    _session_factory = None
    _scoped_session = None
    
    @classmethod
    def initialize(cls, config=None, echo=False):
        """Inicializar el motor de base de datos"""
        if cls._engine is None:
            connection_string = DatabaseConfig.get_connection_string(config)
            
            cls._engine = create_engine(
                connection_string,
                poolclass=QueuePool,
                pool_size=config.get('pool_size', 5) if config else 5,
                max_overflow=config.get('max_overflow', 10) if config else 10,
                pool_timeout=config.get('pool_timeout', 30) if config else 30,
                echo=echo or (config.get('echo', False) if config else False),
                pool_pre_ping=True  # Verificar conexiones antes de usar
            )
            
            cls._session_factory = sessionmaker(bind=cls._engine)
            cls._scoped_session = scoped_session(cls._session_factory)
            
            logger.info("✓ Motor de base de datos inicializado correctamente")
        
        return cls._engine
    
    @classmethod
    def get_engine(cls):
        """Obtener el motor de base de datos"""
        if cls._engine is None:
            cls.initialize()
        return cls._engine
    
    @classmethod
    def get_session(cls):
        """Obtener una nueva sesión de base de datos"""
        if cls._session_factory is None:
            cls.initialize()
        return cls._session_factory()
    
    @classmethod
    def get_scoped_session(cls):
        """Obtener sesión thread-safe"""
        if cls._scoped_session is None:
            cls.initialize()
        return cls._scoped_session
    
    @classmethod
    def close(cls):
        """Cerrar todas las conexiones"""
        if cls._scoped_session:
            cls._scoped_session.remove()
        if cls._engine:
            cls._engine.dispose()
            cls._engine = None
            cls._session_factory = None
            cls._scoped_session = None
            logger.info("✓ Conexiones cerradas")


# ============================================================================
# CONTEXT MANAGER PARA SESIONES
# ============================================================================

@contextmanager
def get_db_session():
    """Context manager para sesiones de base de datos
    
    Uso:
        with get_db_session() as session:
            # Hacer operaciones con session
            session.query(...)
    """
    session = DatabaseEngine.get_session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error en sesión de base de datos: {str(e)}")
        raise
    finally:
        session.close()


# ============================================================================
# UTILIDADES DE INICIALIZACIÓN
# ============================================================================

def verificar_extension_pgvector(engine=None):
    """Verificar que la extensión pgvector está instalada"""
    if engine is None:
        engine = DatabaseEngine.get_engine()
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
            ))
            existe = result.scalar()
            
            if existe:
                logger.info("✓ Extensión pgvector detectada")
                return True
            else:
                logger.warning("⚠ Extensión pgvector NO detectada")
                return False
    except Exception as e:
        logger.error(f"Error verificando pgvector: {str(e)}")
        return False


def instalar_extension_pgvector(engine=None):
    """Instalar extensión pgvector (requiere permisos de superusuario)"""
    if engine is None:
        engine = DatabaseEngine.get_engine()
    
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
            conn.commit()
            logger.info("✓ Extensiones instaladas correctamente")
            return True
    except Exception as e:
        logger.error(f"Error instalando extensiones: {str(e)}")
        logger.error("Nota: Puede requerir permisos de superusuario PostgreSQL")
        return False


def crear_base_datos_completa(schema_path='database/schema.sql', engine=None):
    """Ejecutar el script SQL completo para crear todas las tablas"""
    if engine is None:
        engine = DatabaseEngine.get_engine()
    
    try:
        # Leer archivo SQL
        with open(schema_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # Ejecutar
        with engine.connect() as conn:
            # Dividir por comandos individuales
            commands = sql_script.split(';')
            for command in commands:
                command = command.strip()
                if command:
                    conn.execute(text(command))
            conn.commit()
        
        logger.info("✓ Base de datos creada completamente desde schema.sql")
        return True
        
    except FileNotFoundError:
        logger.error(f"Archivo schema.sql no encontrado en: {schema_path}")
        return False
    except Exception as e:
        logger.error(f"Error ejecutando schema.sql: {str(e)}")
        return False


def verificar_conexion(engine=None):
    """Verificar que la conexión a la base de datos funciona"""
    if engine is None:
        engine = DatabaseEngine.get_engine()
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            logger.info(f"✓ Conexión exitosa a PostgreSQL")
            logger.info(f"  Versión: {version}")
            return True
    except Exception as e:
        logger.error(f"✗ Error de conexión: {str(e)}")
        return False


def obtener_estadisticas_db(engine=None):
    """Obtener estadísticas de la base de datos"""
    if engine is None:
        engine = DatabaseEngine.get_engine()
    
    try:
        stats = {}
        
        with engine.connect() as conn:
            # Número de tablas
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """))
            stats['num_tablas'] = result.scalar()
            
            # Tamaño de la base de datos
            result = conn.execute(text("""
                SELECT pg_size_pretty(pg_database_size(current_database()))
            """))
            stats['tamano_db'] = result.scalar()
            
            # Número de conexiones activas
            result = conn.execute(text("""
                SELECT COUNT(*) FROM pg_stat_activity 
                WHERE datname = current_database()
            """))
            stats['conexiones_activas'] = result.scalar()
        
        return stats
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {str(e)}")
        return {}


# ============================================================================
# FUNCIONES DE SETUP INICIAL
# ============================================================================

def setup_database(config=None, schema_path='database/schema.sql'):
    """Setup completo de la base de datos
    
    Pasos:
    1. Inicializar motor
    2. Verificar conexión
    3. Instalar extensiones
    4. Crear tablas
    5. Verificar creación
    """
    logger.info("="*80)
    logger.info("INICIANDO SETUP DE BASE DE DATOS AALabelPP")
    logger.info("="*80)
    
    # 1. Inicializar motor
    logger.info("\n[1/5] Inicializando motor de base de datos...")
    engine = DatabaseEngine.initialize(config)
    
    # 2. Verificar conexión
    logger.info("\n[2/5] Verificando conexión...")
    if not verificar_conexion(engine):
        logger.error("✗ Setup cancelado: no se pudo conectar a la base de datos")
        return False
    
    # 3. Instalar extensiones
    logger.info("\n[3/5] Instalando extensiones (pgvector, uuid-ossp)...")
    if not instalar_extension_pgvector(engine):
        logger.warning("⚠ No se pudieron instalar extensiones automáticamente")
        logger.warning("  Ejecute manualmente: CREATE EXTENSION vector;")
    
    # 4. Crear tablas
    logger.info("\n[4/5] Creando tablas desde schema.sql...")
    if not crear_base_datos_completa(schema_path, engine):
        logger.error("✗ Error creando tablas")
        return False
    
    # 5. Verificar creación
    logger.info("\n[5/5] Verificando instalación...")
    stats = obtener_estadisticas_db(engine)
    if stats:
        logger.info(f"  • Tablas creadas: {stats.get('num_tablas', 'N/A')}")
        logger.info(f"  • Tamaño DB: {stats.get('tamano_db', 'N/A')}")
        logger.info(f"  • Conexiones activas: {stats.get('conexiones_activas', 'N/A')}")
    
    logger.info("\n" + "="*80)
    logger.info("✓ SETUP COMPLETADO EXITOSAMENTE")
    logger.info("="*80)
    
    return True


# ============================================================================
# CLI DE UTILIDADES
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        comando = sys.argv[1]
        
        if comando == "setup":
            # Setup completo
            setup_database()
            
        elif comando == "verify":
            # Solo verificar conexión
            DatabaseEngine.initialize()
            verificar_conexion()
            verificar_extension_pgvector()
            
        elif comando == "stats":
            # Mostrar estadísticas
            DatabaseEngine.initialize()
            stats = obtener_estadisticas_db()
            print("\nEstadísticas de Base de Datos:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
        
        else:
            print(f"Comando desconocido: {comando}")
            print("\nComandos disponibles:")
            print("  setup   - Setup completo de la base de datos")
            print("  verify  - Verificar conexión y extensiones")
            print("  stats   - Mostrar estadísticas")
    
    else:
        print("Uso: python db_config.py [comando]")
        print("\nComandos disponibles:")
        print("  setup   - Setup completo de la base de datos")
        print("  verify  - Verificar conexión y extensiones")
        print("  stats   - Mostrar estadísticas")
