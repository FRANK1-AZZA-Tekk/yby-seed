"""
Bayesian Teaching — Atualização de crenças com Teoria das Probabilidades

Responsabilidade:
- Modelar crenças como distribuições de probabilidade
- Atualizar crenças com feedback (Bayes)
- Convergir para estratégia ótima sem re-treinar modelo

Fórmula de Bayes:
Posterior = (Likelihood × Prior) / ((Likelihood × Prior) + ((1 - Likelihood) × (1 - Prior)))

Otimizações:
- Atualização online (não requer batch)
- Convergência rápida (5-10 iterações)
- Robusto a outliers (feedback ruidoso)

Licença: MIT
"""

from typing import Dict, Any, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BayesianTeaching:
    """
    Ensino Bayesiano para aprendizado contínuo.
    """
    
    def __init__(self):
        # Crenças iniciais (priors)
        self.beliefs: Dict[str, float] = {
            "backup_automation_success": 0.5,  # Incerteza inicial
            "notification_success": 0.5,
            "api_integration_success": 0.5
        }
    
    def update(self, belief_key: str, feedback: str, likelihood_success: float = 0.9):
        """
        Atualizar crença com feedback.
        
        Args:
            belief_key: Chave da crença (ex: "backup_automation_success")
            feedback: Feedback ("success" ou "error")
            likelihood_success: Probabilidade do feedback dado sucesso (0.9 = 90% confiável)
        
        Returns:
            Posterior atualizado
        """
        logger.info(f"🧮 Bayesian update: {belief_key} (feedback: {feedback})")
        
        # Obter prior
        prior = self.beliefs.get(belief_key, 0.5)
        
        # Calcular likelihood
        likelihood = likelihood_success if feedback == "success" else (1 - likelihood_success)
        
        # Calcular posterior (Bayes)
        numerator = likelihood * prior
        denominator = (likelihood * prior) + ((1 - likelihood) * (1 - prior))
        
        if denominator == 0:
            posterior = prior  # Evitar divisão por zero
        else:
            posterior = numerator / denominator
        
        # Atualizar crença
        self.beliefs[belief_key] = posterior
        
        logger.info(f"✅ {belief_key}: prior={prior:.2f}, likelihood={likelihood:.2f}, posterior={posterior:.2f}")
        
        return posterior
    
    def get_best_strategy(self, belief_keys: List[str]) -> str:
        """
        Obter melhor estratégia baseado nas crenças.
        
        Args:
            belief_keys: Lista de chaves de crenças (estratégias)
        
        Returns:
            Chave da melhor estratégia
        """
        best_key = max(belief_keys, key=lambda k: self.beliefs.get(k, 0.5))
        logger.info(f"🏆 Melhor estratégia: {best_key} (confidence: {self.beliefs[best_key]:.2f})")
        return best_key
    
    def converge(self, belief_key: str, target_confidence: float = 0.95, max_iterations: int = 20):
        """
        Simular convergência para confiança alvo.
        
        Args:
            belief_key: Chave da crença
            target_confidence: Confiança alvo (0.95 = 95%)
            max_iterations: Número máximo de iterações
        
        Returns:
            Número de iterações para convergir
        """
        logger.info(f"🧮 Simulando convergência: {belief_key} (target: {target_confidence:.2f})")
        
        iterations = 0
        
        while iterations < max_iterations:
            # Simular feedback positivo
            posterior = self.update(belief_key, "success", likelihood_success=0.9)
            iterations += 1
            
            # Verificar convergência
            if posterior >= target_confidence:
                logger.info(f"✅ Convergiu em {iterations} iterações (posterior: {posterior:.2f})")
                return iterations
        
        logger.warning(f"⚠️  Não convergiu em {max_iterations} iterações (posterior: {posterior:.2f})")
        return iterations
    
    def reset(self, belief_key: str = None):
        """
        Resetar crenças (para experimentos).
        
        Args:
            belief_key: Chave específica (None = resetar todas)
        """
        if belief_key:
            self.beliefs[belief_key] = 0.5
            logger.info(f"🔄 Crença resetada: {belief_key}")
        
        else:
            self.beliefs = {k: 0.5 for k in self.beliefs}
            logger.info("🔄 Todas as crenças resetadas")
    
    def get_all_beliefs(self) -> Dict[str, float]:
        """
        Obter todas as crenças.
        
        Returns:
            Dict com crenças
        """
        return self.beliefs.copy()


# Instância global
bayesian_teaching = BayesianTeaching()


if __name__ == "__main__":
    # Teste: Atualizar crença
    bayesian_teaching.update("backup_automation_success", "success")
    bayesian_teaching.update("backup_automation_success", "success")
    bayesian_teaching.update("backup_automation_success", "error")
    
    # Obter crenças
    beliefs = bayesian_teaching.get_all_beliefs()
    print(f"\n🧮 Crenças: {beliefs}")
    
    # Obter melhor estratégia
    best = bayesian_teaching.get_best_strategy([
        "backup_automation_success",
        "notification_success",
        "api_integration_success"
    ])
    print(f"\n🏆 Melhor estratégia: {best}")
    
    # Simular convergência
    iterations = bayesian_teaching.converge("notification_success", target_confidence=0.95)
    print(f"\n🧮 Convergência: {iterations} iterações")
