"""Free-mail domains list and detection helper.

Per algorithm.md §1:
FREE_MAIL_DOMAINS = gmail.com, googlemail.com, yahoo.com, yahoo.co.in,
outlook.com, hotmail.com, live.com, icloud.com, me.com, proton.me,
protonmail.com, rediffmail.com, aol.com, zoho.com (personal), gmx.com, yandex.com.
"""

FREE_MAIL_DOMAINS: frozenset[str] = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.co.in",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "icloud.com",
        "me.com",
        "proton.me",
        "protonmail.com",
        "rediffmail.com",
        "aol.com",
        "zoho.com",
        "gmx.com",
        "yandex.com",
        "mail.com",
        "fastmail.com",
    }
)


def is_freemail_domain(domain: str) -> bool:
    """Return True if domain is in the free-mail list (case-insensitive)."""
    norm = domain.strip().lower()
    if norm.startswith("www."):
        norm = norm[4:]
    return norm in FREE_MAIL_DOMAINS
