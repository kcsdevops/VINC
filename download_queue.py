"""
Sistema de Fila de Downloads
Inspirado no 9xconvert - Gerenciamento completo de downloads
"""

import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

class DownloadStatus(Enum):
    """Estados possíveis de um download"""
    WAITING = "waiting"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"

@dataclass
class DownloadTask:
    """Tarefa de download"""
    id: str
    url: str
    title: str
    platform: str
    quality: str = "best"
    format: str = "mp4"
    status: str = "waiting"
    progress: float = 0.0
    speed: str = "0 KB/s"
    eta: str = "--:--"
    file_size: str = "Unknown"
    downloaded_size: str = "0 MB"
    thumbnail: Optional[str] = None
    error: Optional[str] = None
    added_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    output_path: Optional[str] = None
    
    def to_dict(self):
        """Converte para dicionário"""
        return asdict(self)

class DownloadQueue:
    """Gerenciador de fila de downloads"""
    
    def __init__(self, max_parallel: int = 3):
        self.max_parallel = max_parallel
        self.tasks: Dict[str, DownloadTask] = {}
        self.queue: List[str] = []  # IDs na ordem da fila
        self.active: List[str] = []  # IDs em download
        self.lock = threading.Lock()
        self.running = True
        
        # Callbacks
        self.on_start: Optional[Callable] = None
        self.on_progress: Optional[Callable] = None
        self.on_complete: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
    def add(self, url: str, title: str, platform: str, 
            quality: str = "best", format: str = "mp4",
            thumbnail: Optional[str] = None) -> str:
        """
        Adiciona nova tarefa à fila
        Retorna o ID da tarefa
        """
        task_id = str(uuid.uuid4())
        
        task = DownloadTask(
            id=task_id,
            url=url,
            title=title,
            platform=platform,
            quality=quality,
            format=format,
            status=DownloadStatus.WAITING.value,
            added_at=datetime.now().isoformat(),
            thumbnail=thumbnail
        )
        
        with self.lock:
            self.tasks[task_id] = task
            self.queue.append(task_id)
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """Obtém tarefa pelo ID"""
        return self.tasks.get(task_id)
    
    def update_progress(self, task_id: str, progress: float, 
                       speed: str = "", eta: str = "",
                       downloaded_size: str = ""):
        """Atualiza progresso de uma tarefa"""
        with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.progress = progress
                if speed:
                    task.speed = speed
                if eta:
                    task.eta = eta
                if downloaded_size:
                    task.downloaded_size = downloaded_size
                
                if self.on_progress:
                    self.on_progress(task)
    
    def start_task(self, task_id: str):
        """Marca tarefa como iniciada"""
        with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.status = DownloadStatus.DOWNLOADING.value
                task.started_at = datetime.now().isoformat()
                
                if task_id in self.queue:
                    self.queue.remove(task_id)
                if task_id not in self.active:
                    self.active.append(task_id)
                
                if self.on_start:
                    self.on_start(task)
    
    def complete_task(self, task_id: str, output_path: str):
        """Marca tarefa como completada"""
        with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.status = DownloadStatus.COMPLETED.value
                task.progress = 100.0
                task.completed_at = datetime.now().isoformat()
                task.output_path = output_path
                
                if task_id in self.active:
                    self.active.remove(task_id)
                
                if self.on_complete:
                    self.on_complete(task)
    
    def fail_task(self, task_id: str, error: str):
        """Marca tarefa como falha"""
        with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.status = DownloadStatus.FAILED.value
                task.error = error
                
                if task_id in self.active:
                    self.active.remove(task_id)
                
                if self.on_error:
                    self.on_error(task)
    
    def pause_task(self, task_id: str):
        """Pausa uma tarefa"""
        with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                if task.status == DownloadStatus.DOWNLOADING.value:
                    task.status = DownloadStatus.PAUSED.value
                    
                    if task_id in self.active:
                        self.active.remove(task_id)
                    if task_id not in self.queue:
                        self.queue.insert(0, task_id)  # Volta para início da fila
    
    def resume_task(self, task_id: str):
        """Resume uma tarefa pausada"""
        with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                if task.status == DownloadStatus.PAUSED.value:
                    task.status = DownloadStatus.WAITING.value
                    
                    if task_id not in self.queue:
                        self.queue.append(task_id)
    
    def cancel_task(self, task_id: str):
        """Cancela uma tarefa"""
        with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.status = DownloadStatus.CANCELED.value
                
                if task_id in self.queue:
                    self.queue.remove(task_id)
                if task_id in self.active:
                    self.active.remove(task_id)
    
    def retry_task(self, task_id: str):
        """Tenta novamente uma tarefa falha"""
        with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                if task.status in [DownloadStatus.FAILED.value, DownloadStatus.CANCELED.value]:
                    task.status = DownloadStatus.WAITING.value
                    task.progress = 0.0
                    task.error = None
                    task.started_at = None
                    task.completed_at = None
                    
                    if task_id not in self.queue:
                        self.queue.append(task_id)
    
    def remove_task(self, task_id: str):
        """Remove completamente uma tarefa"""
        with self.lock:
            if task_id in self.tasks:
                if task_id in self.queue:
                    self.queue.remove(task_id)
                if task_id in self.active:
                    self.active.remove(task_id)
                del self.tasks[task_id]
    
    # Operações em massa
    
    def pause_all(self):
        """Pausa todos os downloads ativos"""
        with self.lock:
            for task_id in list(self.active):
                self.pause_task(task_id)
    
    def resume_all(self):
        """Resume todos os downloads pausados"""
        with self.lock:
            paused_tasks = [
                task_id for task_id, task in self.tasks.items()
                if task.status == DownloadStatus.PAUSED.value
            ]
            for task_id in paused_tasks:
                self.resume_task(task_id)
    
    def cancel_all(self):
        """Cancela todos os downloads"""
        with self.lock:
            all_task_ids = list(self.queue) + list(self.active)
            for task_id in all_task_ids:
                self.cancel_task(task_id)
    
    def retry_all(self):
        """Tenta novamente todos os downloads falhados"""
        with self.lock:
            failed_tasks = [
                task_id for task_id, task in self.tasks.items()
                if task.status == DownloadStatus.FAILED.value
            ]
            for task_id in failed_tasks:
                self.retry_task(task_id)
    
    def clear_completed(self):
        """Remove todos os downloads completados"""
        with self.lock:
            completed_tasks = [
                task_id for task_id, task in self.tasks.items()
                if task.status == DownloadStatus.COMPLETED.value
            ]
            for task_id in completed_tasks:
                self.remove_task(task_id)
    
    def clear_all(self):
        """Limpa toda a fila (exceto downloads ativos)"""
        with self.lock:
            # Remove apenas tarefas não ativas
            inactive_tasks = [
                task_id for task_id, task in self.tasks.items()
                if task.status != DownloadStatus.DOWNLOADING.value
            ]
            for task_id in inactive_tasks:
                self.remove_task(task_id)
    
    # Consultas
    
    def get_all_tasks(self) -> Dict[str, List[DownloadTask]]:
        """Retorna todas as tarefas organizadas por status"""
        with self.lock:
            result = {
                'queue': [],
                'active': [],
                'completed': [],
                'failed': [],
                'paused': []
            }
            
            for task_id, task in self.tasks.items():
                if task.status == DownloadStatus.WAITING.value:
                    result['queue'].append(task)
                elif task.status == DownloadStatus.DOWNLOADING.value:
                    result['active'].append(task)
                elif task.status == DownloadStatus.COMPLETED.value:
                    result['completed'].append(task)
                elif task.status == DownloadStatus.FAILED.value:
                    result['failed'].append(task)
                elif task.status == DownloadStatus.PAUSED.value:
                    result['paused'].append(task)
            
            return result
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas da fila"""
        with self.lock:
            stats = {
                'total': len(self.tasks),
                'waiting': 0,
                'downloading': 0,
                'paused': 0,
                'completed': 0,
                'failed': 0,
                'canceled': 0,
                'active_slots': len(self.active),
                'max_parallel': self.max_parallel
            }
            
            for task in self.tasks.values():
                if task.status == DownloadStatus.WAITING.value:
                    stats['waiting'] += 1
                elif task.status == DownloadStatus.DOWNLOADING.value:
                    stats['downloading'] += 1
                elif task.status == DownloadStatus.PAUSED.value:
                    stats['paused'] += 1
                elif task.status == DownloadStatus.COMPLETED.value:
                    stats['completed'] += 1
                elif task.status == DownloadStatus.FAILED.value:
                    stats['failed'] += 1
                elif task.status == DownloadStatus.CANCELED.value:
                    stats['canceled'] += 1
            
            return stats
    
    def can_start_download(self) -> bool:
        """Verifica se pode iniciar um novo download"""
        return len(self.active) < self.max_parallel
    
    def get_next_task(self) -> Optional[str]:
        """Retorna próxima tarefa da fila (se houver slot disponível)"""
        with self.lock:
            if self.queue and self.can_start_download():
                return self.queue[0]
            return None


# Instância global
download_queue = DownloadQueue()


# Testes
if __name__ == '__main__':
    print("=" * 60)
    print("Sistema de Fila de Downloads - Teste")
    print("=" * 60)
    
    # Criar fila
    queue = DownloadQueue(max_parallel=3)
    
    # Adicionar tarefas
    print("\n📥 Adicionando tarefas...")
    task1 = queue.add("https://youtube.com/1", "Vídeo 1", "YouTube", quality="1080p")
    task2 = queue.add("https://youtube.com/2", "Vídeo 2", "YouTube", quality="720p")
    task3 = queue.add("https://soundcloud.com/1", "Música 1", "SoundCloud", format="mp3")
    print(f"  ✓ 3 tarefas adicionadas")
    
    # Estatísticas
    print("\n📊 Estatísticas:")
    stats = queue.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Simular downloads
    print("\n▶ Simulando downloads...")
    queue.start_task(task1)
    queue.update_progress(task1, 25.0, "2.5 MB/s", "00:30", "50 MB")
    queue.update_progress(task1, 50.0, "2.8 MB/s", "00:25", "100 MB")
    queue.update_progress(task1, 75.0, "3.0 MB/s", "00:10", "150 MB")
    queue.complete_task(task1, "/downloads/video1.mp4")
    print(f"  ✓ Tarefa 1 completada")
    
    queue.start_task(task2)
    queue.fail_task(task2, "Network error")
    print(f"  ✗ Tarefa 2 falhou")
    
    # Listar todas
    print("\n📋 Todas as tarefas:")
    all_tasks = queue.get_all_tasks()
    for status, tasks in all_tasks.items():
        if tasks:
            print(f"\n  {status.upper()}:")
            for task in tasks:
                print(f"    - {task.title} ({task.status}) - {task.progress:.1f}%")
    
    # Testar retry
    print("\n🔄 Tentando novamente tarefa falhada...")
    queue.retry_task(task2)
    stats = queue.get_statistics()
    print(f"  waiting: {stats['waiting']}, failed: {stats['failed']}")
    
    # Operações em massa
    print("\n⏸ Pausando tudo...")
    queue.pause_all()
    stats = queue.get_statistics()
    print(f"  paused: {stats['paused']}")
    
    print("\n▶ Resumindo tudo...")
    queue.resume_all()
    stats = queue.get_statistics()
    print(f"  waiting: {stats['waiting']}")
    
    print("\n✅ Teste concluído!")
