"""
SQLite Cache Manager para Spotify Downloads
Reduz chamadas à API do Spotify e acelera re-downloads
Inspirado no SpotiFlyer (sqlite-jdbc-3.34.0.jar)
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class SpotifyCacheManager:
    """Gerencia cache SQLite de metadata do Spotify e mapeamentos YouTube"""
    
    def __init__(self, db_path: str = 'downloads/spotify_cache.db'):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info(f"📦 Cache SQLite inicializado: {self.db_path}")
    
    def _init_db(self):
        """Cria tabelas se não existirem"""
        conn = sqlite3.connect(str(self.db_path))
        
        # Tabela de tracks individuais
        conn.execute('''
            CREATE TABLE IF NOT EXISTS cached_tracks (
                spotify_url TEXT PRIMARY KEY,
                spotify_id TEXT,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                album TEXT,
                duration_sec INTEGER,
                youtube_video_id TEXT,
                youtube_url TEXT,
                score FLOAT,
                download_path TEXT,
                file_size_bytes INTEGER,
                timestamp DATETIME NOT NULL,
                last_accessed DATETIME,
                success BOOLEAN NOT NULL,
                error_message TEXT
            )
        ''')
        
        # Tabela de playlists completas
        conn.execute('''
            CREATE TABLE IF NOT EXISTS cached_playlists (
                playlist_id TEXT PRIMARY KEY,
                playlist_url TEXT NOT NULL,
                name TEXT NOT NULL,
                owner TEXT,
                total_tracks INTEGER,
                metadata TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                last_accessed DATETIME
            )
        ''')
        
        # Índices para performance
        conn.execute('CREATE INDEX IF NOT EXISTS idx_spotify_id ON cached_tracks(spotify_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON cached_tracks(timestamp)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_success ON cached_tracks(success)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_youtube_id ON cached_tracks(youtube_video_id)')
        
        conn.commit()
        conn.close()
        logger.info("✅ Schema SQLite criado com sucesso")
    
    def get_cached_track(self, spotify_url: str, max_age_days: int = 30) -> Optional[Dict[str, Any]]:
        """
        Retorna cache de uma track se existir e não estiver expirado
        
        Args:
            spotify_url: URL completa ou ID do Spotify
            max_age_days: Idade máxima do cache em dias (default: 30)
        
        Returns:
            Dict com dados do cache ou None se não encontrado/expirado
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        
        # Busca por URL ou ID
        cursor = conn.execute('''
            SELECT * FROM cached_tracks
            WHERE (spotify_url = ? OR spotify_id = ?)
            AND datetime(timestamp) > datetime('now', ?)
            AND success = 1
        ''', (spotify_url, spotify_url, f'-{max_age_days} days'))
        
        row = cursor.fetchone()
        
        if row:
            # Atualiza last_accessed
            conn.execute('''
                UPDATE cached_tracks
                SET last_accessed = datetime('now')
                WHERE spotify_url = ?
            ''', (row['spotify_url'],))
            conn.commit()
            
            result = dict(row)
            logger.info(f"✅ Cache hit: {result['artist']} - {result['title']} (score: {result['score']:.1f})")
            conn.close()
            return result
        
        conn.close()
        return None
    
    def cache_track(
        self,
        spotify_url: str,
        spotify_id: str,
        title: str,
        artist: str,
        duration_sec: int,
        youtube_video_id: Optional[str] = None,
        youtube_url: Optional[str] = None,
        score: Optional[float] = None,
        download_path: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        album: Optional[str] = None
    ):
        """
        Salva resultado de download no cache
        
        Args:
            spotify_url: URL completa do Spotify
            spotify_id: ID da track (extraído da URL)
            title: Nome da música
            artist: Nome do artista
            duration_sec: Duração em segundos
            youtube_video_id: ID do vídeo no YouTube (se encontrado)
            youtube_url: URL completa do YouTube
            score: Score do fuzzy matching (0-100)
            download_path: Caminho do arquivo baixado
            file_size_bytes: Tamanho do arquivo em bytes
            success: True se download bem-sucedido
            error_message: Mensagem de erro (se falhou)
            album: Nome do álbum
        """
        conn = sqlite3.connect(str(self.db_path))
        
        # Calcula tamanho do arquivo se não fornecido
        if download_path and file_size_bytes is None:
            path = Path(download_path)
            if path.exists():
                file_size_bytes = path.stat().st_size
        
        conn.execute('''
            INSERT OR REPLACE INTO cached_tracks
            (spotify_url, spotify_id, title, artist, album, duration_sec,
             youtube_video_id, youtube_url, score, download_path, file_size_bytes,
             timestamp, last_accessed, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), ?, ?)
        ''', (
            spotify_url, spotify_id, title, artist, album, duration_sec,
            youtube_video_id, youtube_url, score, download_path, file_size_bytes,
            success, error_message
        ))
        
        conn.commit()
        conn.close()
        
        if success:
            logger.info(f"💾 Cache salvo: {artist} - {title} → {youtube_video_id or 'FAILED'}")
        else:
            logger.warning(f"💾 Cache salvo (falha): {artist} - {title} → {error_message}")
    
    def get_cached_playlist(self, playlist_id: str, max_age_days: int = 7) -> Optional[Dict[str, Any]]:
        """
        Retorna metadata de playlist cacheada
        
        Args:
            playlist_id: ID da playlist do Spotify
            max_age_days: Idade máxima do cache (default: 7 dias, playlists mudam)
        
        Returns:
            Dict com metadata da playlist ou None
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute('''
            SELECT * FROM cached_playlists
            WHERE playlist_id = ?
            AND datetime(timestamp) > datetime('now', ?)
        ''', (playlist_id, f'-{max_age_days} days'))
        
        row = cursor.fetchone()
        
        if row:
            # Atualiza last_accessed
            conn.execute('''
                UPDATE cached_playlists
                SET last_accessed = datetime('now')
                WHERE playlist_id = ?
            ''', (playlist_id,))
            conn.commit()
            
            result = dict(row)
            result['metadata'] = json.loads(result['metadata'])
            logger.info(f"✅ Playlist cache hit: {result['name']} ({result['total_tracks']} tracks)")
            conn.close()
            return result
        
        conn.close()
        return None
    
    def cache_playlist(
        self,
        playlist_id: str,
        playlist_url: str,
        name: str,
        total_tracks: int,
        metadata: List[Dict[str, Any]],
        owner: Optional[str] = None
    ):
        """
        Salva metadata de playlist no cache
        
        Args:
            playlist_id: ID da playlist
            playlist_url: URL completa
            name: Nome da playlist
            total_tracks: Número total de músicas
            metadata: Lista de dicts com info de cada track
            owner: Dono da playlist
        """
        conn = sqlite3.connect(str(self.db_path))
        
        conn.execute('''
            INSERT OR REPLACE INTO cached_playlists
            (playlist_id, playlist_url, name, owner, total_tracks, metadata,
             timestamp, last_accessed)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        ''', (
            playlist_id, playlist_url, name, owner, total_tracks,
            json.dumps(metadata, ensure_ascii=False)
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"💾 Playlist cacheada: {name} ({total_tracks} tracks)")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache"""
        conn = sqlite3.connect(str(self.db_path))
        
        # Stats de tracks
        conn.row_factory = sqlite3.Row
        cursor = conn.execute('''
            SELECT
                COUNT(*) as total_tracks,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_tracks,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_tracks,
                AVG(score) as avg_score,
                SUM(file_size_bytes) as total_size_bytes,
                COUNT(DISTINCT artist) as unique_artists
            FROM cached_tracks
        ''')
        
        row = cursor.fetchone()
        track_stats = dict(row) if row else {}
        
        # Stats de playlists
        cursor = conn.execute('''
            SELECT
                COUNT(*) as total_playlists,
                SUM(total_tracks) as total_playlist_tracks
            FROM cached_playlists
        ''')
        
        row = cursor.fetchone()
        playlist_stats = dict(row) if row else {}
        
        # Tamanho do banco
        db_size_bytes = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
        
        conn.close()
        
        return {
            'cache_db_path': str(self.db_path),
            'cache_db_size_mb': db_size_bytes / (1024 * 1024),
            'tracks': {
                'total': track_stats['total_tracks'] or 0,
                'successful': track_stats['successful_tracks'] or 0,
                'failed': track_stats['failed_tracks'] or 0,
                'avg_score': track_stats['avg_score'] or 0,
                'total_size_mb': (track_stats['total_size_bytes'] or 0) / (1024 * 1024),
                'unique_artists': track_stats['unique_artists'] or 0
            },
            'playlists': {
                'total': playlist_stats['total_playlists'] or 0,
                'total_tracks': playlist_stats['total_playlist_tracks'] or 0
            }
        }
    
    def clean_old_cache(self, days: int = 90):
        """Remove entradas antigas do cache"""
        conn = sqlite3.connect(str(self.db_path))
        
        cursor = conn.execute('''
            DELETE FROM cached_tracks
            WHERE datetime(timestamp) < datetime('now', ?)
        ''', (f'-{days} days',))
        
        tracks_deleted = cursor.rowcount
        
        cursor = conn.execute('''
            DELETE FROM cached_playlists
            WHERE datetime(timestamp) < datetime('now', ?)
        ''', (f'-{days} days',))
        
        playlists_deleted = cursor.rowcount
        
        conn.execute('VACUUM')  # Compacta o banco
        conn.commit()
        conn.close()
        
        logger.info(f"🧹 Cache limpo: {tracks_deleted} tracks, {playlists_deleted} playlists removidas")
        return {'tracks_deleted': tracks_deleted, 'playlists_deleted': playlists_deleted}


# Instância global (singleton)
_cache_instance: Optional[SpotifyCacheManager] = None


def get_cache_manager() -> SpotifyCacheManager:
    """Retorna instância global do cache manager"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SpotifyCacheManager()
    return _cache_instance


if __name__ == '__main__':
    # Teste do cache
    logging.basicConfig(level=logging.INFO)
    
    cache = SpotifyCacheManager('test_cache.db')
    
    # Testa cache de track
    print("\n=== Teste 1: Cache de Track ===")
    cache.cache_track(
        spotify_url='https://open.spotify.com/track/2Rqf4usBdZUxLaXM2pXDnZ',
        spotify_id='2Rqf4usBdZUxLaXM2pXDnZ',
        title='Left To Right',
        artist='Alok',
        duration_sec=180,
        youtube_video_id='abc123',
        youtube_url='https://youtube.com/watch?v=abc123',
        score=99.5,
        download_path='downloads/spotify/Alok - Left To Right.mp3',
        success=True
    )
    
    # Busca no cache
    cached = cache.get_cached_track('2Rqf4usBdZUxLaXM2pXDnZ')
    print(f"Cache encontrado: {cached is not None}")
    if cached:
        print(f"  Artista: {cached['artist']}")
        print(f"  Título: {cached['title']}")
        print(f"  Score: {cached['score']}")
    
    # Testa cache de playlist
    print("\n=== Teste 2: Cache de Playlist ===")
    cache.cache_playlist(
        playlist_id='4TbL08c7zALzQhEu5baQ8S',
        playlist_url='https://open.spotify.com/playlist/4TbL08c7zALzQhEu5baQ8S',
        name='ALOK LIVE TOMORROWLAND',
        total_tracks=97,
        metadata=[
            {'title': 'Fever', 'artist': 'Alok', 'duration': 180},
            {'title': 'Left To Right', 'artist': 'Alok', 'duration': 180}
        ],
        owner='Alok'
    )
    
    cached_playlist = cache.get_cached_playlist('4TbL08c7zALzQhEu5baQ8S')
    print(f"Playlist encontrada: {cached_playlist is not None}")
    
    # Stats
    print("\n=== Teste 3: Estatísticas ===")
    stats = cache.get_cache_stats()
    print(json.dumps(stats, indent=2))
    
    # Limpa teste
    Path('test_cache.db').unlink(missing_ok=True)
    print("\n✅ Todos os testes passaram!")
