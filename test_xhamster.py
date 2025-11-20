import yt_dlp
import traceback

url = 'https://pt.xhamster.com/videos/something-went-wrong-horny-teen-stepsister-cums-loudly-from-raw-night-sex-pov-xhNg0Eq'
ydl_opts = {
    'quiet': True,
    'no_warnings': True,
}

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
        print('=== INFO EXTRACTION ===')
        print(f'ID: {info.get("id")}')
        print(f'Title: {info.get("title")}')
        print(f'Extractor: {info.get("extractor")}')
        print(f'\nCategories: {info.get("categories")} (type: {type(info.get("categories"))})')
        print(f'Tags: {info.get("tags")} (type: {type(info.get("tags"))})')
        print(f'Has entries: {"entries" in info}')
        
        # Testar proteção
        print('\n=== TESTING PROTECTION ===')
        categories = info.get('categories') or []
        tags = info.get('tags') or []
        print(f'After or []: categories={categories}, tags={tags}')
        
        # Testar iteração
        print('\n=== TESTING ITERATION ===')
        if categories:
            print('Iterating categories...')
            for cat in categories:
                print(f'  - {cat}')
        else:
            print('No categories to iterate')
        
        if tags:
            print('Iterating tags...')
            for tag in tags:
                print(f'  - {tag}')
        else:
            print('No tags to iterate')
                
        print('\nSUCCESS!')
        
except Exception as e:
    print(f'\nERROR: {e}')
    print('\nFull traceback:')
    traceback.print_exc()
