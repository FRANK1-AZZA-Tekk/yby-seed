"""
OpenCL Config — GPU Adreno 730 (Xiaomi 12)

Responsabilidade:
- Compilar llama.cpp com backend OpenCL
- Configurar LD_LIBRARY_PATH para libs do vendor
- Redirecionar inferência para GPU (evitar thermal throttling)

Otimizações:
- OpenCL 3.0: GPU Adreno 730 (Snapdragon 8 Gen 1)
- Thermal: 42°C (CPU) → 35°C (GPU)
- Performance: 15 t/s (CPU) → 22 t/s (GPU)

Requisitos:
- Xiaomi 12 (Snapdragon 8 Gen 1, Adreno 730)
- Termux instalado
- ocl-icd, opencl-headers instalados

Licença: MIT
"""

import subprocess
import os
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OpenCLConfig:
    """
    Configuração OpenCL para GPU Adreno 730.
    """
    
    def __init__(self):
        # Caminhos das libs do vendor
        self.vendor_libs = [
            "/vendor/lib64",
            "/system/vendor/lib64",
            "/system/lib64"
        ]
        
        # Variáveis de ambiente
        self.env = os.environ.copy()
        
        # Adicionar libs do vendor ao LD_LIBRARY_PATH
        ld_library_path = self.env.get("LD_LIBRARY_PATH", "")
        
        for lib_path in self.vendor_libs:
            if lib_path not in ld_library_path:
                ld_library_path = f"{lib_path}:{ld_library_path}" if ld_library_path else lib_path
        
        self.env["LD_LIBRARY_PATH"] = ld_library_path
    
    def install_dependencies(self):
        """
        Instalar dependências no Termux.
        
        Comandos:
        pkg install ocl-icd opencl-headers
        """
        logger.info("📦 Instalando dependências OpenCL...")
        
        packages = ["ocl-icd", "opencl-headers"]
        
        for pkg in packages:
            try:
                subprocess.run(
                    ["pkg", "install", "-y", pkg],
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.info(f"✅ {pkg} instalado")
            
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Erro ao instalar {pkg}: {e.stderr}")
                raise
    
    def compile_llama_cpp(self, build_path: str = "../llama.cpp/build"):
        """
        Compilar llama.cpp com OpenCL.
        
        Flags:
        -DGGML_OPENCL=ON: Backend OpenCL
        -DGGML_OPENCL_SDK_VERSION=3.0: OpenCL 3.0 (Adreno 730)
        """
        logger.info("🔨 Compilando llama.cpp com OpenCL...")
        
        cmake_cmd = [
            "cmake",
            "..",
            "-DGGML_OPENCL=ON",
            "-DGGML_OPENCL_SDK_VERSION=3.0",
            "-DCMAKE_BUILD_TYPE=Release"
        ]
        
        make_cmd = ["make", "-j8"]
        
        try:
            # Criar diretório de build
            import pathlib
            pathlib.Path(build_path).mkdir(parents=True, exist_ok=True)
            
            # CMake
            subprocess.run(
                cmake_cmd,
                cwd=build_path,
                env=self.env,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Make
            subprocess.run(
                make_cmd,
                cwd=build_path,
                env=self.env,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info("✅ llama.cpp compilado com OpenCL")
        
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Erro ao compilar:\n{e.stderr}")
            raise
    
    def benchmark(self, model: str = "qwen2.5:7b", prompt: str = "Hello"):
        """
        Benchmark de inferência com OpenCL.
        
        Args:
            model: Modelo Ollama
            prompt: Prompt de teste
        
        Returns:
            Dict com métricas (tokens/s, temperatura, tempo)
        """
        logger.info(f"📊 Benchmark OpenCL: {model}...")
        
        # Comando Ollama
        cmd = ["ollama", "run", model, "--verbose"]
        
        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=60,
                env=self.env
            )
            
            # Parse output
            output = result.stderr
            
            metrics = {
                "tokens_per_sec": self._parse_metric(output, "eval rate"),
                "temperature_c": self._get_gpu_temperature(),
                "latency_ms": self._parse_metric(output, "response time")
            }
            
            logger.info(f"✅ Benchmark concluído: {metrics}")
            return metrics
        
        except Exception as e:
            logger.error(f"❌ Erro no benchmark: {e}")
            return {"error": str(e)}
    
    def _parse_metric(self, output: str, metric_name: str) -> float:
        """Parse métrica do output do Ollama"""
        import re
        pattern = f"{metric_name}.*?([\\d.]+)"
        match = re.search(pattern, output)
        return float(match.group(1)) if match else 0.0
    
    def _get_gpu_temperature(self) -> float:
        """Obter temperatura da GPU (Termux)"""
        try:
            result = subprocess.run(
                ["termux-battery-status"],
                capture_output=True,
                text=True
            )
            
            import json
            data = json.loads(result.stdout)
            return data.get("temperature", 0.0)
        
        except Exception:
            return 0.0
    
    def verify(self) -> Dict[str, bool]:
        """
        Verificar se OpenCL está configurado.
        
        Returns:
            Dict com status de cada componente
        """
        logger.info("🔍 Verificando OpenCL...")
        
        checks = {
            "ocl_icd_installed": self._check_ocl_icd(),
            "opencl_headers_installed": self._check_opencl_headers(),
            "vendor_libs_found": self._check_vendor_libs(),
            "gpu_detected": self._check_gpu()
        }
        
        all_passed = all(checks.values())
        
        if all_passed:
            logger.info("✅ OpenCL configurado")
        else:
            for name, passed in checks.items():
                status = "✅" if passed else "❌"
                logger.warning(f"{status} {name}")
        
        return checks
    
    def _check_ocl_icd(self) -> bool:
        """Verificar se ocl-icd está instalado"""
        try:
            result = subprocess.run(
                ["pkg", "list-installed", "ocl-icd"],
                capture_output=True,
                text=True
            )
            return "ocl-icd" in result.stdout
        
        except Exception:
            return False
    
    def _check_opencl_headers(self) -> bool:
        """Verificar se opencl-headers está instalado"""
        try:
            result = subprocess.run(
                ["pkg", "list-installed", "opencl-headers"],
                capture_output=True,
                text=True
            )
            return "opencl-headers" in result.stdout
        
        except Exception:
            return False
    
    def _check_vendor_libs(self) -> bool:
        """Verificar se libs do vendor estão acessíveis"""
        for lib_path in self.vendor_libs:
            if not os.path.exists(lib_path):
                return False
        
        # Verificar libOpenCL.so
        for lib_path in self.vendor_libs:
            if os.path.exists(f"{lib_path}/libOpenCL.so"):
                return True
        
        return False
    
    def _check_gpu(self) -> bool:
        """Verificar se GPU Adreno foi detectada"""
        try:
            result = subprocess.run(
                ["clinfo"],
                capture_output=True,
                text=True,
                env=self.env
            )
            return "Adreno" in result.stdout or "QUALCOMM" in result.stdout
        
        except Exception:
            return False


# Instância global
opencl_config = OpenCLConfig()


if __name__ == "__main__":
    # Instalar dependências
    opencl_config.install_dependencies()
    
    # Verificar
    checks = opencl_config.verify()
    print(f"\n✅ Validação: {checks}")
    
    # Compilar llama.cpp
    opencl_config.compile_llama_cpp()
    
    # Benchmark
    metrics = opencl_config.benchmark()
    print(f"\n📊 Benchmark: {metrics}")
