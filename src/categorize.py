"""
Rule-based topic labels for markets. Polymarket's market records don't carry
topic tags, so we classify from the question and event title.

Rules are checked in order; the first match wins. Kept deliberately simple and
transparent so labels can be audited against a hand-labeled sample.
"""
import re

TOPICS = [
    ("sports", r"\b(nba|nfl|mlb|nhl|ufc|mma|fifa|uefa|premier league|champions league|la liga|serie a|bundesliga|"
               r"world cup|super bowl|stanley cup|world series|grand slam|wimbledon|us open|french open|australian open|"
               r"f1|formula 1|grand prix|ncaa|march madness|olympic|playoffs?|finals?|vs\.?|tournament|"
               r"heat|lakers|celtics|warriors|nuggets|knicks|chiefs|eagles|bills|cowboys|yankees|dodgers|"
               r"boxing|fight|match|seed|mvp|draft pick|win the (nba|nfl|mlb))\b"),
    ("crypto", r"\b(bitcoin|btc|ethereum|eth|solana|sol|xrp|doge|dogecoin|crypto|token|airdrop|memecoin|"
               r"binance|coinbase|stablecoin|usdt|usdc|etf approval|fdv|tvl|nft|blockchain|defi|"
               r"pump\.fun|farcaster|opensea|uniswap|arb|arbitrum|base chain|memecoins?)\b|\$[A-Z]{2,6}\b(?! market cap)"),
    ("economics", r"\b(fed|fomc|interest rates?|rate (cut|hike)|inflation|cpi|pce|gdp|recession|unemployment|"
                  r"jobs report|nonfarm|treasury|yields?|s&p|nasdaq|dow|stock|ipo|earnings|tariffs?|oil price|"
                  r"powell|ecb|bank of (england|japan)|debt ceiling|shutdown|market cap|svb|bank fail|acquired|bankrupt|bank of america)\b"),
    ("geopolitics", r"\b(ukraine|russia|putin|zelensky|israel|gaza|hamas|hezbollah|iran|china|taiwan|xi jinping|"
                    r"north korea|nato|ceasefire|invasion|war|missile|strike|sanctions|un security council|houthi)\b"),
    ("tech_ai", r"\b(openai|chatgpt|gpt-?\d|anthropic|claude|gemini|google deepmind|llm|\bai\b|artificial intelligence|"
                r"apple|iphone|tesla|spacex|starship|elon|musk|twitter|x\.com|meta|zuckerberg|nvidia|microsoft|"
                r"tiktok|ilya|altman|gpt)\b"),
    ("politics", r"\b(trump|biden|harris|kamala|desantis|haley|vance|walz|election|electoral|primary|nominee|"
                 r"nomination|senate|house|congress|governor|mayor|president|presidential|democrat|republican|gop|"
                 r"vote|poll|impeach|supreme court|scotus|cabinet|indicted|indictment|trial|prime minister|"
                 r"parliament|chancellor|macron|starmer|sunak|modi|milei|referendum)\b"),
    ("culture", r"\b(oscar|oscars|academy award|grammy|emmy|golden globe|box office|movie|film|album|song|spotify|"
                r"billboard|taylor swift|kanye|drake|celebrity|youtube|mrbeast|tv show|netflix|time person of the year|"
                r"eurovision|best picture|nobel|mrbeast|onlyfans|opening weekend)\b"),
    ("science_weather", r"\b(hurricane|storm|earthquake|temperature|weather|heat ?wave|snow|rain|climate|nasa|"
                        r"covid|pandemic|bird flu|h5n1|measles|asteroid|eclipse)\b"),
]
_COMPILED = [(name, re.compile(pattern, re.I)) for name, pattern in TOPICS]


def topic_of(question: str | None, event_title: str | None = None) -> str:
    text = " ".join(t for t in (question, event_title) if t)
    for name, rx in _COMPILED:
        if rx.search(text):
            return name
    return "other"
