"""
Sistema de Internacionalização (i18n)
Inspirado no Windows App Certification Kit
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

class I18nManager:
    """Gerenciador de internacionalização"""
    
    SUPPORTED_LANGUAGES = {
        'pt-br': 'Português (Brasil)',
        'en-us': 'English (US)',
        'es-es': 'Español (España)',
        'fr-fr': 'Français (France)',
        'de-de': 'Deutsch (Deutschland)',
        'it-it': 'Italiano (Italia)',
        'ja-jp': '日本語 (日本)',
        'ko-kr': '한국어 (대한민국)',
        'zh-cn': '简体中文 (中国)',
        'ru-ru': 'Русский (Россия)'
    }
    
    def __init__(self, default_language: str = 'pt-br'):
        self.i18n_dir = Path(__file__).parent / 'i18n'
        self.default_language = default_language
        self.current_language = default_language
        self.strings: Dict[str, Any] = {}
        self.load_language(self.current_language)
    
    def load_language(self, language_code: str) -> bool:
        """Carrega arquivos de strings para o idioma especificado"""
        lang_file = self.i18n_dir / language_code / 'strings.json'
        
        if not lang_file.exists():
            print(f"⚠️  Arquivo de idioma não encontrado: {lang_file}")
            # Fallback para inglês
            lang_file = self.i18n_dir / 'en-us' / 'strings.json'
            if not lang_file.exists():
                print(f"❌ Arquivo de fallback também não encontrado!")
                return False
        
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                self.strings = json.load(f)
            self.current_language = language_code
            print(f"✓ Idioma carregado: {self.SUPPORTED_LANGUAGES.get(language_code, language_code)}")
            return True
        except Exception as e:
            print(f"❌ Erro ao carregar idioma: {e}")
            return False
    
    def get(self, key_path: str, default: str = '') -> str:
        """
        Obtém string traduzida usando notação de ponto
        Exemplo: get('download.title') -> 'Baixar Mídia'
        """
        keys = key_path.split('.')
        value = self.strings
        
        try:
            for key in keys:
                value = value[key]
            return str(value)
        except (KeyError, TypeError):
            print(f"⚠️  Chave não encontrada: {key_path}")
            return default or key_path
    
    def get_all(self, section: str) -> Dict[str, Any]:
        """Obtém todas as strings de uma seção"""
        return self.strings.get(section, {})
    
    def get_available_languages(self) -> Dict[str, str]:
        """Retorna lista de idiomas disponíveis"""
        available = {}
        for code, name in self.SUPPORTED_LANGUAGES.items():
            lang_file = self.i18n_dir / code / 'strings.json'
            if lang_file.exists():
                available[code] = name
        return available
    
    def switch_language(self, language_code: str) -> bool:
        """Troca o idioma atual"""
        if language_code in self.SUPPORTED_LANGUAGES:
            return self.load_language(language_code)
        return False
    
    def format(self, key_path: str, **kwargs) -> str:
        """
        Obtém string traduzida com substituição de variáveis
        Exemplo: format('errors.downloadFailed', filename='video.mp4')
        """
        template = self.get(key_path)
        try:
            return template.format(**kwargs)
        except KeyError as e:
            print(f"⚠️  Variável não encontrada no template: {e}")
            return template
    
    def export_template(self, output_file: str):
        """Exporta template para novo idioma"""
        template_path = self.i18n_dir / 'en-us' / 'strings.json'
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                template = json.load(f)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=2, ensure_ascii=False)
            print(f"✓ Template exportado para: {output_file}")
        else:
            print(f"❌ Template não encontrado: {template_path}")


# Testes
if __name__ == '__main__':
    print("=" * 60)
    print("Sistema de Internacionalização - Teste")
    print("=" * 60)
    
    # Criar instância
    i18n = I18nManager('pt-br')
    
    # Testar tradução de strings
    print("\n📝 Testando strings em PT-BR:")
    print(f"  Título do app: {i18n.get('app.title')}")
    print(f"  Botão download: {i18n.get('download.submitButton')}")
    print(f"  Erro de rede: {i18n.get('errors.networkError')}")
    print(f"  Mensagem de boas-vindas: {i18n.get('messages.welcomeMessage')}")
    
    # Testar mudança de idioma
    print("\n🌐 Mudando para EN-US:")
    i18n.switch_language('en-us')
    print(f"  App title: {i18n.get('app.title')}")
    print(f"  Download button: {i18n.get('download.submitButton')}")
    print(f"  Network error: {i18n.get('errors.networkError')}")
    
    # Testar mudança para espanhol
    print("\n🌐 Mudando para ES-ES:")
    i18n.switch_language('es-es')
    print(f"  Título de la app: {i18n.get('app.title')}")
    print(f"  Botón de descarga: {i18n.get('download.submitButton')}")
    print(f"  Error de red: {i18n.get('errors.networkError')}")
    
    # Listar idiomas disponíveis
    print("\n📋 Idiomas disponíveis:")
    for code, name in i18n.get_available_languages().items():
        print(f"  [{code}] {name}")
    
    # Testar seção completa
    print("\n📦 Seção completa de erros (PT-BR):")
    i18n.switch_language('pt-br')
    errors = i18n.get_all('errors')
    for key, value in errors.items():
        print(f"  {key}: {value}")
    
    print("\n✅ Teste concluído!")
