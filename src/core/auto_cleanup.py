"""
Auto Cleanup — Auto-limpeza (deletar logs >30 dias)

Responsabilidade:
- Deletar logs antigos (>30 dias)
- Compactar banco de dados (VACUUM)
- Limpar cache (Redis)

Otimizações:
- Execução diária (cron job)
- Logs rotacionados (logrotate)
- Cache TTL (Redis expire)

Licença: MIT
"""

import os
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse, urlunparse

logger = logging.getLogger(__name__)


class AutoCleanup:
    """
    Auto-limpeza de logs e cache.
    """
    
    def __init__(self, log_dir: str = "/var/log/yby", db_url: str | None = None):
        """
        Inicializar cleanup.
        
        Args:
            log_dir: Diretório de logs
            db_url: URL do PostgreSQL
        """
        self.log_dir = Path(log_dir)
        if db_url is None:
            db_url = os.getenv("YBY_DATABASE_URL", "")
        self.db_url = db_url.strip()
    
    def cleanup_logs(self, max_age_days: int = 30):
        """
        Deletar logs antigos.
        
        Args:
            max_age_days: Idade máxima dos logs (dias)
        """
        logger.info(f"🧹 Limpando logs >{max_age_days} dias...")
        
        if not self.log_dir.exists():
            logger.warning(f"⚠️  Diretório de logs não existe: {self.log_dir}")
            return
        
        cutoff = datetime.now() - timedelta(days=max_age_days)
        deleted_count = 0
        
        for log_file in self.log_dir.glob("*.log"):
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            
            if mtime < cutoff:
                log_file.unlink()
                deleted_count += 1
                logger.debug(f"🗑️  Deletado: {log_file}")
        
        logger.info(f"✅ {deleted_count} logs deletados")
    
    def vacuum_database(self):
        """
        Compactar banco de dados (VACUUM).
        """
        logger.info("Executando VACUUM no PostgreSQL...")

        if not self.db_url:
            raise RuntimeError("defina YBY_DATABASE_URL (sem senha no código)")

        try:
            parsed = urlparse(self.db_url)
            if parsed.scheme not in {"postgresql", "postgres"} or not parsed.hostname:
                raise ValueError(f"URL PostgreSQL inválida: {self.db_url!r}")

            env = {"PATH": os.environ.get("PATH", "")}
            if parsed.password is not None:
                env["PGPASSWORD"] = unquote(parsed.password)

            user = unquote(parsed.username) if parsed.username else ""
            host = parsed.hostname
            port = f":{parsed.port}" if parsed.port else ""
            netloc = f"{user}@{host}{port}" if user else f"{host}{port}"
            clean_uri = urlunparse(
                ("postgresql", netloc, parsed.path or "/", parsed.params, parsed.query, "")
            )

            subprocess.run(
                ["psql", clean_uri, "-c", "VACUUM ANALYZE"],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            logger.info("✅ VACUUM executado")

        except Exception as e:
            logger.error(f"❌ Erro ao executar VACUUM: {e}")
    
    def cleanup_redis_cache(self, redis_host: str = "localhost", redis_port: int = 6379):
        """
        Limpar cache Redis (TTL expirado).
        
        Args:
            redis_host: Host do Redis
            redis_port: Porta do Redis
        """
        logger.info(f"🧹 Limpando cache Redis ({redis_host}:{redis_port})...")
        
        try:
            import redis
            
            r = redis.Redis(host=redis_host, port=redis_port, db=0, socket_timeout=5.0)

            # Redis remove chaves com TTL expirado automaticamente; evita DEBUG SLEEP bloqueante.
            info = r.info("stats")
            expired_keys = info.get("expired_keys", 0)
            evicted_keys = info.get("evicted_keys", 0)

            logger.info("✅ Cache Redis inspecionado: %s expiradas, %s evitadas", expired_keys, evicted_keys)
        
        except Exception as e:
            logger.error(f"❌ Erro ao limpar Redis: {e}")
    
    def run_all(self):
        """
        Executar todas as limpezas.
        """
        logger.info("🧹 Executando auto-limpeza completa...")
        
        self.cleanup_logs(max_age_days=30)
        self.vacuum_database()
        self.cleanup_redis_cache()
        
        logger.info("✅ Auto-limpeza concluída")


# Instância global
auto_cleanup = AutoCleanup()


if __name__ == "__main__":
    # Executar limpeza
    auto_cleanup.run_all()
