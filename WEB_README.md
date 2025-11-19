# 🌐 Interface Web para Download de Vídeos

Interface web local e intuitiva para fazer download de vídeos de mais de 1000 sites.

## 🚀 Como Usar

### 1. Instale as dependências (se ainda não instalou):

```powershell
pip install -r requirements.txt
```

### 2. Inicie o servidor web:

```powershell
python web_downloader.py
```

### 3. Acesse no navegador:

```
http://localhost:5000
```

## ✨ Funcionalidades da Interface Web

### 📋 Análise de URL
- Cole qualquer URL de vídeo ou playlist
- O sistema analisa automaticamente e lista todos os vídeos
- Mostra informações detalhadas: título, duração, uploader, thumbnail

### 🎬 Download Individual
- Baixe vídeos individualmente com a qualidade desejada
- Opção para baixar apenas áudio (MP3)
- Barra de progresso em tempo real
- Informações de velocidade e tempo estimado

### 📦 Download em Massa
- Detecta playlists automaticamente
- Botões para baixar todos os vídeos de uma vez
- Opção para baixar apenas o áudio de todos

### ⚙️ Opções Disponíveis
- **Qualidade**: Melhor, 1080p, 720p, 480p, 360p
- **Formato**: MP4 (vídeo) ou MP3 (áudio)
- **Progresso**: Acompanhe cada download em tempo real

## 🎯 Exemplos de Uso

### Baixar um vídeo do YouTube
1. Acesse http://localhost:5000
2. Cole a URL: `https://www.youtube.com/watch?v=VIDEO_ID`
3. Clique em "🔍 Analisar"
4. Escolha a qualidade e clique em "📥 Baixar Vídeo"

### Baixar uma playlist completa
1. Cole a URL da playlist: `https://www.youtube.com/playlist?list=PLAYLIST_ID`
2. Clique em "🔍 Analisar"
3. Clique em "📥 Baixar Todos" para baixar todos os vídeos

### Extrair apenas áudio
1. Cole a URL do vídeo
2. Clique em "🔍 Analisar"
3. Clique em "🎵 Baixar Áudio" ou marque a opção "Apenas áudio (MP3)"

## 🌐 Sites Suportados

A interface suporta os mesmos 1000+ sites do script CLI, incluindo:

- ✅ YouTube (vídeos, playlists, canais)
- ✅ Vimeo
- ✅ Facebook
- ✅ Instagram
- ✅ Twitter/X
- ✅ TikTok
- ✅ Twitch
- ✅ Dailymotion
- ✅ Reddit
- ✅ E muitos outros...

## 📁 Arquivos

```
.
├── web_downloader.py      # Servidor Flask (backend)
├── templates/
│   └── index.html         # Interface web (frontend)
├── downloads/             # Pasta onde os vídeos são salvos
└── requirements.txt       # Dependências
```

## 🔧 Arquitetura

### Backend (Flask)
- **`/`**: Página principal
- **`/api/analyze`**: Analisa URL e retorna lista de vídeos
- **`/api/download`**: Inicia download de um vídeo
- **`/api/download-status/<video_id>`**: Retorna status do download
- **`/api/downloads`**: Lista arquivos baixados

### Frontend (HTML/CSS/JS)
- Interface responsiva e moderna
- Atualização de progresso em tempo real
- Suporte para múltiplos downloads simultâneos
- Design gradiente e animações suaves

## 💡 Dicas

### Melhor Desempenho
- Para playlists grandes, os downloads são iniciados com 1 segundo de intervalo
- Você pode baixar múltiplos vídeos ao mesmo tempo

### Troubleshooting
- Se o servidor não iniciar, verifique se a porta 5000 está livre
- Para mudar a porta, edite `web_downloader.py`: `app.run(port=OUTRA_PORTA)`

### Acessar de outros dispositivos na rede
O servidor já está configurado com `host='0.0.0.0'`, então você pode acessar de outros dispositivos usando:
```
http://SEU_IP_LOCAL:5000
```

## 🎨 Personalização

### Mudar cores do tema
Edite as cores em `templates/index.html` na seção `<style>`:
```css
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
```

### Mudar pasta de downloads
Edite `web_downloader.py`:
```python
DOWNLOAD_PATH = Path("sua_pasta_aqui")
```

## 🔒 Segurança

- O servidor é configurado para uso **local apenas** por padrão
- Não exponha o servidor diretamente à internet sem autenticação
- Para produção, adicione autenticação e HTTPS

## 📝 Notas

- ⚠️ Respeite direitos autorais e termos de serviço
- ⚠️ Use apenas para conteúdo que você tem permissão
- ⚠️ A velocidade depende da sua conexão

---

**Desenvolvido com ❤️ usando Flask + Python + yt-dlp**
