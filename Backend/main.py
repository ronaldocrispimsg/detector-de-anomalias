import os
import signal
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from Backend.database import engine, async_engine, SessionLocal, wait_for_database
from Backend.models import Base, User
from Backend.monitor_engine import monitor_engine
from Backend.routes.hosts import router as hosts_router
from Backend.routes.health import router as health_router
from Backend.snmp_engine import reset_snmp_backoff
from Backend.security import hash_password
from Backend.mq_manager import mq_manager

logger = logging.getLogger("netspot.main")

# 1. Autocura PostgreSQL: aguarda a disponibilidade do DB antes de criar tabelas e admin
if wait_for_database(max_retries=3, delay_seconds=1.0):
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.error(f"Erro ao executar Base.metadata.create_all: {e}")
else:
    logger.warning("PostgreSQL não respondeu no tempo limite. Inicialização de tabelas diferida.")


def create_default_admin():
    try:
        db = SessionLocal()
        try:
            default_admin_password = os.getenv("NETSPOT_DEFAULT_ADMIN_PASSWORD")
            if not default_admin_password:
                logger.info("Banco de dados: NETSPOT_DEFAULT_ADMIN_PASSWORD não configurada. Usuário admin padrão não será criado.")
                return

            if not db.query(User).filter(User.username == "admin").first():
                novo_admin = User(
                    username="admin",
                    password_hash=hash_password(default_admin_password),
                    must_change_password=True
                )
                db.add(novo_admin)
                db.commit()
                logger.info("Banco de dados: usuário admin criado com sucesso!")
            else:
                logger.info("Banco de dados: usuário admin já existe.")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Não foi possível criar admin padrão (banco indisponível): {e}")


def setup_kathara_routes():
    """Configura automaticamente as rotas estáticas para as redes Kathará (10.0.0.0/16 e 100.0.0.0/16) ao iniciar."""
    import subprocess
    import ipaddress
    gateway = os.getenv("KATHARA_ROUTER_IP", "172.17.0.2").strip()
    subnets_raw = os.getenv("KATHARA_SUBNETS", "10.0.0.0/16,100.0.0.0/16")
    subnets = [s.strip() for s in subnets_raw.split(",") if s.strip()]

    # Validação sintática defensiva do gateway (evita comandos inválidos no sistema)
    try:
        ipaddress.ip_address(gateway)
    except ValueError:
        logger.warning(f"[KATHARA] Gateway inválido configurado em KATHARA_ROUTER_IP: '{gateway}'. Roteamento abortado.")
        return

    for subnet in subnets:
        # Validação sintática defensiva da sub-rede CIDR
        try:
            ipaddress.ip_network(subnet, strict=False)
        except ValueError:
            logger.warning(f"[KATHARA] Sub-rede inválida em KATHARA_SUBNETS: '{subnet}'. Ignorada.")
            continue

        try:
            res = subprocess.run(
                ["ip", "route", "replace", subnet, "via", gateway],
                capture_output=True,
                text=True
            )
            if res.returncode == 0:
                logger.info(f"[KATHARA] Rota estática configurada: {subnet} via {gateway}")
            else:
                logger.warning(f"[KATHARA] Aviso ao adicionar rota {subnet} via {gateway}: {res.stderr.strip()}")
        except Exception as e:
            logger.warning(f"[KATHARA] Não foi possível configurar rota para {subnet}: {e}")


# 5. Desligamento Gracioso (Graceful Shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Inicialização dos serviços e background tasks
    setup_kathara_routes()
    create_default_admin()
    reset_snmp_backoff()
    await mq_manager.connect()
    await mq_manager.start_consumers()
    await monitor_engine.start()


    try:
        yield
    finally:
        # Shutdown: Liberação sequencial e graciosa dos recursos
        logger.info("[SHUTDOWN] Iniciando procedimentos de Graceful Shutdown...")
        
        # 1. Para o loop do monitor de checagens
        try:
            await monitor_engine.stop()
            logger.info("[SHUTDOWN] MonitorEngine finalizado.")
        except Exception as e:
            logger.error(f"[SHUTDOWN] Erro ao parar MonitorEngine: {e}")

        # 2. Desconecta do RabbitMQ e cancela consumidores
        try:
            await mq_manager.close()
            logger.info("[SHUTDOWN] QueueManager finalizado.")
        except Exception as e:
            logger.error(f"[SHUTDOWN] Erro ao fechar QueueManager: {e}")

        # 3. Libera pools de conexão com o PostgreSQL
        try:
            await async_engine.dispose()
            engine.dispose()
            logger.info("[SHUTDOWN] Pool de conexões do SQLAlchemy descarregado.")
        except Exception as e:
            logger.error(f"[SHUTDOWN] Erro ao liberar engines do SQLAlchemy: {e}")

        logger.info("[SHUTDOWN] Graceful Shutdown concluído com sucesso.")


app = FastAPI(
    title="NetSpot NOC Lite API",
    description="Sistema de Monitoramento de Redes com Foco em Prevenção de Falhas",
    version="1.1.1",
    lifespan=lifespan
)

# 1. Registro de Rotas (Hosts & Healthcheck /healthz)
app.include_router(hosts_router)
app.include_router(health_router)

cors_origins_env = os.getenv("CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080,http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000")
allow_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)
