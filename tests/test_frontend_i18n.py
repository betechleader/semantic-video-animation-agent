import re
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "index.html"


def test_frontend_exposes_persistent_chinese_english_switch() -> None:
    html = FRONTEND.read_text(encoding="utf-8")
    assert 'id="language-select"' in html
    assert '<option value="zh-CN">中文</option>' in html
    assert '<option value="en">English</option>' in html
    assert "semantic-video-language" in html
    assert "languageSelect.addEventListener('change'" in html


def test_all_static_translation_keys_exist_in_both_languages() -> None:
    html = FRONTEND.read_text(encoding="utf-8")
    static_keys = set(re.findall(r'data-i18n(?:-placeholder)?="([A-Za-z0-9_]+)"', html))
    chinese_block, english_and_rest = html.split("'zh-CN': {", 1)[1].split("      en: {", 1)
    english_block = english_and_rest.split("      },\n    };", 1)[0]
    key_pattern = re.compile(r"(?:^|,)\s*([A-Za-z][A-Za-z0-9_]*):", re.MULTILINE)
    assert static_keys <= set(key_pattern.findall(chinese_block))
    assert static_keys <= set(key_pattern.findall(english_block))


def test_video_preview_is_responsive_on_desktop_and_narrow_screens() -> None:
    html = FRONTEND.read_text(encoding="utf-8")
    assert '.preview-shell { display: flex; justify-content: center;' in html
    assert 'max-width: 100%' in html
    assert 'max-height: min(72vh, 760px)' in html
    assert 'object-fit: contain' in html
    assert '@media (max-width: 700px)' in html
    assert '#preview { max-height: 64vh; }' in html
