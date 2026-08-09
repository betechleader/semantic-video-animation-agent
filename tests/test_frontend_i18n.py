import re
from pathlib import Path


FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
HTML = FRONTEND / "index.html"
SCRIPT = FRONTEND / "app.js"
STYLES = FRONTEND / "styles.css"


def translation_keys(block: str) -> set[str]:
    return set(re.findall(r"(?:^|,)\s*([A-Za-z][A-Za-z0-9_]*):", block, re.MULTILINE))


def translation_blocks() -> tuple[str, str]:
    script = SCRIPT.read_text(encoding="utf-8")
    chinese_and_rest = script.split("    'zh-CN': {", 1)[1]
    chinese, english_and_rest = chinese_and_rest.split("    en: {", 1)
    english = english_and_rest.split("    },\n  };", 1)[0]
    return chinese, english


def test_frontend_assets_are_split_without_a_build_dependency() -> None:
    html = HTML.read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="/styles.css" />' in html
    assert '<script src="/app.js" defer></script>' in html
    assert SCRIPT.is_file()
    assert STYLES.is_file()
    assert "<style>" not in html
    assert "<script>" not in html


def test_frontend_exposes_persistent_chinese_english_switch() -> None:
    html = HTML.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    assert 'id="language-select"' in html
    assert '<option value="zh-CN">中文</option>' in html
    assert '<option value="en">English</option>' in html
    assert "semantic-video-language" in script
    assert "refs.languageSelect.addEventListener('change'" in script
    assert "refs.settingsLanguage.addEventListener('change'" in script


def test_all_static_translation_keys_exist_in_both_languages() -> None:
    html = HTML.read_text(encoding="utf-8")
    static_keys = set(re.findall(r'data-i18n(?:-placeholder|-aria-label)?="([A-Za-z0-9_]+)"', html))
    chinese, english = translation_blocks()
    chinese_keys = translation_keys(chinese)
    english_keys = translation_keys(english)
    assert static_keys <= chinese_keys
    assert static_keys <= english_keys
    assert chinese_keys == english_keys


def test_platform_shell_routes_and_tools_are_data_driven() -> None:
    html = HTML.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    assert 'id="sidebar"' in html
    assert 'id="primary-nav"' in html
    assert 'data-route-view="home"' in html
    assert 'data-route-view="semantic-video"' in html
    assert 'data-route-view="tasks"' in html
    assert 'data-route-view="settings"' in html
    assert "const NAV_ITEMS = [" in script
    assert "const TOOL_CATALOG = [" in script
    assert "window.APP_TOOL_CATALOG = TOOL_CATALOG" in script
    assert "'#/home'" in script
    assert "'#/tools/semantic-video'" in script
    assert "'#/tasks'" in script
    assert "window.addEventListener('hashchange'" in script


def test_mobile_navigation_and_responsive_layout_rules_are_present() -> None:
    styles = STYLES.read_text(encoding="utf-8")
    html = HTML.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    assert 'id="menu-button"' in html
    assert 'aria-controls="sidebar"' in html
    assert "@media (max-width: 760px)" in styles
    assert "transform: translateX(-105%)" in styles
    assert "body.nav-open .sidebar" in styles
    assert "overflow-x: hidden" in styles
    assert ".upload-layout, .result-grid { grid-template-columns: 1fr; }" in styles
    assert "document.body.classList.toggle('nav-open'" in script
    assert "event.key === 'Escape'" in script


def test_video_preview_is_responsive_and_keeps_a_stable_source() -> None:
    styles = STYLES.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    assert ".preview-shell { display: flex;" in styles
    assert "max-width: 100%" in styles
    assert "max-height: min(68vh, 720px)" in styles
    assert "object-fit: contain" in styles
    assert "#preview { max-height: 64vh; }" in styles

    show_result = script.split("  function showResult(id, version) {", 1)[1].split("\n  }", 1)[0]
    assert "refs.preview.dataset.sourceKey !== sourceKey" in show_result
    assert "refs.preview.src =" in show_result
    assert "refs.preview.load()" not in show_result

    completed_handler = script.split("source.addEventListener('completed'", 1)[1].split("    });", 1)[0]
    assert "showResult(id" not in completed_handler
    assert "await loadTask(id" in completed_handler


def test_task_state_can_survive_refresh_and_browser_history() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert "semantic-video-current-task" in script
    assert "semantic-video-recent-tasks" in script
    assert "localStorage.setItem(STORAGE_KEYS.currentTask" in script
    assert "taskId: localStorage.getItem(STORAGE_KEYS.currentTask)" in script
    assert "loadTask(state.taskId)" in script
    assert "history.replaceState(null, '', '#/home')" in script


def test_completed_review_uses_accessible_tabs_and_keeps_all_existing_tools() -> None:
    html = HTML.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    for tab in ("transcript", "plan", "media", "activity"):
        assert f'data-tab="{tab}"' in html
        assert f'data-tab-panel="{tab}"' in html
    assert 'id="preview"' in html
    assert 'id="download"' in html
    assert 'id="search-media"' in html
    assert 'id="manual-media-url"' in html
    assert 'id="save-review"' in html
    assert "/media/search" in script
    assert "/media/candidates" in script
    assert "/review" in script
    assert "/cancel" in script
    assert "event.key === 'ArrowRight'" in script
