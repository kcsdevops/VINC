# 🎬 Downloader de Vídeos Universal

Automação em Python para fazer download de vídeos de mais de 1000 sites diferentes, incluindo YouTube, Vimeo, Facebook, Instagram, Twitter, TikTok e muitos outros.

## 🌟 Recursos

- ✅ Suporta **1000+ sites** (YouTube, Vimeo, Facebook, Instagram, TikTok, Twitter, Twitch, etc.)
- ✅ Download de vídeos em diversas qualidades (best, 1080p, 720p, 480p, 360p)
- ✅ Download apenas de áudio (MP3)
- ✅ Suporte para playlists completas
- ✅ Interface interativa amigável
- ✅ Modo linha de comando
- ✅ Barra de progresso em tempo real
- ✅ Informações detalhadas do vídeo antes do download

## 📋 Requisitos

- Python 3.7 ou superior
- yt-dlp (instalado automaticamente)

## 🚀 Instalação

1. **Clone ou baixe os arquivos do projeto**

2. **Instale as dependências:**

```bash
pip install -r requirements.txt
```

Ou instale manualmente:

```bash
pip install yt-dlp
```

## 💻 Como Usar

### Modo Interativo (Recomendado)

Execute o script sem argumentos para usar o menu interativo:

```bash
python video_downloader.py
```

O menu interativo permite:
- Colar a URL do vídeo
- Ver informações do vídeo antes de baixar
- Escolher qualidade e formato
- Baixar playlists completas

### Modo Linha de Comando

Para download rápido direto:

```bash
python video_downloader.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Uso Programático

Você também pode importar e usar a classe em seus próprios scripts:

```python
from video_downloader import VideoDownloader

# Criar instância
downloader = VideoDownloader(download_path="meus_videos")

# Download simples
downloader.download("https://www.youtube.com/watch?v=VIDEO_ID")

# Download em qualidade específica
downloader.download(
    url="https://vimeo.com/VIDEO_ID",
    quality="720p",
    format_type="mp4"
)

# Download apenas áudio
downloader.download(
    url="https://www.youtube.com/watch?v=VIDEO_ID",
    audio_only=True
)

# Download de playlist completa
downloader.download(
    url="https://www.youtube.com/playlist?list=PLAYLIST_ID",
    playlist=True
)

# Obter informações sem baixar
info = downloader.get_video_info("https://www.youtube.com/watch?v=VIDEO_ID")
print(info)
```

## 🎯 Exemplos de Uso

### Baixar vídeo do YouTube em melhor qualidade

```bash
python video_downloader.py
# Cole a URL: https://www.youtube.com/watch?v=dQw4w9WgXcQ
# Escolha opção: 1
```

### Baixar apenas áudio (MP3)

```bash
python video_downloader.py
# Cole a URL do vídeo
# Escolha opção: 4
```

### Baixar playlist completa

```bash
python video_downloader.py
# Cole a URL da playlist
# Escolha opção: 5
```

### Baixar vídeo do Instagram, TikTok, etc.

```bash
python video_downloader.py
# Cole a URL do Instagram/TikTok/etc
# Escolha a qualidade desejada
```

## 🌐 Sites Suportados

O script suporta mais de 1000 sites, incluindo:

### Redes Sociais
- YouTube (vídeos e playlists)
- Facebook
- Instagram (posts e stories)
- Twitter/X
- TikTok
- Reddit

### Plataformas de Vídeo
- Vimeo
- Dailymotion
- Twitch (VODs e clips)
- Rumble

### Educacional
- Coursera
- Udemy
- Khan Academy

### E muitos outros...

Para ver a lista completa de sites suportados, visite:
https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md

## 📁 Estrutura de Arquivos

```
.
├── video_downloader.py    # Script principal
├── requirements.txt       # Dependências
├── README.md             # Este arquivo
└── downloads/            # Pasta onde os vídeos são salvos (criada automaticamente)
```

## ⚙️ Opções de Qualidade

- **best**: Melhor qualidade disponível
- **1080p**: Full HD
- **720p**: HD
- **480p**: SD
- **360p**: Baixa qualidade
- **audio**: Apenas áudio em MP3

## 🔧 Personalização

Você pode personalizar o comportamento editando o script `video_downloader.py`:

- Mudar pasta padrão de downloads
- Ajustar formatos de saída
- Modificar qualidade padrão de áudio
- Adicionar hooks personalizados

## ❓ Solução de Problemas

### Erro: "yt-dlp não está instalado"
```bash
pip install yt-dlp
```

### Erro ao baixar de sites específicos
Certifique-se de ter a versão mais recente do yt-dlp:
```bash
pip install --upgrade yt-dlp
```

### Vídeos privados ou protegidos
Alguns vídeos podem exigir autenticação. O yt-dlp suporta cookies de navegador:
```python
ydl_opts['cookiefile'] = 'cookies.txt'
```

### Erro de codec/formato
Instale o FFmpeg para melhor suporte a conversão:
- Windows: Baixe de https://ffmpeg.org/download.html
- Linux: `sudo apt install ffmpeg`
- macOS: `brew install ffmpeg`

## 📝 Notas Importantes

- ⚠️ Respeite os direitos autorais e termos de serviço dos sites
- ⚠️ Use apenas para conteúdo que você tem permissão para baixar
- ⚠️ Alguns sites podem bloquear downloads automáticos
- ⚠️ A velocidade de download depende da sua conexão e do servidor

## 🔄 Atualizações

Para manter o downloader funcionando com os sites mais recentes:

```bash
pip install --upgrade yt-dlp
```

## 📄 Licença

Este projeto é fornecido "como está" para fins educacionais.

## 🤝 Contribuições

Sinta-se livre para melhorar o código e adicionar novas funcionalidades!

## 📧 Suporte

Para problemas relacionados a sites específicos, consulte a documentação do yt-dlp:
https://github.com/yt-dlp/yt-dlp

---

**Desenvolvido com ❤️ usando Python e yt-dlp**
