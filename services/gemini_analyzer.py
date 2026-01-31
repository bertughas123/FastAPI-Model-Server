"""
Gemini Analyzer - Backward Compatibility Facade

Bu dosya geriye dönük uyumluluk için korunmuştur.
Tüm mantık services/analyzer/ paketi altına taşınmıştır.

Yeni kod için doğrudan şunu kullanın:
    from services.analyzer import GeminiAnalyzerOrchestrator

Mevcut kod için bu alias'lar çalışmaya devam eder:
    from services.gemini_analyzer import gemini_analyzer
    from services.gemini_analyzer import GeminiAnalyzerRedis
    from services.gemini_analyzer import GeminiAnalyzer
"""

from services.analyzer import GeminiAnalyzerOrchestrator


# ═══════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY ALIASES
# Eski kod bu import'ları kullanıyorsa çalışmaya devam etsin
# ═══════════════════════════════════════════════════════════════════════════

# Yeni ana sınıf
GeminiAnalyzerRedis = GeminiAnalyzerOrchestrator

# Legacy alias (çok eski import'lar için)
GeminiAnalyzer = GeminiAnalyzerOrchestrator


# ═══════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# routes/analytics.py ve diğer dosyalar bunu kullanıyor
# ═══════════════════════════════════════════════════════════════════════════

gemini_analyzer = GeminiAnalyzerOrchestrator()


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    'gemini_analyzer',
    'GeminiAnalyzerRedis',
    'GeminiAnalyzer',
    'GeminiAnalyzerOrchestrator',
]
