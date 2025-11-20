"""
Interface Web para Download de Vídeos
Servidor Flask que fornece interface web para listar e baixar vídeos
"""

from flask import Flask, render_template, request, jsonify, send_file
import os
import sys
import webbrowser
from pathlib import Path
import threading
import json
from datetime import datetime
import subprocess
from urllib.parse import urlparse
import logging
import re

try:
    import yt_dlp
except ImportError:
    print("Erro: yt-dlp não está instalado.")
    print("Execute: pip install yt-dlp")
    sys.exit(1)

# Importa cache manager
from spotify_cache import get_cache_manager

# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Função para verificar e instalar FFmpeg para spotdl
def ensure_ffmpeg():
    """Verifica se FFmpeg está instalado e instala se necessário"""
    try:
        # Verifica se FFmpeg já está disponível
        subprocess.run(['ffmpeg', '-version'], 
                      capture_output=True, 
                      check=True,
                      creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("FFmpeg não encontrado. Instalando via spotdl...")
        try:
            # Instala FFmpeg usando spotdl
            subprocess.run([sys.executable, '-m', 'spotdl', '--download-ffmpeg'],
                          check=True,
                          creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            print("✓ FFmpeg instalado com sucesso!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Erro ao instalar FFmpeg: {e}")
            return False

app = Flask(__name__)

# Domínios conhecidos por usarem DRM (não suportados)
DRM_DOMAINS = [
    'netflix.com', 'www.netflix.com',
    'primevideo.com', 'www.primevideo.com', 'amazon.com', 'www.amazon.com',
    'disneyplus.com', 'www.disneyplus.com',
    'hulu.com', 'www.hulu.com',
    'hbomax.com', 'www.hbomax.com', 'max.com', 'www.max.com', 'hbo.com', 'www.hbo.com',
    'tv.apple.com', 'apple.com', 'www.apple.com',
    'paramountplus.com', 'www.paramountplus.com',
    'peacocktv.com', 'www.peacocktv.com',
    'starplus.com', 'www.starplus.com',
    'dazn.com', 'www.dazn.com',
    'hotstar.com', 'www.hotstar.com',
]


def is_known_drm_site(check_url: str) -> bool:
    """Retorna True se o domínio da URL for conhecido por uso de DRM"""
    try:
        host = urlparse(check_url).netloc.lower()
    except Exception:
        return False
    return any(host.endswith(d) for d in DRM_DOMAINS)


def get_windows_videos_folder():
    """Retorna o caminho da pasta Meus Vídeos do Windows"""
    if sys.platform == 'win32':
        import winreg
        try:
            # Tenta obter via Registry
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r'Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders')
            videos_path = winreg.QueryValueEx(key, 'My Video')[0]
            winreg.CloseKey(key)
            return videos_path
        except Exception:
            # Fallback para caminho padrão
            return str(Path.home() / 'Videos')
    else:
        # Em sistemas não-Windows, usa pasta Videos no home
        return str(Path.home() / 'Videos')


def detect_platform(url):
    """Detecta a plataforma/serviço da URL e retorna nome da pasta"""
    domain = urlparse(url).netloc.lower()
    
    # Mapeamento de domínios para pastas
    platform_map = {
        'youtube.com': 'YouTube',
        'youtu.be': 'YouTube',
        'm.youtube.com': 'YouTube',
        'spotify.com': 'Spotify',
        'open.spotify.com': 'Spotify',
        'pornhub.com': 'PornHub',
        'pt.pornhub.com': 'PornHub',
        'xvideos.com': 'XVideos',
        'twitter.com': 'Twitter',
        'x.com': 'Twitter',
        'instagram.com': 'Instagram',
        'facebook.com': 'Facebook',
        'fb.watch': 'Facebook',
        'tiktok.com': 'TikTok',
        'vimeo.com': 'Vimeo',
        'dailymotion.com': 'DailyMotion',
        'twitch.tv': 'Twitch',
        'reddit.com': 'Reddit',
        'streamable.com': 'Streamable',
        'soundcloud.com': 'SoundCloud',
        'bandcamp.com': 'Bandcamp',
        'mixcloud.com': 'Mixcloud',
    }
    
    # Procura por correspondência exata ou parcial
    for domain_key, folder_name in platform_map.items():
        if domain_key in domain:
            return folder_name
    
    # Se não encontrou, usa "Outros"
    return 'Outros'

# Handler global de erros para APIs - sempre retorna JSON
@app.errorhandler(Exception)
def handle_error(error):
    """Captura todos os erros e retorna JSON em vez de HTML"""
    # Se a requisição é para API, retorna JSON
    if request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'error': str(error)
        }), 500
    # Caso contrário, deixa o Flask lidar normalmente
    raise error

# Configurações
DOWNLOAD_PATH = Path("downloads")
DOWNLOAD_PATH.mkdir(exist_ok=True)

# Armazenar status dos downloads
download_status = {}

# Configuração de downloads simultâneos (aumentado de 3 para 8)
MAX_CONCURRENT_DOWNLOADS = 8

# Gerenciamento de prevenção de suspensão do Windows
_PREVENT_SLEEP_COUNT = 0
def _set_windows_prevent_sleep(enable: bool):
    try:
        if os.name != 'nt':
            return
        import ctypes
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        if enable:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        else:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except Exception:
        pass

def _prevent_sleep_acquire():
    global _PREVENT_SLEEP_COUNT
    _PREVENT_SLEEP_COUNT += 1
    if _PREVENT_SLEEP_COUNT == 1:
        _set_windows_prevent_sleep(True)

def _prevent_sleep_release():
    global _PREVENT_SLEEP_COUNT
    _PREVENT_SLEEP_COUNT = max(0, _PREVENT_SLEEP_COUNT - 1)
    if _PREVENT_SLEEP_COUNT == 0:
        _set_windows_prevent_sleep(False)


class WebVideoDownloader:
    """Classe para gerenciar downloads via web"""
    
    def __init__(self, download_path="downloads"):
        self.download_path = Path(download_path)
        self.download_path.mkdir(exist_ok=True)

    def _format_duration(self, seconds):
        """Converte duração em segundos para string mm:ss ou hh:mm:ss"""
        try:
            if not seconds or int(seconds) <= 0:
                return 'N/A'
            seconds = int(seconds)
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            if h > 0:
                return f"{h}:{m:02d}:{s:02d}"
            return f"{m}:{s:02d}"
        except Exception:
            return 'N/A'
    
    def get_video_info(self, url):
        """
        Obtém informações detalhadas sobre vídeo(s) de uma URL
        
        Args:
            url: URL do vídeo ou playlist
            
        Returns:
            dict: Informações estruturadas
        """
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',  # Para playlists, não extrai todos os detalhes
            'playlistend': None,  # Sem limite de vídeos
            'ignoreerrors': True,  # Continua mesmo se algum vídeo falhar
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if 'entries' in info:
                    # É uma playlist ou canal
                    total_entries = len(info['entries'])
                    print(f"[DEBUG] Total de entries detectadas: {total_entries}")
                    
                    videos = []
                    for idx, entry in enumerate(info['entries'], 1):
                        if entry:  # Algumas entradas podem ser None
                            print(f"[DEBUG] Processando vídeo {idx}/{total_entries}: {entry.get('title', 'Sem título')[:50]}")
                            videos.append({
                                'id': entry.get('id', ''),
                                'title': entry.get('title', 'Sem título'),
                                'url': entry.get('url') or entry.get('webpage_url', ''),
                                'duration': self._format_duration(entry.get('duration', 0)),
                                'thumbnail': entry.get('thumbnail', ''),
                                'uploader': entry.get('uploader', 'Desconhecido'),
                            })
                    
                    print(f"[DEBUG] Total de vídeos processados: {len(videos)}")
                    
                    return {
                        'success': True,
                        'type': 'playlist',
                        'title': info.get('title', 'Playlist'),
                        'uploader': info.get('uploader', 'Desconhecido'),
                        'video_count': len(videos),
                        'videos': videos
                    }
                else:
                    # É um único vídeo - extrair TODOS os formatos disponíveis
                    formats = []
                    if 'formats' in info and info['formats']:
                        seen_qualities = set()
                        for fmt in info['formats']:
                            # Pegar apenas formatos com vídeo E áudio (ou marcados como combinados)
                            if fmt.get('vcodec') != 'none' and (fmt.get('acodec') != 'none' or fmt.get('format_note') == 'combined'):
                                height = fmt.get('height') or 0
                                width = fmt.get('width') or 0
                                fps = fmt.get('fps') or 30
                                filesize = fmt.get('filesize') or fmt.get('filesize_approx') or 0
                                
                                # Identificar qualidade
                                if height >= 4320:
                                    quality = '8K'
                                elif height >= 2160:
                                    quality = '4K'
                                elif height >= 1440:
                                    quality = '2K'
                                elif height >= 1080:
                                    quality = '1080p' if fps <= 30 else '1080p60'
                                elif height >= 720:
                                    quality = '720p' if fps <= 30 else '720p60'
                                elif height >= 480:
                                    quality = '480p'
                                elif height >= 360:
                                    quality = '360p'
                                else:
                                    quality = '240p'
                                
                                # Evitar duplicatas de qualidade
                                quality_key = f"{quality}_{fmt.get('ext', 'mp4')}"
                                if quality_key not in seen_qualities:
                                    seen_qualities.add(quality_key)
                                    formats.append({
                                        'quality': quality,
                                        'resolution': f"{width}x{height}" if width and height else 'N/A',
                                        'fps': fps,
                                        'ext': fmt.get('ext', 'mp4'),
                                        'filesize': self._format_bytes(filesize) if filesize else 'Tamanho desconhecido',
                                        'filesize_bytes': filesize,
                                        'format_id': fmt.get('format_id', ''),
                                        'vcodec': fmt.get('vcodec', 'unknown')[:20],
                                        'acodec': fmt.get('acodec', 'unknown')[:20],
                                    })
                    
                    # Ordenar formatos por qualidade (maior primeiro)
                    quality_order = {'8K': 8, '4K': 7, '2K': 6, '1080p60': 5, '1080p': 4, '720p60': 3, '720p': 2, '480p': 1, '360p': 0, '240p': -1}
                    formats.sort(key=lambda x: quality_order.get(x['quality'], -2), reverse=True)
                    
                    return {
                        'success': True,
                        'type': 'video',
                        'videos': [{
                            'id': info.get('id', ''),
                            'title': info.get('title', 'Sem título'),
                            'url': info.get('webpage_url', url),
                            'duration': self._format_duration(info.get('duration', 0)),
                            'thumbnail': info.get('thumbnail', ''),
                            'uploader': info.get('uploader', 'Desconhecido'),
                            'view_count': info.get('view_count', 0),
                            'description': info.get('description', '')[:300],
                            'formats': formats  # NOVO: lista de formatos disponíveis
                        }]
                    }
                    
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def scan_site_for_videos(self, url):
        """
        Escaneia um site/página/canal e extrai TODOS os vídeos encontrados
        
        Args:
            url: URL do site, canal, perfil ou página
            
        Returns:
            dict: Informações de todos os vídeos encontrados
        """
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,  # Extrair informações completas
            'playlistend': None,  # Sem limite de vídeos
            'ignoreerrors': True,  # Continuar mesmo se algum vídeo falhar
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print(f"Escaneando: {url}")
                info = ydl.extract_info(url, download=False)
                
                videos = []
                
                if 'entries' in info:
                    # É uma lista (canal, playlist, página de busca, etc.)
                    total_entries = len(info['entries'])
                    print(f"Encontradas {total_entries} entradas")
                    
                    for idx, entry in enumerate(info['entries'], 1):
                        if entry:
                            print(f"Processando {idx}/{total_entries}: {entry.get('title', 'Sem título')}")
                            videos.append({
                                'id': entry.get('id', ''),
                                'title': entry.get('title', 'Sem título'),
                                'url': entry.get('webpage_url') or entry.get('url', ''),
                                'duration': self._format_duration(entry.get('duration', 0)),
                                'thumbnail': entry.get('thumbnail', ''),
                                'uploader': entry.get('uploader') or entry.get('channel', 'Desconhecido'),
                                'view_count': entry.get('view_count', 0),
                            })
                    
                    return {
                        'success': True,
                        'type': 'site_scan',
                        'title': info.get('title', 'Vídeos encontrados'),
                        'uploader': info.get('uploader') or info.get('channel', 'Site'),
                        'video_count': len(videos),
                        'videos': videos
                    }
                else:
                    # É um único vídeo
                    return {
                        'success': True,
                        'type': 'video',
                        'videos': [{
                            'id': info.get('id', ''),
                            'title': info.get('title', 'Sem título'),
                            'url': info.get('webpage_url', url),
                            'duration': self._format_duration(info.get('duration', 0)),
                            'thumbnail': info.get('thumbnail', ''),
                            'uploader': info.get('uploader', 'Desconhecido'),
                            'view_count': info.get('view_count', 0),
                        }]
                    }
                    
        except Exception as e:
            print(f"Erro ao escanear site: {str(e)}")
            return {
                'success': False,
                'error': f'Erro ao escanear site: {str(e)}'
            }
    
    def _detect_platform(self, url):
        """Detecta a plataforma/rede social da URL"""
        url_lower = url.lower()
        
        if 'instagram.com' in url_lower or 'instagr.am' in url_lower:
            return 'instagram'
        elif 'tiktok.com' in url_lower:
            return 'tiktok'
        elif 'facebook.com' in url_lower or 'fb.watch' in url_lower or 'fb.com' in url_lower:
            return 'facebook'
        elif 'twitter.com' in url_lower or 'x.com' in url_lower:
            return 'twitter'
        elif 'pinterest.com' in url_lower or 'pin.it' in url_lower:
            return 'pinterest'
        elif 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            return 'youtube'
        elif 'vimeo.com' in url_lower:
            return 'vimeo'
        elif 'dailymotion.com' in url_lower:
            return 'dailymotion'
        elif 'reddit.com' in url_lower or 'redd.it' in url_lower:
            return 'reddit'
        elif 'twitch.tv' in url_lower:
            return 'twitch'
        else:
            return 'generic'
    
    def _format_bytes(self, bytes_size):
        """Converte bytes para formato legível (KB, MB, GB)"""
        if not bytes_size or bytes_size == 0:
            return 'N/A'
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"
    
    def download_video(self, url, video_id, quality="best", audio_only=False, mp3_bitrate="320", 
                     audio_format="mp3", video_codec="auto", playlist_name=None):
        """Faz download de um vídeo"""
        global download_status
        
        # Carrega configurações atuais
        config = {}
        try:
            cfg_path = Path('config.json')
            if cfg_path.exists():
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
        except Exception:
            config = {}

        prevent_sleep = bool(config.get('prevent_sleep', True))
        create_subdirs = bool(config.get('create_subdirs', True))
        number_files = bool(config.get('number_files', True))
        skip_duplicates = bool(config.get('skip_duplicates', True))
        generate_m3u = bool(config.get('generate_m3u', True))
        embed_subtitles = bool(config.get('embed_subtitles', False))
        auto_audio_tags = bool(config.get('auto_audio_tags', True))

        download_status[video_id] = {
            'status': 'downloading',
            'progress': 0,
            'speed': 'N/A',
            'eta': 'N/A',
            'filename': ''
        }
        
        # Detecta plataforma e cria subpasta organizada
        platform = detect_platform(url)
        media_type = 'audio' if audio_only else 'video'
        
        # Cria caminho base: downloads/video/YouTube ou downloads/audio/Spotify
        platform_folder = self.download_path / media_type / platform
        platform_folder.mkdir(exist_ok=True, parents=True)

        # Pasta específica para playlist/canal se desejado
        output_base_folder = platform_folder
        safe_name = None
        if create_subdirs and playlist_name:
            # Sanitiza nome de pasta
            try:
                safe_name = re.sub(r'[\\/:*?"<>|]+', '_', str(playlist_name))
            except Exception:
                safe_name = str(playlist_name)
            output_base_folder = platform_folder / safe_name
            output_base_folder.mkdir(exist_ok=True, parents=True)

        # Sequenciador opcional por playlist
        def _next_seq(folder: Path) -> str:
            seq_path = folder / '.seq'
            try:
                n = 0
                if seq_path.exists():
                    with open(seq_path, 'r', encoding='utf-8') as f:
                        n = int((f.read() or '0').strip())
                n += 1
                with open(seq_path, 'w', encoding='utf-8') as f:
                    f.write(str(n))
                return f"{n:03d}"
            except Exception:
                return "001"

        # Organização por artista para áudios: pasta "NNN - Artista" por plataforma
        artist_folder = None
        artist_index_file = None
        artist_name = None
        if audio_only:
            try:
                # Extração rápida de metadata
                with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'noplaylist': True}) as yinfo:
                    info = yinfo.extract_info(url, download=False)
                # Resolve artista
                def _pick_artist(meta):
                    cand = meta.get('artist') or meta.get('uploader') or meta.get('channel') or meta.get('creator') or meta.get('uploader_id')
                    if isinstance(cand, list) and cand:
                        cand = cand[0]
                    if not cand:
                        cand = 'Desconhecido'
                    return str(cand)
                raw_artist = _pick_artist(info or {})
                try:
                    artist_name = re.sub(r'[\\/:*?"<>|]+', '_', raw_artist).strip() or 'Desconhecido'
                except Exception:
                    artist_name = raw_artist or 'Desconhecido'
                # Índice estável por artista (por plataforma)
                artist_index_file = platform_folder / '.artists_index.json'
                artists_index = {'next': 1, 'map': {}}
                if artist_index_file.exists():
                    try:
                        with open(artist_index_file, 'r', encoding='utf-8') as f:
                            artists_index = json.load(f) or artists_index
                    except Exception:
                        pass
                amap = artists_index.get('map', {})
                nextn = int(artists_index.get('next', 1))
                key = artist_name.lower()
                if key not in amap:
                    amap[key] = nextn
                    artists_index['map'] = amap
                    artists_index['next'] = nextn + 1
                    try:
                        with open(artist_index_file, 'w', encoding='utf-8') as f:
                            json.dump(artists_index, f, indent=2, ensure_ascii=False)
                    except Exception:
                        pass
                num = int(amap.get(key, 1))
                artist_folder = platform_folder / f"{num:03d} - {artist_name}"
                artist_folder.mkdir(exist_ok=True, parents=True)
                output_base_folder = artist_folder
            except Exception:
                # Se falhar a detecção de artista, mantém a pasta padrão
                pass

        # Template de saída (numeração de arquivo opcional)
        if number_files:
            seq_prefix = _next_seq(output_base_folder)
            output_path = str(output_base_folder / f"{seq_prefix} - %(title)s.%(ext)s")
        else:
            output_path = str(output_base_folder / '%(title)s.%(ext)s')

        # Hook de progresso para atualizar status em tempo real
        def _progress_hook(d):
            try:
                if d.get('status') == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                    downloaded = d.get('downloaded_bytes') or 0
                    percent = int(downloaded * 100 / total) if total else 0
                    speed = d.get('speed') or 0
                    eta = d.get('eta') or 0
                    download_status[video_id] = {
                        'status': 'downloading',
                        'progress': percent,
                        'speed': f"{self._format_bytes(speed)}/s" if speed else 'N/A',
                        'eta': f"{eta}s" if eta else 'N/A',
                        'filename': d.get('filename', '')
                    }
                elif d.get('status') == 'finished':
                    # Arquivo baixado, iniciando pós-processamento (ex: conversão para MP3)
                    download_status[video_id] = {
                        'status': 'processing',
                        'progress': 100,
                        'speed': 'N/A',
                        'eta': 'N/A',
                        'filename': d.get('filename', '')
                    }
            except Exception:
                # Evita quebrar o download por erro no hook
                pass
        
        if audio_only:
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': (
                    [
                        {
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': audio_format,
                            'preferredquality': mp3_bitrate,
                        }
                    ]
                    + ([{'key': 'FFmpegMetadata'}] if auto_audio_tags else [])
                ),
                'outtmpl': output_path,
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
                'progress_hooks': [_progress_hook],
            }
            output_folder = platform_folder
        else:
            ydl_opts = {
                'format': 'best' if video_codec == 'auto' else f"bestvideo[vcodec*={video_codec}]+bestaudio/best",
                'outtmpl': output_path,
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
                'progress_hooks': [_progress_hook],
            }
            output_folder = platform_folder
        
        output_folder.mkdir(exist_ok=True, parents=True)

        # Subtítulos (vídeo): escrever e incorporar
        if embed_subtitles and not audio_only:
            ydl_opts['writesubtitles'] = True
            ydl_opts['subtitleslangs'] = ['all']
            ydl_opts['embedsubtitles'] = True

        # Evitar re-downloads (baseado em ID) se habilitado
        if skip_duplicates:
            archive_file = self.download_path / 'download_archive.txt'
            ydl_opts['download_archive'] = str(archive_file)
        
        try:
            # Evita suspensão enquanto há downloads ativos
            if prevent_sleep:
                _prevent_sleep_acquire()

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Se chegou aqui, terminou com sucesso (inclusive pós-processamento)
            status_obj = download_status.get(video_id, {})
            status_obj.update({
                'status': 'completed',
                'progress': 100,
                'output_path': str(output_folder)
            })
            download_status[video_id] = status_obj
        except Exception as e:
            download_status[video_id] = {
                'status': 'error',
                'error': str(e)
            }
        finally:
            # Gera/atualiza playlist .m3u
            try:
                if generate_m3u and create_subdirs and playlist_name:
                    # Detecta arquivo final a partir do status
                    final_dir = output_base_folder
                    m3u = final_dir / (f"{safe_name or 'playlist'}.m3u")
                    fn = download_status.get(video_id, {}).get('filename') or ''
                    if fn:
                        with open(m3u, 'a', encoding='utf-8') as f:
                            f.write(os.path.basename(fn) + "\n")
            except Exception:
                pass
            # Libera prevenção de suspensão
            if prevent_sleep:
                _prevent_sleep_release()


# (Removida definição duplicada de process_ultradown_shortcuts; mantida versão consolidada abaixo)


def process_ultradown_shortcuts(url):
    """
    Processa atalhos do ULTRA DOWN AI para facilitar downloads
    
    Atalhos suportados:
    1. udyoutube.com/... → youtube.com/...
    2. udai.com/URL_COMPLETA → extrai a URL completa
    
    Args:
        url: URL original fornecida pelo usuário
        
    Returns:
        URL processada pronta para download
    """
    if not url:
        return url
    
    # Atalho 1: udyoutube.com → youtube.com
    if 'udyoutube.com' in url:
        url = url.replace('udyoutube.com', 'youtube.com')
        if not url.startswith('http'):
            url = 'https://' + url
        return url
    
    # Atalho 2: udai.com/URL_COMPLETA
    if 'udai.com/' in url:
        # Extrair a URL após udai.com/
        parts = url.split('udai.com/', 1)
        if len(parts) > 1:
            extracted_url = parts[1]
            # Se não começar com http, adicionar
            if not extracted_url.startswith('http'):
                extracted_url = 'https://' + extracted_url
            return extracted_url
    
    # Retornar URL original se não for atalho
    return url


# Criar instância do downloader
downloader = WebVideoDownloader(DOWNLOAD_PATH)


@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')


@app.route('/api/analyze', methods=['POST'])
def analyze_url():
    """Analisa uma URL e retorna informações dos vídeos"""
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'success': False, 'error': 'URL não fornecida'})

    # Normalizar atalhos e bloquear DRM
    url = process_ultradown_shortcuts(url)
    if is_known_drm_site(url):
        return jsonify({'success': False, 'error': 'Conteúdo protegido por DRM — este site de streaming não é suportado.', 'code': 'drm_protected'}), 200

    result = downloader.get_video_info(url)
    return jsonify(result)


@app.route('/api/scan-site', methods=['POST'])
def scan_site():
    """Escaneia um site/canal e retorna TODOS os vídeos encontrados"""
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'success': False, 'error': 'URL não fornecida'})

    # Normalizar atalhos e bloquear DRM
    url = process_ultradown_shortcuts(url)
    if is_known_drm_site(url):
        return jsonify({'success': False, 'error': 'Conteúdo protegido por DRM — este site de streaming não é suportado.', 'code': 'drm_protected'}), 200

    result = downloader.scan_site_for_videos(url)
    return jsonify(result)


@app.route('/api/download', methods=['POST'])
def start_download():
    """Inicia o download de um vídeo"""
    data = request.get_json()
    url = data.get('url', '')
    video_id = data.get('video_id', '')
    quality = data.get('quality', 'best')
    audio_only = data.get('audio_only', False)
    mp3_bitrate = data.get('mp3_bitrate', '320')
    audio_format = data.get('audio_format', 'mp3')
    video_codec = data.get('video_codec', 'auto')
    playlist_name = data.get('playlist_name', None)
    
    if not url or not video_id:
        return jsonify({'success': False, 'error': 'URL ou ID não fornecidos'})

    # Normalizar atalhos e bloquear DRM
    url = process_ultradown_shortcuts(url)
    if is_known_drm_site(url):
        return jsonify({'success': False, 'error': 'Conteúdo protegido por DRM — este site de streaming não é suportado.', 'code': 'drm_protected'}), 200
    
    # Inicia o download em uma thread separada
    thread = threading.Thread(
        target=downloader.download_video,
        args=(url, video_id, quality, audio_only, mp3_bitrate, audio_format, video_codec, playlist_name)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'video_id': video_id})


@app.route('/api/download-status/<video_id>')
def get_download_status(video_id):
    """Retorna o status de um download"""
    status = download_status.get(video_id, {'status': 'not_found'})
    return jsonify(status)


@app.route('/api/download-spotify', methods=['POST'])
def download_spotify():
    """
    Download de músicas do Spotify via spotdl (busca equivalente no YouTube)
    Funciona com: tracks, albums, playlists, artist pages
    CACHE SQLite: Reduz chamadas à API e acelera re-downloads
    """
    data = request.get_json()
    url = data.get('url', '')
    
    if not url:
        return jsonify({'success': False, 'error': 'URL não fornecida'}), 400
    
    if 'spotify.com' not in url and not url.startswith('spotify:'):
        return jsonify({'success': False, 'error': 'URL não é do Spotify'}), 400
    
    try:
        import subprocess
        
        # Inicializa cache manager
        cache = get_cache_manager()
        logger.info(f"🎵 Iniciando download Spotify: {url}")
        
        # Criar pasta para downloads do Spotify
        spotify_path = DOWNLOAD_PATH / 'spotify'
        spotify_path.mkdir(exist_ok=True)
        
        # Verificar e instalar FFmpeg se necessário
        if not ensure_ffmpeg():
            return jsonify({
                'success': False,
                'error': 'FFmpeg não pôde ser instalado. Necessário para spotdl.'
            }), 500
        
        # Extrai ID da playlist/album/track
        spotify_id = None
        if '/track/' in url:
            spotify_id = re.search(r'/track/([a-zA-Z0-9]+)', url)
        elif '/playlist/' in url:
            spotify_id = re.search(r'/playlist/([a-zA-Z0-9]+)', url)
        elif '/album/' in url:
            spotify_id = re.search(r'/album/([a-zA-Z0-9]+)', url)
        
        spotify_id = spotify_id.group(1) if spotify_id else None
        
        # Para playlists, verifica cache de metadata
        cache_hits = 0
        cache_misses = 0
        
        if '/playlist/' in url and spotify_id:
            cached_playlist = cache.get_cached_playlist(spotify_id, max_age_days=7)
            if cached_playlist:
                logger.info(f"📦 Playlist em cache: {cached_playlist['name']} ({cached_playlist['total_tracks']} tracks)")
                
                # Verifica quais tracks já estão cacheadas
                for track_meta in cached_playlist['metadata']:
                    track_url = track_meta.get('url', '')
                    if track_url:
                        cached_track = cache.get_cached_track(track_url, max_age_days=30)
                        if cached_track and cached_track['success']:
                            cache_hits += 1
                            logger.info(f"✅ Cache hit: {cached_track['artist']} - {cached_track['title']}")
                        else:
                            cache_misses += 1
        
        # Comando spotdl com configurações otimizadas
        cmd = [
            sys.executable,
            '-m', 'spotdl',
            'download',
            url,
            '--output', str(spotify_path),
            '--format', 'mp3',
            '--bitrate', '320k',
            '--threads', '4',  # Download paralelo
            '--print-errors',  # Mostrar erros detalhados
            '--search-query', '{artists} - {title}',  # Query mais precisa
        ]
        
        logger.info(f"⚡ Executando spotdl (cache hits: {cache_hits}, misses: {cache_misses})...")
        
        # Executar spotdl COM VERBOSE
        logger.info(f"🔧 Comando: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(Path.cwd()),
            timeout=1800  # 30 minutos timeout (para playlists grandes)
        )
        
        # Log verbose do output
        logger.info(f"📤 STDOUT ({len(result.stdout)} chars):")
        for line in result.stdout.split('\n')[:50]:  # Primeiras 50 linhas
            if line.strip():
                logger.info(f"  > {line}")
        
        if result.stderr:
            logger.warning(f"⚠️ STDERR ({len(result.stderr)} chars):")
            for line in result.stderr.split('\n')[:30]:
                if line.strip():
                    logger.warning(f"  ! {line}")
        
        logger.info(f"✅ spotdl exit code: {result.returncode}")
        
        logger.info(f"✅ spotdl exit code: {result.returncode}")
        
        # Parse output do spotdl para cachear resultados
        output_lines = result.stdout.split('\n') if result.stdout else []
        
        logger.info(f"📊 Parseando {len(output_lines)} linhas de output...")
        
        downloaded_count = 0
        failed_count = 0
        skipped_count = 0
        
        for line in output_lines:
            # Detecta downloads bem-sucedidos
            if 'Downloaded' in line:
                downloaded_count += 1
                logger.info(f"✅ Download: {line.strip()}")
                # Extrai info da música (formato: "Downloaded: Artist - Title")
                match = re.search(r'Downloaded:\s+(.+?)\s+-\s+(.+)', line)
                if match and spotify_id:
                    artist, title = match.groups()
                    logger.info(f"📝 Cacheando: {artist} - {title}")
                    # Tenta encontrar arquivo correspondente
                    for mp3_file in spotify_path.glob('*.mp3'):
                        if artist.lower() in mp3_file.stem.lower() and title.lower() in mp3_file.stem.lower():
                            logger.info(f"💾 Salvando no cache: {mp3_file.name}")
                            cache.cache_track(
                                spotify_url=url,
                                spotify_id=spotify_id,
                                title=title,
                                artist=artist,
                                duration_sec=0,  # spotdl não informa duração no output
                                download_path=str(mp3_file),
                                file_size_bytes=mp3_file.stat().st_size,
                                success=True
                            )
                            break
            
            # Detecta falhas
            elif 'LookupError' in line or 'ERROR' in line:
                failed_count += 1
                logger.warning(f"❌ Falha: {line.strip()}")
            
            # Detecta skips (já existe)
            elif 'Skipping' in line or 'already exists' in line:
                skipped_count += 1
                logger.info(f"⏭️ Skip: {line.strip()}")
        
        logger.info(f"📈 RESULTADO FINAL: {downloaded_count} baixados, {skipped_count} skipped, {failed_count} falhas")
        
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or 'Erro desconhecido'
            logger.error(f"❌ spotdl falhou: {error_msg}")
            return jsonify({
                'success': False,
                'error': f'spotdl falhou: {error_msg}'
            }), 500
        
        # Estatísticas do cache
        stats = cache.get_cache_stats()
        
        logger.info(f"✅ Download concluído: {downloaded_count} baixadas, {skipped_count} já existiam, {failed_count} falharam")
        
        return jsonify({
            'success': True,
            'message': 'Download do Spotify concluído com sucesso!',
            'output_path': str(spotify_path),
            'stats': {
                'downloaded': downloaded_count,
                'skipped': skipped_count,
                'failed': failed_count,
                'cache_hits': cache_hits,
                'cache_misses': cache_misses
            },
            'cache_stats': stats,
            'details': result.stdout
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Tempo esgotado (>30 minutos). Tente um álbum/playlist menor.'
        }), 408
    except ImportError:
        return jsonify({
            'success': False,
            'error': 'spotdl não está instalado. Execute: pip install spotdl'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro inesperado: {str(e)}'
        }), 500


@app.route('/api/download-spotify-advanced', methods=['POST'])
def download_spotify_advanced():
    """
    Download avançado de músicas do Spotify usando SpotiFlyer algorithm
    Usa fuzzy matching e intelligent scoring para melhor taxa de sucesso
    """
    data = request.get_json()
    url = data.get('url', '')
    
    if not url:
        return jsonify({'success': False, 'error': 'URL não fornecida'}), 400
    
    if 'spotify.com' not in url and not url.startswith('spotify:'):
        return jsonify({'success': False, 'error': 'URL não é do Spotify'}), 400
    
    try:
        from spotify_search import SpotifySearchEngine
        import subprocess
        
        # Criar pasta para downloads do Spotify
        spotify_path = DOWNLOAD_PATH / 'spotify'
        spotify_path.mkdir(exist_ok=True)
        
        # Obter metadados do Spotify usando spotdl
        print(f"[Spotify Advanced] Obtendo metadados de: {url}")
        cmd = [
            sys.executable,
            '-m', 'spotdl',
            'save',
            url,
            '--save-file', str(spotify_path / 'temp_metadata.spotdl'),
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            return jsonify({
                'success': False,
                'error': 'Falha ao obter metadados do Spotify'
            }), 500
        
        # Ler arquivo de metadados
        metadata_file = spotify_path / 'temp_metadata.spotdl'
        if not metadata_file.exists():
            return jsonify({
                'success': False,
                'error': 'Arquivo de metadados não encontrado'
            }), 500
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Limpar arquivo temporário
        metadata_file.unlink()
        
        # Inicializar search engine
        class FlaskLogger:
            def info(self, msg): print(f"[INFO] {msg}", flush=True)
            def debug(self, msg): print(f"[DEBUG] {msg}", flush=True)
            def error(self, msg): print(f"[ERROR] {msg}", flush=True)
        
        search_engine = SpotifySearchEngine(logger=FlaskLogger())
        
        # Processar cada música
        songs = metadata if isinstance(metadata, list) else [metadata]
        results = {
            'success': True,
            'total': len(songs),
            'downloaded': 0,
            'failed': 0,
            'errors': []
        }
        
        for song in songs:
            try:
                # Extrair metadados
                title = song.get('name', '')
                artists = song.get('artists', [])
                if isinstance(artists, list) and len(artists) > 0:
                    artist = artists[0] if isinstance(artists[0], str) else artists[0].get('name', '')
                else:
                    artist = str(artists)
                
                duration_ms = song.get('duration', 0)
                duration_sec = duration_ms // 1000 if duration_ms else 180  # Default 3min
                
                print(f"[Spotify Advanced] Procurando: {artist} - {title}")
                
                # Buscar no YouTube com SpotiFlyer algorithm
                video_id = search_engine.search_youtube_music(artist, title, duration_sec)
                
                if not video_id:
                    results['failed'] += 1
                    results['errors'].append(f"{artist} - {title}: Nenhum match encontrado")
                    continue
                
                # Baixar usando yt-dlp
                youtube_url = f"https://www.youtube.com/watch?v={video_id}"
                output_template = str(spotify_path / f"{artist} - {title}.%(ext)s")
                
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': output_template,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '320',
                    }],
                    'quiet': True,
                    'no_warnings': True,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([youtube_url])
                
                results['downloaded'] += 1
                print(f"[Spotify Advanced] ✅ Baixado: {artist} - {title}")
            
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"{artist} - {title}: {str(e)}")
                print(f"[Spotify Advanced] ❌ Erro: {artist} - {title} - {str(e)}")
        
        return jsonify(results)
    
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Tempo esgotado ao obter metadados do Spotify'
        }), 408
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro inesperado: {str(e)}'
        }), 500


@app.route('/api/smart-analyze', methods=['POST'])
def smart_analyze():
    """
    Análise inteligente de URL - detecta automaticamente:
    - Plataforma (YouTube, SoundCloud, Vimeo, TikTok, etc)
    - Tipo de conteúdo (vídeo, áudio, playlist, canal)
    - Metadados relevantes
    - NOVO: Suporta atalhos estilo 9xbuddy
    """
    data = request.get_json()
    url = data.get('url', '')
    
    if not url:
        return jsonify({'success': False, 'error': 'URL não fornecida'}), 400
    
    # Processar atalhos estilo ULTRA DOWN AI
    url = process_ultradown_shortcuts(url)

    # Bloquear proativamente domínios conhecidos por DRM para evitar 500 e dar mensagem clara

    if is_known_drm_site(url):
        return jsonify({
            'success': False,
            'error': 'Conteúdo protegido por DRM — este site de streaming não é suportado.',
            'code': 'drm_protected'
        }), 200
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Detectar plataforma
            platform = 'Unknown'
            extractor = info.get('extractor', '').lower()
            if 'youtube' in extractor:
                platform = 'YouTube'
            elif 'soundcloud' in extractor:
                platform = 'SoundCloud'
            elif 'spotify' in extractor:
                platform = 'Spotify'
            elif 'vimeo' in extractor:
                platform = 'Vimeo'
            elif 'tiktok' in extractor:
                platform = 'TikTok'
            elif 'instagram' in extractor:
                platform = 'Instagram'
            elif 'twitter' in extractor or 'x.com' in url.lower():
                platform = 'Twitter/X'
            elif 'facebook' in extractor:
                platform = 'Facebook'
            elif 'dailymotion' in extractor:
                platform = 'Dailymotion'
            elif 'xhamster' in extractor or 'xhamster' in url.lower():
                platform = 'xHamster'
            else:
                platform = info.get('extractor_key', 'Unknown')
            
            # Detectar se é conteúdo de áudio/música
            is_music = False
            categories = info.get('categories') or []
            tags = info.get('tags') or []
            title = (info.get('title') or '').lower()
            
            if 'soundcloud' in extractor or 'spotify' in extractor:
                is_music = True
            elif categories and any(cat and 'music' in str(cat).lower() for cat in categories):
                is_music = True
            elif tags and any(tag and 'music' in str(tag).lower() for tag in tags):
                is_music = True
            elif 'music' in title or 'audio' in title or 'song' in title:
                is_music = True
            
            # Processar baseado no tipo
            if 'entries' in info:
                # Playlist, canal ou álbum
                videos = []
                for entry in (info.get('entries') or []):
                    if entry:
                        duration = entry.get('duration', 0)
                        duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}" if duration else "N/A"
                        
                        videos.append({
                            'id': entry.get('id', ''),
                            'title': entry.get('title', 'Sem título'),
                            'url': entry.get('url') or entry.get('webpage_url', ''),
                            'duration': duration_str,
                            'thumbnail': entry.get('thumbnail', ''),
                            'uploader': entry.get('uploader', 'Desconhecido'),
                        })
                
                content_type = 'playlist'
                if 'channel' in extractor or 'user' in extractor:
                    content_type = 'channel'
                elif 'album' in str(info.get('title', '')).lower():
                    content_type = 'album'
                
                return jsonify({
                    'success': True,
                    'platform': platform,
                    'content_type': content_type,
                    'is_music': is_music,
                    'title': info.get('title', 'Conteúdo'),
                    'uploader': info.get('uploader', 'Desconhecido'),
                    'video_count': len(videos),
                    'videos': videos
                })
            else:
                # Vídeo ou áudio único
                duration = info.get('duration', 0)
                duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}" if duration else "N/A"
                
                # Extrair formatos disponíveis
                formats = []
                for f in info.get('formats', []):
                    # Incluir apenas formatos de vídeo (não audio-only)
                    if f.get('vcodec') != 'none' and f.get('height'):
                        filesize = f.get('filesize') or f.get('filesize_approx') or 0
                        if filesize > 0:
                            filesize_str = f"{filesize / (1024*1024):.1f}MB"
                        else:
                            filesize_str = "N/A"
                        
                        formats.append({
                            'format_id': f.get('format_id'),
                            'quality': f'{f.get("height")}p',
                            'resolution': f'{f.get("width", "?")}x{f.get("height")}',
                            'filesize': filesize_str,
                            'fps': f.get('fps', 30),
                            'ext': f.get('ext', 'mp4')
                        })
                
                # Ordenar por qualidade (maior primeiro)
                formats.sort(key=lambda x: int(x['quality'].replace('p', '')), reverse=True)
                
                return jsonify({
                    'success': True,
                    'platform': platform,
                    'content_type': 'audio' if is_music else 'video',
                    'is_music': is_music,
                    'type': 'single',
                    'videos': [{
                        'id': info.get('id', ''),
                        'title': info.get('title', 'Sem título'),
                        'url': info.get('webpage_url', url),
                        'duration': duration_str,
                        'thumbnail': info.get('thumbnail', ''),
                        'uploader': info.get('uploader', 'Desconhecido'),
                        'view_count': info.get('view_count', 0),
                        'formats': formats
                    }]
                })
                
    except Exception as e:
        err = str(e)
        # Mapear erros comuns para respostas amigáveis (sem 500)
        drm_markers = ['DRM', 'DRM protection', 'is known to use DRM', 'encrypted HLS', 'Widevine']
        unsupported_markers = ['Unsupported URL', 'unsupported url', 'Unsupported extractor', 'This video is not available']

        if any(m.lower() in err.lower() for m in drm_markers):
            return jsonify({
                'success': False,
                'error': 'Conteúdo protegido por DRM — não suportado. Tente outra fonte (ex.: YouTube, Vimeo).',
                'code': 'drm_protected'
            }), 200
        if any(m.lower() in err.lower() for m in unsupported_markers):
            return jsonify({
                'success': False,
                'error': 'URL não suportada por yt-dlp. Tente outro link.',
                'code': 'unsupported_url'
            }), 200

        return jsonify({
            'success': False,
            'error': f'Erro ao analisar URL: {err}'
        }), 500


@app.route('/api/smart-download', methods=['POST'])
def smart_download():
    """
    Download inteligente - baixa no formato mais adequado automaticamente
    """
    data = request.get_json()
    url = data.get('url', '')
    format_type = data.get('format', 'auto')  # auto, video, audio
    
    if not url:
        return jsonify({'success': False, 'error': 'URL não fornecida'}), 400

    # Normalizar atalhos e bloquear DRM
    url = process_ultradown_shortcuts(url)
    if is_known_drm_site(url):
        return jsonify({'success': False, 'error': 'Conteúdo protegido por DRM — este site de streaming não é suportado.', 'code': 'drm_protected'}), 200
    
    try:
        # Configurar opções baseadas no formato
        if format_type == 'audio':
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': str(DOWNLOAD_PATH / 'audio' / '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            }
            output_folder = DOWNLOAD_PATH / 'audio'
        else:
            ydl_opts = {
                'format': 'best',
                'outtmpl': str(DOWNLOAD_PATH / 'video' / '%(title)s.%(ext)s'),
            }
            output_folder = DOWNLOAD_PATH / 'video'
        
        output_folder.mkdir(exist_ok=True)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        return jsonify({
            'success': True,
            'message': 'Download concluído!',
            'output_path': str(output_folder)
        })
        
    except Exception as e:
        err = str(e)
        drm_markers = ['DRM', 'DRM protection', 'is known to use DRM', 'encrypted HLS', 'Widevine']
        if any(m.lower() in err.lower() for m in drm_markers):
            return jsonify({'success': False, 'error': 'Conteúdo protegido por DRM — não suportado.', 'code': 'drm_protected'}), 200
        return jsonify({'success': False, 'error': f'Erro no download: {err}'}), 500


@app.route('/api/downloads')
def list_downloads():
    """Lista todos os arquivos baixados (recursivo), categorizado"""
    files = []
    for dirpath, dirnames, filenames in os.walk(DOWNLOAD_PATH):
        for name in filenames:
            try:
                p = Path(dirpath) / name
                rel = p.relative_to(DOWNLOAD_PATH)
                files.append({
                    'name': name,
                    'path': str(rel),
                    'size': p.stat().st_size,
                    'modified': datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
            except Exception:
                continue
    # Ordena por data (desc)
    files.sort(key=lambda f: f['modified'], reverse=True)
    return jsonify({'files': files, 'base': str(DOWNLOAD_PATH)})


# ============================================================
# NOVAS ROTAS: PÁGINAS ESTILO DESKTOP APP (ULTRA DOWN AI)
# ============================================================

@app.route('/desktop')
def desktop_page():
    """Página principal estilo desktop app - interface limpa e rápida"""
    return render_template('desktop.html')

@app.route('/express')
def express_page():
    """Página Express - download ultra-rápido com um clique"""
    return render_template('express.html')

@app.route('/batch')
def batch_page():
    """Página Batch - download em massa otimizado"""
    return render_template('batch.html')


@app.route('/api/open-download-folder', methods=['POST'])
def open_download_folder():
    """Abre a pasta de downloads no Windows Explorer do host"""
    try:
        import subprocess
        
        # Lê o caminho configurado
        config_file = Path('config.json')
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            host_path = config.get('host_download_path', r'C:\Users\renov\Documents\z\downloads')
        else:
            host_path = r'C:\Users\renov\Documents\z\downloads'
        
        # Verifica se está rodando em Docker
        is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER', False)
        
        if is_docker:
            # Executa PowerShell no host para abrir o Explorer
            # Usa docker exec reverso ou simplesmente tenta executar via subprocess
            try:
                # Comando PowerShell para abrir o Explorer
                ps_command = f'explorer.exe "{host_path}"'
                
                # Tenta executar diretamente (funciona se o Docker tiver acesso ao host)
                subprocess.Popen(['powershell.exe', '-Command', ps_command], 
                               shell=False,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                
                return jsonify({
                    'success': True,
                    'message': 'Pasta de downloads aberta no Windows Explorer',
                    'path': host_path,
                    'is_docker': True
                })
            except Exception:
                # Se falhar, retorna instrução para o usuário
                return jsonify({
                    'success': False,
                    'error': 'Não foi possível abrir automaticamente',
                    'path': host_path,
                    'is_docker': True
                })
        else:
            # Se está rodando nativamente no Windows/macOS/Linux
            import platform

            # Preferir pasta configurada do host, senão caminho padrão interno
            preferred_path = Path(host_path) if host_path else DOWNLOAD_PATH.absolute()

            if platform.system() == 'Windows':
                subprocess.Popen(['explorer', str(preferred_path)])
            elif platform.system() == 'Darwin':  # macOS
                subprocess.Popen(['open', str(preferred_path)])
            else:  # Linux
                subprocess.Popen(['xdg-open', str(preferred_path)])

            return jsonify({
                'success': True,
                'message': 'Pasta de downloads aberta',
                'path': str(preferred_path),
                'is_docker': False
            })
    except Exception as e:


        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/select-folder', methods=['POST'])
def select_folder():
    """Abre um seletor de pasta nativo e retorna o caminho escolhido"""
    try:
        # Pasta inicial sugerida: host_download_path ou pasta padrão de Vídeos
        initial_dir = get_windows_videos_folder()
        config_file = Path('config.json')
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                initial_dir = cfg.get('host_download_path', initial_dir)

        # Usar tkinter para exibir diálogo nativo
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            selected = filedialog.askdirectory(initialdir=initial_dir, title='Selecione a pasta de downloads')
            root.destroy()
        except Exception as te:
            return jsonify({'success': False, 'error': f'Falha ao abrir seletor nativo: {te}'}), 500

        if not selected:
            return jsonify({'success': False, 'cancelled': True})

        return jsonify({'success': True, 'path': selected})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config', methods=['GET'])
def get_config():
    """Retorna configurações do servidor"""
    try:
        # Lê configurações do arquivo se existir
        config_file = Path('config.json')
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            # Configuração padrão - usa pasta Meus Vídeos do Windows
            default_videos_folder = get_windows_videos_folder()
            config = {
                'download_path': str(DOWNLOAD_PATH.absolute()),
                'host_download_path': default_videos_folder
            }
        
        default_videos_folder = get_windows_videos_folder()

        # Defaults adicionais para painel avançado / notificações
        advanced_defaults = {
            'simultaneous_transfers': 4,  # 1..8
            'prevent_sleep': True,
            'create_subdirs': True,
            'number_files': True,
            'skip_duplicates': True,
            'generate_m3u': True,
            'embed_subtitles': False,
            'auto_audio_tags': True,
            'notify_on_finish': True,
            'notify_reminders': True,
            'notify_recommendations': True,
            'confirm_exit_incomplete': True,
            'confirm_remove_items': False,
            'offer_channel_bulk': True,
            'show_in_notification_center': True,
            'play_notification_sound': True
        }
        # Preenche valores ausentes
        for k, v in advanced_defaults.items():
            config.setdefault(k, v)
        
        return jsonify({
            'success': True,
            'config': config,
            'download_path': config.get('download_path', str(DOWNLOAD_PATH.absolute())),
            'host_download_path': config.get('host_download_path', default_videos_folder),
            'audio_path': str(DOWNLOAD_PATH / 'audio'),
            'video_path': str(DOWNLOAD_PATH / 'video'),
            'default_videos_folder': default_videos_folder
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/config', methods=['POST'])
def update_config():
    """Atualiza configurações do servidor"""
    try:
        data = request.get_json()
        
        # Lê configuração existente ou cria nova
        config_file = Path('config.json')
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {}
        
        # Campos permitidos para atualização
        allowed_keys = {
            'host_download_path',
            'simultaneous_transfers',
            'prevent_sleep',
            'create_subdirs',
            'number_files',
            'skip_duplicates',
            'generate_m3u',
            'embed_subtitles',
            'auto_audio_tags',
            'notify_on_finish',
            'notify_reminders',
            'notify_recommendations',
            'confirm_exit_incomplete',
            'confirm_remove_items',
            'offer_channel_bulk',
            'show_in_notification_center',
            'play_notification_sound'
        }

        for key, value in data.items():
            if key in allowed_keys:
                config[key] = value
        
        # Salva configurações
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True,
            'message': 'Configurações salvas com sucesso',
            'config': config
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/disk-space', methods=['GET'])
def get_disk_space():
    """Retorna informações de espaço em disco"""
    try:
        import shutil
        
        # Obtém caminho configurado ou padrão
        config_file = Path('config.json')
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            download_path = config.get('host_download_path', get_windows_videos_folder())
        else:
            download_path = get_windows_videos_folder()
        
        # Obtém informações do disco
        disk_usage = shutil.disk_usage(download_path)
        
        # Calcula tamanho da pasta de downloads
        downloads_size = 0
        if DOWNLOAD_PATH.exists():
            for dirpath, dirnames, filenames in os.walk(DOWNLOAD_PATH):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        downloads_size += os.path.getsize(filepath)
                    except (OSError, FileNotFoundError):
                        pass
        
        def format_bytes(bytes_size):
            """Formata bytes para formato legível"""
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if bytes_size < 1024.0:
                    return f"{bytes_size:.2f} {unit}"
                bytes_size /= 1024.0
            return f"{bytes_size:.2f} PB"
        
        return jsonify({
            'success': True,
            'disk': {
                'total': disk_usage.total,
                'used': disk_usage.used,
                'free': disk_usage.free,
                'percent_used': round((disk_usage.used / disk_usage.total) * 100, 2),
                'total_formatted': format_bytes(disk_usage.total),
                'used_formatted': format_bytes(disk_usage.used),
                'free_formatted': format_bytes(disk_usage.free)
            },
            'downloads': {
                'size': downloads_size,
                'size_formatted': format_bytes(downloads_size)
            },
            'path': download_path
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/spotify-cache-stats', methods=['GET'])
def get_spotify_cache_stats():
    """Retorna estatísticas do cache SQLite do Spotify"""
    try:
        cache = get_cache_manager()
        stats = cache.get_cache_stats()
        return jsonify({
            'success': True,
            **stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/spotify-cache-clean', methods=['POST'])
def clean_spotify_cache():
    """Limpa cache antigo (>90 dias)"""
    try:
        cache = get_cache_manager()
        result = cache.clean_old_cache(days=90)
        return jsonify({
            'success': True,
            **result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


def main():
    """Inicia o servidor"""
    try:
        print("\n" + "="*60)
        print("SERVIDOR WEB DE DOWNLOAD DE VIDEOS")
        print("="*60)
        print(f"\nPasta de downloads: {DOWNLOAD_PATH.absolute()}")
        print("\nIniciando servidor...")
        print("\nAcesse: http://localhost:5002")
        print("\nPressione CTRL+C para parar o servidor\n")
        print("="*60 + "\n")
    except UnicodeEncodeError:
        print("\n" + "="*60)
        print("SERVIDOR WEB DE DOWNLOAD DE VIDEOS")
        print("="*60)
        print(f"\nPasta de downloads: {DOWNLOAD_PATH.absolute()}")
        print("="*60 + "\n")
    
    try:
        # Abre o navegador após o servidor iniciar
        threading.Timer(1.0, lambda: webbrowser.open('http://localhost:5002')).start()
    except Exception:
        pass
    app.run(debug=True, host='0.0.0.0', port=5002)


if __name__ == '__main__':
    main()
