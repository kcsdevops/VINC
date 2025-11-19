"""Script para popular o cache com músicas existentes"""

from spotify_cache import get_cache_manager
from pathlib import Path

cache = get_cache_manager()

# Simula cache de músicas existentes
spotify_path = Path('downloads/spotify')

count = 0
for mp3_file in sorted(spotify_path.glob('*.mp3'))[:20]:
    # Extrai artista e título do nome do arquivo
    parts = mp3_file.stem.split(' - ', 1)
    if len(parts) == 2:
        artist, title = parts
        cache.cache_track(
            spotify_url=f'https://open.spotify.com/track/{mp3_file.stem}',
            spotify_id=mp3_file.stem[:22],
            title=title.strip(),
            artist=artist.strip(),
            duration_sec=180,
            download_path=str(mp3_file),
            file_size_bytes=mp3_file.stat().st_size,
            success=True,
            score=95.0
        )
        count += 1
        print(f'✅ Cacheado ({count}): {artist} - {title}')

stats = cache.get_cache_stats()
print(f'\n📊 Cache Stats:')
print(f'  Total tracks: {stats["tracks"]["successful"]}')
print(f'  Total size: {stats["tracks"]["total_size_mb"]:.2f} MB')
print(f'  Unique artists: {stats["tracks"]["unique_artists"]}')
print(f'  Cache DB: {stats["cache_db_size_mb"]:.2f} MB')
