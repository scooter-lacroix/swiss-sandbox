"""
Caching implementation for task plan templates.
"""

import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from .interfaces import TaskPlanCacheInterface
from .models import TaskPlanTemplate, CacheStats
from ..planner.models import TaskPlan


class TaskPlanCache(TaskPlanCacheInterface):
    """Cache for task plan templates with similarity matching."""
    
    def __init__(self, cache_dir: str, max_templates: int = 500, default_ttl: int = 7200):
        """
        Initialize the task plan cache.
        
        Args:
            cache_dir: Directory for cache storage
            max_templates: Maximum number of cached templates
            default_ttl: Default time to live in seconds
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_templates = max_templates
        self.default_ttl = default_ttl
        
        # In-memory cache for templates
        self._templates: Dict[str, TaskPlanTemplate] = {}
        
        # Statistics
        self._stats = CacheStats()
        
        # Load existing templates from disk
        self._load_templates()
    
    def _load_templates(self) -> None:
        """Load templates from disk."""
        templates_file = self.cache_dir / "templates.json"
        if templates_file.exists():
            try:
                with open(templates_file, 'r') as f:
                    templates_data = json.load(f)
                
                for template_key, template_info in templates_data.items():
                    # Load the actual template
                    template_file = self.cache_dir / f"{template_key}.pkl"
                    if template_file.exists():
                        try:
                            with open(template_file, 'rb') as f:
                                template = pickle.load(f)
                            
                            self._templates[template_key] = template
                            self._stats.total_entries += 1
                        except Exception:
                            # Remove corrupted template
                            template_file.unlink(missing_ok=True)
            except Exception:
                # If templates file is corrupted, start fresh
                pass
    
    def _save_templates_index(self) -> None:
        """Save templates index to disk."""
        templates_file = self.cache_dir / "templates.json"
        templates_data = {}
        
        for template_key, template in self._templates.items():
            templates_data[template_key] = {
                "usage_count": template.usage_count,
                "success_count": template.success_count,
                "created_at": template.created_at.isoformat(),
                "last_used": template.last_used.isoformat() if template.last_used else None,
                "similarity_threshold": template.similarity_threshold,
                "success_rate": template.success_rate
            }
        
        try:
            with open(templates_file, 'w') as f:
                json.dump(templates_data, f, indent=2)
        except Exception:
            pass  # Fail silently for index save errors
    
    def _extract_project_characteristics(self, plan: TaskPlan) -> Dict[str, Any]:
        """Extract characteristics from a task plan for similarity matching."""
        if not plan.codebase_context or not plan.codebase_context.analysis:
            return {}
        
        analysis = plan.codebase_context.analysis
        
        characteristics = {
            "languages": sorted(analysis.structure.languages),
            "frameworks": sorted(analysis.structure.frameworks),
            "task_count": len(plan.tasks),
            "has_tests": len(analysis.structure.test_directories) > 0,
            "patterns": [p.name for p in analysis.patterns[:5]],  # Top 5 patterns
            "complexity_level": self._categorize_complexity(analysis.metrics),
            "project_size": self._categorize_project_size(analysis.metrics)
        }
        
        return characteristics
    
    def _categorize_complexity(self, metrics) -> str:
        """Categorize project complexity based on metrics."""
        if metrics.cyclomatic_complexity > 20:
            return "high"
        elif metrics.cyclomatic_complexity > 10:
            return "medium"
        else:
            return "low"
    
    def _categorize_project_size(self, metrics) -> str:
        """Categorize project size based on lines of code."""
        if metrics.lines_of_code > 50000:
            return "large"
        elif metrics.lines_of_code > 10000:
            return "medium"
        else:
            return "small"
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache."""
        template = self._templates.get(key)
        if template is None:
            self._stats.miss_count += 1
            return None
        
        self._stats.hit_count += 1
        return template.plan
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in the cache."""
        # This method is not typically used directly for task plans
        # Use cache_plan_template instead
        return False
    
    def delete(self, key: str) -> bool:
        """Delete a template from the cache."""
        if key in self._templates:
            del self._templates[key]
            self._stats.total_entries = len(self._templates)
            
            # Remove from disk
            template_file = self.cache_dir / f"{key}.pkl"
            template_file.unlink(missing_ok=True)
            
            self._save_templates_index()
            return True
        
        return False
    
    def clear(self) -> bool:
        """Clear all cached templates."""
        self._templates.clear()
        self._stats = CacheStats()
        
        # Clear disk cache
        for file_path in self.cache_dir.glob("*.pkl"):
            file_path.unlink(missing_ok=True)
        
        templates_file = self.cache_dir / "templates.json"
        templates_file.unlink(missing_ok=True)
        
        return True
    
    def exists(self, key: str) -> bool:
        """Check if a template exists in the cache."""
        return key in self._templates
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        memory_usage = sum(
            len(pickle.dumps(template)) for template in self._templates.values()
        )
        
        return {
            "total_entries": self._stats.total_entries,
            "hit_count": self._stats.hit_count,
            "miss_count": self._stats.miss_count,
            "hit_rate": self._stats.hit_rate,
            "memory_usage_bytes": memory_usage,
            "cache_type": "task_plans"
        }
    
    def cache_plan_template(self, template_key: str, plan: TaskPlan,
                           similarity_threshold: float = 0.8) -> bool:
        """Cache a task plan as a template for similar projects."""
        project_characteristics = self._extract_project_characteristics(plan)
        
        template = TaskPlanTemplate(
            template_key=template_key,
            plan=plan,
            project_characteristics=project_characteristics,
            similarity_threshold=similarity_threshold
        )
        
        # Enforce max templates limit
        if len(self._templates) >= self.max_templates:
            self._evict_least_successful_template()
        
        self._templates[template_key] = template
        self._stats.total_entries = len(self._templates)
        
        # Save to disk
        self._save_template_to_disk(template_key, template)
        self._save_templates_index()
        
        return True
    
    def find_similar_templates(self, project_characteristics: Dict[str, Any],
                              max_results: int = 5) -> List[Tuple[str, TaskPlan, float]]:
        """Find similar task plan templates."""
        similarities = []
        
        for template_key, template in self._templates.items():
            similarity = template.calculate_similarity(project_characteristics)
            
            if similarity >= template.similarity_threshold:
                similarities.append((template_key, template.plan, similarity))
        
        # Sort by similarity score (descending) and success rate
        similarities.sort(key=lambda x: (x[2], self._templates[x[0]].success_rate), reverse=True)
        
        return similarities[:max_results]
    
    def get_plan_template(self, template_key: str) -> Optional[TaskPlan]:
        """Get a specific task plan template."""
        template = self._templates.get(template_key)
        if template:
            self._stats.hit_count += 1
            return template.plan
        
        self._stats.miss_count += 1
        return None
    
    def update_template_usage(self, template_key: str, success: bool) -> bool:
        """Update template usage statistics."""
        template = self._templates.get(template_key)
        if template is None:
            return False
        
        template.usage_count += 1
        template.last_used = datetime.now()
        
        if success:
            template.success_count += 1
        
        # Save updated statistics
        self._save_templates_index()
        
        return True
    
    def _save_template_to_disk(self, template_key: str, template: TaskPlanTemplate) -> None:
        """Save a template to disk."""
        template_file = self.cache_dir / f"{template_key}.pkl"
        try:
            with open(template_file, 'wb') as f:
                pickle.dump(template, f)
        except Exception:
            pass  # Fail silently for disk save errors
    
    def _evict_least_successful_template(self) -> None:
        """Evict the template with the lowest success rate."""
        if not self._templates:
            return
        
        # Find template with lowest success rate (and lowest usage if tied)
        worst_template_key = min(
            self._templates.keys(),
            key=lambda k: (
                self._templates[k].success_rate,
                self._templates[k].usage_count,
                self._templates[k].last_used or datetime.min
            )
        )
        
        self.delete(worst_template_key)
        self._stats.eviction_count += 1
    
    def cleanup_expired(self) -> int:
        """Clean up expired templates (not applicable for task plans)."""
        # Task plan templates don't expire based on time
        # Instead, we clean up templates with very low success rates
        
        low_success_templates = [
            key for key, template in self._templates.items()
            if template.usage_count >= 5 and template.success_rate < 0.2
        ]
        
        for key in low_success_templates:
            self.delete(key)
        
        return len(low_success_templates)
    
    def evict_lru_entries(self, count: int) -> int:
        """Evict a specific number of least successful templates."""
        evicted = 0
        
        while evicted < count and self._templates:
            self._evict_least_successful_template()
            evicted += 1
        
        return evicted
    
    def get_template_analytics(self) -> Dict[str, Any]:
        """Get analytics about template usage and success rates."""
        if not self._templates:
            return {"total_templates": 0}
        
        success_rates = [t.success_rate for t in self._templates.values()]
        usage_counts = [t.usage_count for t in self._templates.values()]
        
        return {
            "total_templates": len(self._templates),
            "avg_success_rate": sum(success_rates) / len(success_rates),
            "avg_usage_count": sum(usage_counts) / len(usage_counts),
            "most_successful_template": max(
                self._templates.items(),
                key=lambda x: x[1].success_rate
            )[0] if self._templates else None,
            "most_used_template": max(
                self._templates.items(),
                key=lambda x: x[1].usage_count
            )[0] if self._templates else None
        }