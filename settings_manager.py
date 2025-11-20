"""
Settings Manager - Inspirado em Windows Master Store
Gerencia configurações persistentes da aplicação
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

class SettingsManager:
    """Gerenciador de configurações da aplicação"""
    
    def __init__(self, settings_file: str = "app_settings.json"):
        self.settings_file = Path(settings_file)
        self.settings: Dict[str, Any] = {}
        self.load()
    
    def load(self) -> None:
        """Carrega configurações do arquivo JSON"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
                print(f"✓ Configurações carregadas de {self.settings_file}")
            except Exception as e:
                print(f"⚠ Erro ao carregar configurações: {e}")
                self._create_default()
        else:
            self._create_default()
    
    def _create_default(self) -> None:
        """Cria configurações padrão"""
        self.settings = {
            "Settings": {
                "AutoUpdate": True,
                "LanguageSetting": "pt-BR",
                "Theme": "auto",
                "DownloadPath": "downloads",
                "MaxConcurrentDownloads": 3,
                "AutoRetry": True,
                "MaxRetries": 3,
                "NotificationsEnabled": True,
                "AutoConvert": False,
                "PreferredVideoQuality": "1080p",
                "PreferredAudioFormat": "mp3",
                "KeepOriginal": False
            },
            "DownloadHistory": {
                "Records": [],
                "LastCleanup": None,
                "MaxHistoryDays": 30
            },
            "QuickAccess": {
                "RecentUrls": [],
                "FavoriteFolders": [],
                "MaxRecentUrls": 10
            },
            "Performance": {
                "UseHardwareAcceleration": True,
                "MaxCacheSize": 1024,
                "AutoCleanCache": True
            },
            "Privacy": {
                "SaveHistory": True,
                "AnonymousUsage": False
            }
        }
        self.save()
    
    def save(self) -> None:
        """Salva configurações no arquivo JSON"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            print(f"✓ Configurações salvas em {self.settings_file}")
        except Exception as e:
            print(f"✗ Erro ao salvar configurações: {e}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Obtém valor usando caminho separado por ponto
        Exemplo: get("Settings.Theme") retorna auto
        """
        keys = key_path.split('.')
        value = self.settings
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any, auto_save: bool = True) -> None:
        """
        Define valor usando caminho separado por ponto
        Exemplo: set("Settings.Theme", "dark")
        """
        keys = key_path.split('.')
        current = self.settings
        
        # Navegar até o penúltimo nível
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Definir o valor final
        current[keys[-1]] = value
        
        if auto_save:
            self.save()
    
    def add_to_history(self, record: Dict[str, Any]) -> None:
        """Adiciona registro ao histórico de downloads"""
        if not self.get("Privacy.SaveHistory", True):
            return
        
        history = self.get("DownloadHistory.Records", [])
        record["timestamp"] = datetime.now().isoformat()
        history.insert(0, record)  # Adiciona no início
        
        # Limita tamanho do histórico
        max_records = 100
        if len(history) > max_records:
            history = history[:max_records]
        
        self.set("DownloadHistory.Records", history)
    
    def add_recent_url(self, url: str) -> None:
        """Adiciona URL aos recentes"""
        recent = self.get("QuickAccess.RecentUrls", [])
        
        # Remove se já existe
        if url in recent:
            recent.remove(url)
        
        # Adiciona no início
        recent.insert(0, url)
        
        # Limita quantidade
        max_recent = self.get("QuickAccess.MaxRecentUrls", 10)
        if len(recent) > max_recent:
            recent = recent[:max_recent]
        
        self.set("QuickAccess.RecentUrls", recent)
    
    def cleanup_history(self) -> int:
        """
        Remove registros antigos do histórico
        Retorna quantidade de registros removidos
        """
        max_days = self.get("DownloadHistory.MaxHistoryDays", 30)
        history = self.get("DownloadHistory.Records", [])
        cutoff_date = datetime.now().timestamp() - (max_days * 24 * 3600)
        
        original_count = len(history)
        history = [
            r for r in history 
            if datetime.fromisoformat(r.get("timestamp", "2000-01-01")).timestamp() > cutoff_date
        ]
        
        removed_count = original_count - len(history)
        
        if removed_count > 0:
            self.set("DownloadHistory.Records", history)
            self.set("DownloadHistory.LastCleanup", datetime.now().isoformat())
        
        return removed_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas de uso"""
        history = self.get("DownloadHistory.Records", [])
        
        total_downloads = len(history)
        successful = sum(1 for r in history if r.get("status") == "completed")
        failed = sum(1 for r in history if r.get("status") == "failed")
        
        # Tamanho total baixado
        total_size = sum(r.get("size", 0) for r in history if r.get("status") == "completed")
        
        # Plataformas mais usadas
        platforms = {}
        for record in history:
            platform = record.get("platform", "Unknown")
            platforms[platform] = platforms.get(platform, 0) + 1
        
        return {
            "total_downloads": total_downloads,
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / total_downloads * 100) if total_downloads > 0 else 0,
            "total_size_mb": total_size / (1024 * 1024),
            "platforms": platforms,
            "recent_urls_count": len(self.get("QuickAccess.RecentUrls", [])),
        }
    
    def export_settings(self, filepath: str) -> bool:
        """Exporta configurações para arquivo"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"✗ Erro ao exportar: {e}")
            return False
    
    def import_settings(self, filepath: str) -> bool:
        """Importa configurações de arquivo"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                imported = json.load(f)
            
            # Validação básica
            if "Settings" in imported:
                self.settings = imported
                self.save()
                return True
            else:
                print("✗ Arquivo de configurações inválido")
                return False
        except Exception as e:
            print(f"✗ Erro ao importar: {e}")
            return False


# Instância global
settings_manager = SettingsManager()


if __name__ == "__main__":
    # Teste do módulo
    print("\n=== TESTE DO SETTINGS MANAGER ===\n")
    
    sm = SettingsManager()
    
    print(f"Tema atual: {sm.get('Settings.Theme')}")
    print(f"Caminho de download: {sm.get('Settings.DownloadPath')}")
    print(f"Downloads simultâneos: {sm.get('Settings.MaxConcurrentDownloads')}")
    
    # Adicionar URL recente
    sm.add_recent_url("https://youtube.com/watch?v=example")
    sm.add_recent_url("https://soundcloud.com/artist/track")
    
    print(f"\nURLs recentes: {sm.get('QuickAccess.RecentUrls')}")
    
    # Adicionar ao histórico
    sm.add_to_history({
        "url": "https://youtube.com/watch?v=test",
        "title": "Vídeo de Teste",
        "platform": "YouTube",
        "status": "completed",
        "size": 15728640  # 15 MB
    })
    
    # Estatísticas
    stats = sm.get_statistics()
    print(f"\n=== ESTATÍSTICAS ===")
    print(f"Total de downloads: {stats['total_downloads']}")
    print(f"Taxa de sucesso: {stats['success_rate']:.1f}%")
    print(f"Tamanho total: {stats['total_size_mb']:.2f} MB")
    print(f"Plataformas: {stats['platforms']}")
