SELECTOR_VERSION = "fin-land-2026-07"

# DOM details are isolated here so a selector revision cannot weaken URL policy.
COMPLEX_LINK = "a[href^='/complexes/']"
TRADE_COUNT_BUTTON = "button[data-sentry-component='ButtonBoxLink']"
LISTING_CARD = (
    "li:has(button[data-nlogs-area='article*l.group']), "
    "li:has(a[data-nlogs-area='article*l.list'][href^='/articles/'])"
)
BROKER_OPEN_BUTTON = "button[data-nlogs-area='article*l.group']"
BROKER_ARTICLE_LINK = (
    "a[data-nlogs-area='article*l.group'][href^='/articles/']"
)
SINGLE_ARTICLE_LINK = (
    "a[data-nlogs-area='article*l.list'][href^='/articles/']"
)
BROKER_NPAY_DETAIL_TRIGGER = (
    "a[data-sentry-component='ButtonBoxLink'][href^='/articles/']"
)
BROKER_STANDARD_DETAIL_TRIGGER = (
    "a[data-nlogs-area='article*l.group'][href^='/articles/'], "
    "a[data-nlogs-area='article*l.list'][href^='/articles/']"
)
LISTING_SCROLL_CONTAINER = "div[class*='ScrollBox'][class*='panel']"
DETAIL_SLIDE_ROOT = (
    "div[data-sentry-component='SideLayer']:"
    "has(div[class*='DataList'][class*='term']:text-is('매물번호'))"
)
DETAIL_SLIDE_CLOSE_BUTTON = "button:has-text('창닫기')"
DETAIL_READY = "text=매물번호"

BLOCKED_TEXT_MARKERS = (
    "비정상적인 접근",
    "접근이 제한",
    "서비스 이용이 제한",
)
LOGIN_TEXT_MARKERS = ("로그인이 필요",)
CAPTCHA_TEXT_MARKERS = ("CAPTCHA", "자동입력 방지", "로봇이 아닙니다")
