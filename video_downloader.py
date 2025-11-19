"""
Automação para Download de Vídeos
Suporta YouTube, Vimeo, Facebook, Instagram, Twitter, TikTok e muitos outros sites
Utiliza yt-dlp (fork melhorado do youtube-dl)
"""

import os
import sys
from pathlib import Path
try:
    import yt_dlp
except ImportError:
    print("Erro: yt-dlp não está instalado.")
    print("Execute: pip install yt-dlp")
    sys.exit(1)


class VideoDownloader:
    """Classe para fazer download de vídeos de diversos sites"""
    
    def __init__(self, download_path="downloads"):
        """
        Inicializa o downloader
        
        Args:
            download_path: Caminho onde os vídeos serão salvos
        """
        self.download_path = Path(download_path)
        self.download_path.mkdir(exist_ok=True)
        
    def download(self, url, quality="best", format_type="mp4", 
                 audio_only=False, playlist=False):
        """
        Faz download de um vídeo
        
        Args:
            url: URL do vídeo
            quality: Qualidade do vídeo ('best', '1080p', '720p', '480p', '360p')
            format_type: Formato do arquivo ('mp4', 'mkv', 'webm')
            audio_only: Se True, baixa apenas o áudio em MP3
            playlist: Se True, baixa toda a playlist
            
        Returns:
            bool: True se o download foi bem-sucedido
        """
        
        # Configurações base
        ydl_opts = {
            'outtmpl': str(self.download_path / '%(title)s.%(ext)s'),
            'progress_hooks': [self._progress_hook],
            'quiet': False,
            'no_warnings': False,
        }
        
        # Configuração para playlist
        if not playlist:
            ydl_opts['noplaylist'] = True
        
        # Configuração para áudio
        if audio_only:
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            # Configuração de qualidade e formato
            if quality == "best":
                format_str = f'bestvideo[ext={format_type}]+bestaudio[ext=m4a]/best[ext={format_type}]/best'
            else:
                height = quality.replace('p', '')
                format_str = f'bestvideo[height<={height}][ext={format_type}]+bestaudio[ext=m4a]/best[height<={height}]/best'
            
            ydl_opts.update({
                'format': format_str,
                'merge_output_format': format_type,
            })
        
        try:
            print(f"\n{'='*60}")
            print(f"Iniciando download de: {url}")
            print(f"Pasta de destino: {self.download_path.absolute()}")
            print(f"{'='*60}\n")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extrai informações do vídeo
                info = ydl.extract_info(url, download=False)
                
                if 'entries' in info:
                    # É uma playlist
                    print(f"📋 Playlist detectada: {info.get('title', 'Sem título')}")
                    print(f"   Total de vídeos: {len(info['entries'])}\n")
                else:
                    # É um único vídeo
                    print(f"📹 Vídeo: {info.get('title', 'Sem título')}")
                    print(f"   Duração: {self._format_duration(info.get('duration', 0))}")
                    print(f"   Uploader: {info.get('uploader', 'Desconhecido')}\n")
                
                # Faz o download
                ydl.download([url])
                
            print(f"\n✅ Download concluído com sucesso!")
            return True
            
        except Exception as e:
            print(f"\n❌ Erro ao fazer download: {str(e)}")
            return False
    
    def _progress_hook(self, d):
        """Hook para mostrar progresso do download"""
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            
            if total > 0:
                percent = (downloaded / total) * 100
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                
                speed_str = self._format_bytes(speed) + "/s" if speed else "N/A"
                
                print(f"\r⬇️  Progresso: {percent:.1f}% | "
                      f"Velocidade: {speed_str} | "
                      f"ETA: {eta}s", end='', flush=True)
        
        elif d['status'] == 'finished':
            print(f"\n✓ Download finalizado. Processando arquivo...")
    
    def _format_bytes(self, bytes_num):
        """Formata bytes para formato legível"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_num < 1024.0:
                return f"{bytes_num:.2f} {unit}"
            bytes_num /= 1024.0
        return f"{bytes_num:.2f} TB"
    
    def _format_duration(self, seconds):
        """Formata duração em segundos para HH:MM:SS"""
        if not seconds:
            return "N/A"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
    
    def get_video_info(self, url):
        """
        Obtém informações sobre o vídeo sem fazer download
        
        Args:
            url: URL do vídeo
            
        Returns:
            dict: Informações do vídeo
        """
        ydl_opts = {'quiet': True, 'no_warnings': True}
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if 'entries' in info:
                    # Playlist
                    return {
                        'type': 'playlist',
                        'title': info.get('title', 'Sem título'),
                        'count': len(info['entries']),
                        'entries': [
                            {
                                'title': entry.get('title'),
                                'duration': entry.get('duration'),
                                'url': entry.get('webpage_url')
                            }
                            for entry in info['entries'][:5]  # Primeiros 5
                        ]
                    }
                else:
                    # Vídeo único
                    return {
                        'type': 'video',
                        'title': info.get('title', 'Sem título'),
                        'duration': info.get('duration', 0),
                        'uploader': info.get('uploader', 'Desconhecido'),
                        'view_count': info.get('view_count', 0),
                        'description': info.get('description', '')[:200]
                    }
        except Exception as e:
            return {'error': str(e)}


def menu_interativo():
    """Menu interativo para o usuário"""
    print("\n" + "="*60)
    print("🎬 DOWNLOADER DE VÍDEOS UNIVERSAL")
    print("="*60)
    print("\nSites suportados:")
    print("  • YouTube, YouTube Music")
    print("  • Vimeo, Dailymotion")
    print("  • Facebook, Instagram, Twitter/X")
    print("  • TikTok, Twitch")
    print("  • E muitos outros (1000+ sites)")
    print("="*60 + "\n")
    
    downloader = VideoDownloader()
    
    while True:
        url = input("📎 Cole a URL do vídeo (ou 'sair' para encerrar): ").strip()
        
        if url.lower() in ['sair', 'exit', 'quit', 'q']:
            print("\n👋 Até logo!")
            break
        
        if not url:
            continue
        
        # Mostra informações do vídeo
        print("\n🔍 Obtendo informações...")
        info = downloader.get_video_info(url)
        
        if 'error' in info:
            print(f"❌ Erro: {info['error']}\n")
            continue
        
        print("\n📊 Informações:")
        if info['type'] == 'playlist':
            print(f"   Tipo: Playlist")
            print(f"   Título: {info['title']}")
            print(f"   Vídeos: {info['count']}")
        else:
            print(f"   Título: {info['title']}")
            print(f"   Duração: {downloader._format_duration(info['duration'])}")
            print(f"   Uploader: {info['uploader']}")
        
        # Opções de download
        print("\n⚙️  Opções de download:")
        print("  1. Vídeo em melhor qualidade (MP4)")
        print("  2. Vídeo em 720p (MP4)")
        print("  3. Vídeo em 480p (MP4)")
        print("  4. Apenas áudio (MP3)")
        if info['type'] == 'playlist':
            print("  5. Baixar toda a playlist")
        
        opcao = input("\nEscolha uma opção (1-5): ").strip()
        
        # Processar escolha
        if opcao == '1':
            downloader.download(url, quality="best")
        elif opcao == '2':
            downloader.download(url, quality="720p")
        elif opcao == '3':
            downloader.download(url, quality="480p")
        elif opcao == '4':
            downloader.download(url, audio_only=True)
        elif opcao == '5' and info['type'] == 'playlist':
            downloader.download(url, quality="best", playlist=True)
        else:
            print("❌ Opção inválida!")
        
        print("\n" + "-"*60 + "\n")


def main():
    """Função principal"""
    if len(sys.argv) > 1:
        # Modo linha de comando
        url = sys.argv[1]
        downloader = VideoDownloader()
        downloader.download(url)
    else:
        # Modo interativo
        menu_interativo()


if __name__ == "__main__":
    main()
