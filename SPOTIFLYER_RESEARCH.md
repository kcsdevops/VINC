# SpotiFlyer Research - Descobertas e Implementação

## 📊 Status Atual

**Taxa de sucesso original**: 6.19% (6 de 97 músicas)  
**Objetivo**: 80%+ taxa de sucesso  
**Abordagem**: Estudar SpotiFlyer e implementar técnicas avançadas

---

## 🔬 Análise do SpotiFlyer (Kotlin/Compose Multiplatform)

### Repositório
- **URL**: https://github.com/Shabinder/SpotiFlyer.git
- **Linguagem**: Kotlin
- **Arquivo chave**: `common/providers/src/commonMain/kotlin/com.shabinder.common.providers/youtube_music/YoutubeMusic.kt`

### 🎯 3 Técnicas Principais Descobertas

#### 1. **Fuzzy Matching (FuzzyWuzzy)**
```kotlin
import io.github.shabinder.fuzzywuzzy.diffutils.FuzzySearch

// Aceita 85% de similaridade (não exato!)
if (FuzzySearch.partialRatio(nameWord, resultName) > 85) hasCommonWord = true
if (FuzzySearch.ratio(artist.toLowerCase(), result.artist?.toLowerCase() ?: "") > 85)
```

**Python equivalente** (rapidfuzz):
```python
from rapidfuzz import fuzz

if fuzz.partial_ratio(word, result_title_clean) > 85:
    has_common_word = True
if fuzz.partial_ratio(artist.lower(), result_title_clean) > 85:
    artist_match_count += 1
```

**Benefício**: Aceita variações como "Alok feat. BARBZ" ≈ "Alok" com 85% match

---

#### 2. **Sistema de Scoring Sofisticado**
```kotlin
val artistMatch = (artistMatchNumber / trackArtists.size.toFloat()) * 100F
val durationMatch = 100 - ((difference * difference) / trackDurationSec.toFloat())
val avgMatch = (artistMatch + durationMatch) / 2F
```

**Fórmula de Duração**:
- Diferença de 30s em música de 180s: `(30²/180) = 5`, score = `100 - 5 = 95%`
- Diferença de 16s em música de 180s: `(16²/180) = 1.42`, score = `100 - 1.42 = 98.6%`
- Penaliza quadrado da diferença (grandes diferenças têm peso exponencial)

**Exemplo real** (Alok - Fever):
| Resultado YouTube | Duração | Diff | Score Final |
|-------------------|---------|------|-------------|
| Live Tomorrowland | 164s    | 16s  | **99.3%** ✅ |
| Visualizer        | 150s    | 30s  | 97.5% |
| Extended Mix      | 231s    | 51s  | 92.8% |
| Lyrics            | 146s    | 34s  | 96.8% |

---

#### 3. **Type-Aware Search**
```kotlin
if (result.type == "Song") {
    // Procura artista no campo 'artist'
    if (FuzzySearch.ratio(artist, result.artist) > 85) artistMatchNumber++
} else { // Video
    // Procura artista no campo 'name' (title)
    if (FuzzySearch.partialRatio(artist, result.name) > 85) artistMatchNumber++
}
```

**Benefício**: Videos do YouTube têm formato "Artist - Title" no nome, Songs têm campos separados

---

### 🛠️ Fallback Queries (Multi-tentativa)

SpotiFlyer tenta múltiplas variações da busca:

1. **Query original**: `"Alok feat. BARBZ - Forget You"`
2. **Remove featured artists**: `"Alok - Forget You"`
3. **Remove parênteses**: `"Alok - Forget You"` (sem `(feat. BARBZ)`)
4. **Remove caracteres especiais**: `"Alok Forget You"` (sem `-`, `&`, `,`)
5. **Só primeiro artista**: `"Alok - Forget You"` (ignora "Agents Of Time")

**Código Python** (implementado em `spotify_search.py`):
```python
def clean_search_query(self, artist: str, title: str) -> List[Tuple[str, str]]:
    queries = []
    
    # 1. Original
    queries.append((artist, title))
    
    # 2. Remove featured: "Alok feat. BARBZ" -> "Alok"
    artist_clean = re.sub(r'\s+(feat\.|ft\.|featuring|with)\s+.*', '', artist, flags=re.IGNORECASE)
    queries.append((artist_clean, title))
    
    # 3. Remove parênteses: "Song (Remix)" -> "Song"
    title_clean = re.sub(r'\s*[\(\[].*?[\)\]]', '', title)
    queries.append((artist, title_clean))
    
    # 4. Ambos limpos
    queries.append((artist_clean, title_clean))
    
    # 5. Remove especiais: "Artist & Artist" -> "Artist Artist"
    artist_simple = re.sub(r'[&,/]', ' ', artist_clean).strip()
    title_simple = re.sub(r'[&,/]', ' ', title_clean).strip()
    queries.append((artist_simple, title_simple))
    
    # 6. Só primeiro artista
    first_artist = artist_clean.split(',')[0].split('&')[0].strip()
    queries.append((first_artist, title_clean))
    
    return queries
```

---

## 📁 Arquivo Criado: `spotify_search.py`

### Classe `SpotifySearchEngine`

**Métodos**:
- `clean_search_query()`: Gera 6 variações de busca
- `search_youtube_music()`: Busca no YouTube com fallback automático
- `_calculate_match_score()`: Aplica algoritmo SpotiFlyer (Artist + Duration)

**Constantes**:
```python
FUZZY_THRESHOLD = 85        # 85% similaridade mínima
MIN_DURATION_SECONDS = 30   # Rejeita clipes/trailers
MAX_DURATION_SECONDS = 600  # Rejeita videos longos (>10min)
```

**Teste bem-sucedido**:
```bash
$ python spotify_search.py
[INFO] Tentando: Alok - Fever
✅ Match encontrado: Alok & Agents Of Time - Fever (Live at Tomorrowland 2025) (score: 99.3)
✅ Teste bem-sucedido! Video ID: PngU-cD8-98
URL: https://www.youtube.com/watch?v=PngU-cD8-98
```

---

## ⚠️ Limitações Encontradas

### 1. **Spotify API Rate Limit**
- SpotdL usa Spotify Web API para obter metadados
- API pública tem limite: ~100 requisições/minuto
- Playlist de 97 músicas esgota rate limit
- **Erro**: `SpotifyException: http status: 429, code: -1`

### 2. **Integração Bloqueada**
Tentamos criar `/api/download-spotify-advanced` que:
1. Usa `spotdl save` para obter metadados
2. Itera cada música e aplica `SpotifySearchEngine`
3. Baixa com yt-dlp usando video ID escolhido

**Resultado**: Bloqueado por rate limit no passo 1

---

## ✅ Melhorias Implementadas (Endpoint Original)

Arquivo: `web_downloader.py` → `/api/download-spotify`

```python
cmd = [
    sys.executable,
    '-m', 'spotdl',
    'download',
    url,
    '--output', str(spotify_path),
    '--format', 'mp3',
    '--bitrate', '320k',
    '--threads', '4',                           # ⭐ NOVO: Download paralelo
    '--print-errors',                           # ⭐ NOVO: Erros detalhados
    '--search-query', '{artists} - {title}',    # ⭐ NOVO: Query precisa
]

result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    cwd=str(Path.cwd()),
    timeout=1800  # ⭐ NOVO: 30 minutos (antes: 600s = 10min)
)
```

**Mudanças**:
1. `--threads 4`: Baixa 4 músicas simultaneamente
2. `--print-errors`: Mostra LookupError detalhado
3. `--search-query '{artists} - {title}'`: Usa formato exato do Spotify
4. `timeout=1800`: 30 minutos para playlists grandes (97 músicas)

---

## 🎯 Recomendações Futuras

### Opção 1: **Esperar Rate Limit Resetar**
- Spotify rate limit reseta a cada 30 segundos
- Implementar retry com exponential backoff
- Adicionar sleep(30) entre cada música

### Opção 2: **Usar Spotify Cookie/Token Pessoal**
```python
sp = Spotify(
    client_credentials_manager=SpotifyClientCredentials(
        client_id='YOUR_CLIENT_ID',
        client_secret='YOUR_CLIENT_SECRET'
    )
)
```
- Aumenta rate limit para 10.000 req/dia
- Requer conta Spotify Developer

### Opção 3: **Cachear Metadados**
- Salvar metadados da playlist em JSON
- Reusar sem chamar API novamente
- Spotdl já faz isso parcialmente

### Opção 4: **Implementar SpotiFlyer Completo**
- Extrair metadados via scraping (sem API)
- Usar `spotify_search.py` direto
- Bypass do rate limit do Spotify

---

## 📊 Taxa de Sucesso Esperada

**Baseline** (spotdl padrão): 6.19% (6/97)  
**Com melhorias** (estimativa):
- `--threads 4`: +10% velocidade (não afeta sucesso)
- `--search-query`: +15-20% taxa de sucesso (queries mais precisas)
- **SpotiFlyer algorithm**: +40-50% taxa de sucesso (fuzzy matching + fallbacks)

**Taxa esperada total**: **60-80%** (58-77 músicas de 97)

---

## 🚀 Próximos Passos

1. ✅ **Estudar SpotiFlyer** - CONCLUÍDO
2. ✅ **Criar engine Python** - `spotify_search.py` funcionando
3. ⚠️ **Integração** - Bloqueada por rate limit
4. 🔄 **Testar spotdl melhorado** - Aguardando estabilidade do servidor
5. 📊 **Comparar taxa de sucesso** - Original (6.19%) vs. Melhorado (?)
6. 🛠️ **Implementar fallbacks** - Se taxa ainda baixa, adicionar `spotify_search.py` com retry

---

## 💡 Conclusão

**Descobertas principais**:
- SpotiFlyer usa **fuzzy matching 85%** (não busca exata)
- **Scoring inteligente**: Artist Match + Duration Match (penaliza diferenças quadraticamente)
- **Fallback automático**: 6 variações de query por música
- **Type-aware**: Songs vs. Videos têm estratégias diferentes

**Implementação**:
- ✅ Engine Python criado e testado (score 99.3% no teste)
- ✅ Endpoint spotdl melhorado (threads, search-query, timeout)
- ⚠️ Integração completa bloqueada por Spotify rate limit

**Alternativa viável**: Usar spotdl melhorado e avaliar taxa de sucesso. Se ainda insuficiente, implementar scraping de metadados para bypass do rate limit.
