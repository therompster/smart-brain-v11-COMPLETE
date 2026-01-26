"""Routing service - assigns PARA domains to notes."""

from typing import Dict
from loguru import logger

from src.models.workflow_state import ClusterNote, RoutedNote
from src.llm.ollama_client import llm
from src.config import settings
from src.services.confidence_service import confidence_service
from src.services.question_service import question_service
from src.services.domain_service import domain_service


def _build_routing_prompt(cluster: ClusterNote, domains: list) -> str:
    """Build routing prompt with dynamic domains."""
    domain_list = "\n".join([f"- {d['path']}: {d['name']}" for d in domains])
    
    return f"""Assign this note to the correct PARA domain based on its content.

Available domains:
{domain_list}

Note:
Title: {cluster.title}
Content: {cluster.content[:500]}
Keywords: {', '.join(cluster.keywords)}

Output JSON:
{{
  "domain": "domain path",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}

Return ONLY the JSON."""


class RouteService:
    """Service for routing notes to PARA domains with confidence tracking."""
    
    def route(self, cluster: ClusterNote, ask_if_uncertain: bool = True) -> Dict[str, any]:
        """Route note to appropriate PARA domain."""
        logger.debug(f"Routing note: {cluster.title}")
        
        from src.services.threshold_service import threshold_service
        confidence_threshold = threshold_service.get('routing_confidence_min')
        
        domains = domain_service.get_all_domains()
        
        # Fallback if no domains
        if not domains:
            domain_service.ensure_default_domains()
            domains = domain_service.get_all_domains()
        
        keyword_match = self._keyword_match(cluster, domains)
        
        if keyword_match:
            keywords_str = " ".join(cluster.keywords)
            historical_conf = confidence_service.check_domain_confidence(
                keywords_str, 
                keyword_match["domain"]
            )
            keyword_match["confidence"] = max(keyword_match["confidence"], historical_conf)
        
        if keyword_match and keyword_match["confidence"] > 0.8:
            logger.info(f"High confidence routing: {keyword_match['domain']}")
            return keyword_match
        
        llm_match = self._llm_route(cluster, domains)
        
        if ask_if_uncertain and llm_match["confidence"] < confidence_threshold:
            logger.warning(f"Low confidence, asking clarification")
            
            question_id = question_service.ask_domain_clarification(
                cluster.title,
                cluster.content[:200],
                llm_match["domain"],
                llm_match["confidence"]
            )
            
            llm_match["needs_clarification"] = True
            llm_match["question_id"] = question_id
        
        return llm_match
    
    def _keyword_match(self, cluster: ClusterNote, domains: list) -> Dict[str, any]:
        """Match note to domain using learned keywords."""
        text = f"{cluster.title} {cluster.content} {' '.join(cluster.keywords)}".lower()
        
        scores = {}
        for domain in domains:
            if not domain['keywords']:
                continue
                
            match_count = sum(1 for kw in domain['keywords'] if kw in text)
            if match_count > 0:
                scores[domain['path']] = match_count / len(domain['keywords'])
        
        if not scores:
            return None
        
        best_domain = max(scores, key=scores.get)
        confidence = scores[best_domain]
        
        if confidence > 0.3:
            confidence = min(confidence * 2, 1.0)
        
        return {
            "domain": best_domain,
            "confidence": confidence,
            "reasoning": "Keyword matching"
        }
    
    def _llm_route(self, cluster: ClusterNote, domains: list) -> Dict[str, any]:
        """Route using LLM."""
        prompt = _build_routing_prompt(cluster, domains)
        
        try:
            response = llm.generate_json(prompt, task_type='routing')
            
            domain = response.get("domain", "personal")
            valid_domains = [d['path'] for d in domains]
            
            if domain not in valid_domains:
                logger.warning(f"Invalid domain '{domain}', defaulting to first domain")
                domain = valid_domains[0] if valid_domains else "personal"
            
            return {
                "domain": domain,
                "confidence": float(response.get("confidence", 0.7)),
                "reasoning": response.get("reasoning", "LLM classification")
            }
            
        except Exception as e:
            logger.error(f"LLM routing failed: {e}")
            return {
                "domain": domains[0]['path'] if domains else "personal",
                "confidence": 0.5,
                "reasoning": "Fallback due to error"
            }


# Global service instance
route_service = RouteService()
