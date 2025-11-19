"""
Spotify Advanced Search Module
Inspired by SpotiFlyer - Implements fuzzy matching and intelligent scoring
"""

import re
from rapidfuzz import fuzz
from typing import List, Dict, Tuple, Optional
import yt_dlp


class SpotifySearchEngine:
    """Advanced search engine for finding best YouTube matches for Spotify tracks"""
    
    # Matching thresholds
    FUZZY_THRESHOLD = 85  # 85% similarity required (SpotiFlyer standard)
    MIN_DURATION_SECONDS = 30  # Skip results under 30 seconds
    MAX_DURATION_SECONDS = 600  # Skip results over 10 minutes
    
    def __init__(self, logger=None):
        self.logger = logger or self._dummy_logger()
    
    def _dummy_logger(self):
        """Fallback logger if none provided"""
        class DummyLogger:
            def info(self, msg): print(f"[INFO] {msg}")
            def debug(self, msg): print(f"[DEBUG] {msg}")
            def error(self, msg): print(f"[ERROR] {msg}")
        return DummyLogger()
    
    def clean_search_query(self, artist: str, title: str) -> List[Tuple[str, str]]:
        """
        Generate fallback search queries with progressively cleaner metadata
        Returns list of (artist, title) tuples to try in order
        """
        queries = []
        
        # Original exact match
        queries.append((artist, title))
        
        # Remove featured artists: "Alok feat. BARBZ" -> "Alok"
        artist_clean = re.sub(r'\s+(feat\.|ft\.|featuring|with)\s+.*', '', artist, flags=re.IGNORECASE)
        if artist_clean != artist:
            queries.append((artist_clean, title))
        
        # Remove parentheses/brackets from title: "Song (Remix)" -> "Song"
        title_clean = re.sub(r'\s*[\(\[].*?[\)\]]', '', title)
        if title_clean != title:
            queries.append((artist, title_clean))
        
        # Both cleaned
        if artist_clean != artist and title_clean != title:
            queries.append((artist_clean, title_clean))
        
        # Remove special characters: "Artist & Artist" -> "Artist Artist"
        artist_simple = re.sub(r'[&,/]', ' ', artist_clean).strip()
        title_simple = re.sub(r'[&,/]', ' ', title_clean).strip()
        if artist_simple != artist_clean or title_simple != title_clean:
            queries.append((artist_simple, title_simple))
        
        # Split multi-artist and try first artist only
        first_artist = artist_clean.split(',')[0].split('&')[0].strip()
        if first_artist != artist_clean:
            queries.append((first_artist, title_clean))
        
        return queries
    
    def search_youtube_music(self, artist: str, title: str, duration_sec: int) -> Optional[str]:
        """
        Search YouTube Music for best match using SpotiFlyer algorithm
        Returns: YouTube video ID or None
        """
        # Generate fallback queries
        queries = self.clean_search_query(artist, title)
        
        for query_artist, query_title in queries:
            search_query = f"{query_artist} - {query_title}"
            self.logger.info(f"Tentando: {search_query}")
            
            try:
                # Search YouTube Music (ytsearch10 = top 10 results)
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'format': 'bestaudio/best',
                    'skip_download': True,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    search_results = ydl.extract_info(f"ytsearch10:{search_query}", download=False)
                    
                    if not search_results or 'entries' not in search_results:
                        continue
                    
                    # Apply SpotiFlyer scoring algorithm
                    scored_results = []
                    for entry in search_results['entries']:
                        if not entry:
                            continue
                        
                        entry_duration = entry.get('duration', 0) or 0
                        entry_title = entry.get('title', '')
                        
                        score = self._calculate_match_score(
                            result_title=entry_title,
                            result_duration=entry_duration,
                            target_artist=query_artist,
                            target_title=query_title,
                            target_duration=duration_sec,
                            track_artists=[query_artist]  # Simplification
                        )
                        
                        if score > 0:
                            scored_results.append((entry['id'], score, entry['title']))
                    
                    # Sort by best score
                    scored_results.sort(key=lambda x: x[1], reverse=True)
                    
                    if scored_results:
                        best_match = scored_results[0]
                        self.logger.info(f"✅ Match encontrado: {best_match[2]} (score: {best_match[1]:.1f})")
                        return best_match[0]  # Return video ID
            
            except Exception as e:
                self.logger.error(f"Erro na busca '{search_query}': {str(e)}")
                continue
        
        self.logger.error(f"❌ Nenhum match encontrado para: {artist} - {title}")
        return None
    
    def _calculate_match_score(
        self,
        result_title: str,
        result_duration: int,
        target_artist: str,
        target_title: str,
        target_duration: int,
        track_artists: List[str]
    ) -> float:
        """
        SpotiFlyer scoring algorithm (adapted from Kotlin)
        Returns: 0-100 score (higher is better)
        """
        # Normalize strings
        result_title_clean = result_title.lower().replace('-', ' ').replace('/', ' ')
        target_title_clean = target_title.lower()
        
        # 1. Check if at least one word from title appears in result (85% fuzzy match)
        has_common_word = False
        for word in target_title_clean.split():
            if len(word) > 2:  # Skip short words
                if fuzz.partial_ratio(word, result_title_clean) > self.FUZZY_THRESHOLD:
                    has_common_word = True
                    break
        
        if not has_common_word:
            self.logger.debug(f"Rejeitado (sem palavra comum): {result_title}")
            return 0.0
        
        # 2. Artist match (fuzzy search)
        artist_match_count = 0.0
        for artist in track_artists:
            # Check if artist appears in title
            if fuzz.partial_ratio(artist.lower(), result_title_clean) > self.FUZZY_THRESHOLD:
                artist_match_count += 1
        
        if artist_match_count == 0:
            self.logger.debug(f"Rejeitado (artista não encontrado): {result_title}")
            return 0.0
        
        artist_match_percent = (artist_match_count / len(track_artists)) * 100.0
        
        # 3. Duration match (penalize time differences)
        if result_duration <= 0 or target_duration <= 0:
            duration_match_percent = 50.0  # Neutral score if duration unknown
        else:
            # Filter out results too short or too long
            if result_duration < self.MIN_DURATION_SECONDS or result_duration > self.MAX_DURATION_SECONDS:
                self.logger.debug(f"Rejeitado (duração inválida): {result_title} ({result_duration}s)")
                return 0.0
            
            # SpotiFlyer formula: 100 - ((difference²/duration) * 100)
            # Note: non_match_value is already a percentage (0-1 range scaled by division)
            difference = abs(result_duration - target_duration)
            non_match_value = (difference * difference) / float(target_duration)
            duration_match_percent = max(0, 100.0 - non_match_value)  # Fixed: removed extra * 100
        
        # 4. Final score = average of artist and duration matches
        avg_score = (artist_match_percent + duration_match_percent) / 2.0
        
        return avg_score


def test_search():
    """Test function to verify search works"""
    engine = SpotifySearchEngine()
    
    # Test with a known song
    video_id = engine.search_youtube_music(
        artist="Alok",
        title="Fever",
        duration_sec=180  # 3 minutes
    )
    
    if video_id:
        print(f"✅ Teste bem-sucedido! Video ID: {video_id}")
        print(f"URL: https://www.youtube.com/watch?v={video_id}")
    else:
        print("❌ Teste falhou - nenhum resultado encontrado")


if __name__ == '__main__':
    test_search()
