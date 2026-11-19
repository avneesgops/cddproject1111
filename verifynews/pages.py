"""Streamlit pages for the VerifyNews app."""
import html
import json
import re
import textwrap
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

try:
    from newspaper import Article
except Exception:
    Article = None

from .casebook_ui import (
    clear_article_url,
    clear_last_analysis,
    render_casebook,
    show_result,
)
from .components import render_claim_check
from .config import BRAND_MARK_DATA_URI, BRAND_MARK_PATH, BRAND_MARK_SVG, MIN_ARTICLE_CHARS
from .news import load_current_news
from .storage import list_verification_cases
from .verification import (
    WIKIPEDIA_LANGUAGES,
    extract_claims,
    load_claim_model,
    load_xlmr_verifier,
)

def render_main_page():
    st.markdown(textwrap.dedent("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
    :root { color-scheme: light; }
    .stApp { background:#f4f1e9; color:#171915; font-family:'Manrope',sans-serif; }
    .stApp, .stApp * { cursor:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='28' height='34' viewBox='0 0 28 34'%3E%3Cpath d='M3 2.5v25.7l6.1-6.2 4.8 9.2 4-2.1-4.8-9h10.1L3 2.5Z' fill='%23e5654b' stroke='%23171915' stroke-width='1.5' stroke-linejoin='round'/%3E%3Cpath d='m3.7 4.4 15.2 14.5h-6.9' fill='none' stroke='%23fffaf2' stroke-width='1.15' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") 2 2, auto !important; }
    .stApp input, .stApp textarea, .stApp [contenteditable="true"] { cursor:text !important; }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stAppViewContainer"] > .main { background: transparent; }
    .block-container { max-width:1460px; padding:1rem 2.25rem 4rem; }
    [data-testid="stVerticalBlock"] { gap: 1rem; }
    .vn-nav { min-height:64px; display:flex; justify-content:space-between; align-items:center; gap:18px; padding:0 4px; border-bottom:1px solid #d7d3c9; margin-bottom:1.3rem; }
    .vn-brand { display:flex; align-items:center; gap:11px; color:#171915; text-decoration:none; }
    .vn-brand-mark { display:block; width:40px; height:40px; flex:0 0 auto; }
    .vn-brand-copy { display:grid; gap:3px; }
    .vn-brand-main { font-size:.83rem; letter-spacing:.13em; font-weight:800; }
    .vn-brand-slash { color:#e5654b; padding:0 4px; }
    .vn-brand-sub { color:#77766e; font:500 .49rem 'DM Mono',monospace; letter-spacing:.1em; }
    .vn-nav-right,.vn-eyebrow { color:#65655e; font:500 .69rem 'DM Mono',monospace; letter-spacing:.1em; text-transform:uppercase; }
    .vn-nav-right i { display:inline-block; width:8px;height:8px;border-radius:50%;background:#e5654b;margin-right:9px; }
    .vn-hero { display:grid; grid-template-columns:1.05fr .95fr; gap:42px; align-items:center; min-height:480px; border-bottom:1px solid #d7d3c9; padding-bottom:34px; }
    .vn-copy { padding:clamp(20px,3vw,48px) 0 32px; }
    .vn-eyebrow { color:#e5654b; }
    .vn-title { font-size:clamp(3.5rem,7.6vw,7.3rem); line-height:.88; letter-spacing:-.085em; font-weight:600; margin:24px 0 25px; max-width:790px; }
    .vn-title em { font-style:normal; color:#e5654b; }
    .vn-deck { max-width:610px; color:#53534e; font-size:clamp(1rem,1.4vw,1.2rem); line-height:1.65; }
    .vn-note { color:#66665f; font-size:.84rem; border-left:2px solid #e5654b; padding-left:13px; margin-top:24px; }
    .vn-visual { min-height:400px; max-width:590px; width:100%; margin:auto; position:relative; display:flex; align-items:center; padding:clamp(22px,4vw,52px); background:#e9e5db; border:1px solid #ded9cf; }
    .vn-paper { width:100%; padding:clamp(22px,3.5vw,40px); background:#fbf9f4; border:1px solid #d7d3c9; box-shadow:12px 12px 0 #d9d4c8; }
    .vn-paper-head { display:flex; justify-content:space-between; gap:14px; padding-bottom:16px; border-bottom:1px solid #d7d3c9; color:#77766e; font:500 .58rem 'DM Mono',monospace; letter-spacing:.1em; }
    .vn-paper-head span:last-child { color:#e5654b; text-align:right; }
    .vn-paper-kicker { margin:25px 0 10px; color:#e5654b; font:500 .63rem 'DM Mono',monospace; letter-spacing:.12em; }
    .vn-excerpt { max-width:450px; margin:0; font-size:clamp(1.5rem,3vw,2.25rem); line-height:1.25; letter-spacing:-.055em; }
    .vn-excerpt mark { background:linear-gradient(transparent 58%,#f0b6a8 58%); color:inherit; }
    .vn-sample-lines { display:grid; gap:8px; margin:22px 0 28px; }
    .vn-sample-lines i { display:block; width:100%; height:5px; background:#e4e0d7; }
    .vn-sample-lines i:nth-child(2) { width:82%; }.vn-sample-lines i:nth-child(3) { width:91%; }.vn-sample-lines i:nth-child(4) { width:58%; }
    .vn-readout { display:flex; align-items:center; gap:14px; border-top:1px solid #d7d3c9; padding-top:16px; }
    .vn-readout-index { color:#e5654b; font:500 .68rem 'DM Mono',monospace; }
    .vn-readout-copy { display:grid; gap:3px; }
    .vn-readout-copy strong { font-size:.88rem; font-weight:700; }
    .vn-readout-copy small { color:#77766e; font-size:.74rem; }
    .vn-readout-mark { margin-left:auto; color:#e5654b; font-size:1.15rem; }
    .vn-actions { display:flex; align-items:center; gap:20px; margin-top:26px; flex-wrap:wrap; }
    .vn-primary { display:inline-flex; align-items:center; gap:22px; padding:13px 18px; border-radius:999px; background:#171915; color:#fbf9f4!important; text-decoration:none!important; font-size:.85rem; font-weight:700; transition:transform .18s ease,background .18s ease; }
    .vn-primary:hover { transform:translateY(-2px); background:#e5654b; }
    .vn-secondary { color:#34352f!important; text-decoration:none!important; font-size:.85rem; border-bottom:1px solid #aaa69c; padding:0 0 4px; }
    .vn-meta { display:grid; grid-template-columns:repeat(3,1fr); border-bottom:1px solid #d7d3c9; padding:20px 0; gap:20px; }
    .vn-meta-item { display:grid; gap:7px; }
    .vn-meta-item span { color:#77766e; font:500 .58rem 'DM Mono',monospace; letter-spacing:.13em; }
    .vn-meta-item strong { color:#171915; font-size:.84rem; font-weight:600; }
    .vn-ribbon { padding:14px 0; border-bottom:1px solid #d7d3c9; color:#55564f; text-align:center; font:500 .62rem 'DM Mono',monospace; letter-spacing:.1em; text-transform:uppercase; }
    .vn-ribbon span { color:#e5654b; padding:0 12px; }
    .vn-section { margin:2.4rem 0 1rem; }
    .vn-news-grid { display:grid; grid-template-columns:repeat(12,minmax(0,1fr)); gap:12px; margin:14px 0 34px; }
    .vn-news-card { min-width:0; min-height:218px; display:flex; flex-direction:column; justify-content:space-between; gap:20px; padding:22px; background:#fbf9f4; border:1px solid #d7d3c9; box-shadow:4px 4px 0 #e3dfd5; transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease; }
    .vn-news-card:hover { transform:translateY(-3px); border-color:#e5654b; box-shadow:6px 7px 0 #e3dfd5; }
    .vn-news-card:focus-within { outline:2px solid #e5654b; outline-offset:3px; }
    .vn-news-card--lead { grid-column:span 7; min-height:302px; padding:28px; background:#e9e5db; }
    .vn-news-card--side { grid-column:span 5; min-height:145px; }
    .vn-news-card--standard { grid-column:span 4; }
    .vn-news-meta { display:flex; flex-wrap:wrap; align-items:center; gap:8px 12px; color:#77766e; font:500 .61rem 'DM Mono',monospace; letter-spacing:.07em; text-transform:uppercase; }
    .vn-news-index { color:#e5654b; font-weight:700; }
    .vn-news-source { max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .vn-news-time { margin-left:auto; font-variant-numeric:tabular-nums; }
    .vn-news-title { margin:22px 0 12px; color:#171915; font-size:1.25rem; line-height:1.3; letter-spacing:-.035em; text-wrap:balance; overflow-wrap:anywhere; }
    .vn-news-card--lead .vn-news-title { max-width:720px; font-size:clamp(1.6rem,3.2vw,2.4rem); line-height:1.15; }
    .vn-news-title a,.vn-news-title a:visited { color:inherit!important; text-decoration:none; text-underline-offset:4px; }
    .vn-news-title a:hover { color:#b7432f!important; text-decoration:underline; }
    .vn-news-title a:focus-visible { outline:2px solid #e5654b; outline-offset:4px; }
    .vn-news-description { display:-webkit-box; margin:0; overflow:hidden; color:#65655e; font-size:.83rem; line-height:1.65; -webkit-box-orient:vertical; -webkit-line-clamp:3; }
    .vn-news-card--lead .vn-news-description { max-width:700px; -webkit-line-clamp:4; }
    .vn-news-link,.vn-news-link:visited { display:inline-flex; align-items:center; gap:8px; width:max-content; margin-top:auto; color:#b7432f!important; font:600 .62rem 'DM Mono',monospace; letter-spacing:.08em; text-decoration:none; text-transform:uppercase; }
    .vn-news-link:hover { color:#171915!important; text-decoration:underline; text-underline-offset:4px; }
    .vn-news-link:focus-visible { outline:2px solid #e5654b; outline-offset:4px; }
    .vn-news-updated { margin:0 0 10px; color:#77766e; font:500 .62rem 'DM Mono',monospace; letter-spacing:.06em; }
    @media(max-width:900px) { .vn-news-card--lead { grid-column:span 7; }.vn-news-card--side { grid-column:span 5; }.vn-news-card--standard { grid-column:span 6; } }
    @media(max-width:600px) { .vn-news-grid { grid-template-columns:1fr; gap:10px; }.vn-news-card,.vn-news-card--lead,.vn-news-card--side,.vn-news-card--standard { grid-column:1; min-height:0; padding:19px; }.vn-news-card--lead { min-height:235px; }.vn-news-title { margin-top:17px; font-size:1.15rem; }.vn-news-card--lead .vn-news-title { font-size:1.65rem; } }
    @media(prefers-reduced-motion:reduce) { .vn-news-card { transition:none; } }
    .stMarkdown h2,.stMarkdown h3 { color:#171915; letter-spacing:-.045em; }
    [data-testid="stMetric"] { border:1px solid #d7d3c9; border-radius:3px; background:#ebe7dd; padding:16px 18px; }
    [data-testid="stMetricLabel"] p { color:#65655e; }
    [data-testid="stMetricValue"] { color:#e5654b; }
    [data-testid="stTabs"] [role="tablist"] { gap:8px; border-bottom:1px solid #d7d3c9; }
    [data-testid="stTabs"] [role="tab"] { color:#55564f!important; opacity:1!important; border-radius:0; }
    [data-testid="stTabs"] [role="tab"] * { color:inherit!important; opacity:1!important; }
    [data-testid="stTabs"] [role="tab"]:hover { color:#171915!important; background:#ebe7dd; }
    [data-testid="stTabs"] [role="tab"]:focus-visible { outline:2px solid #e5654b; outline-offset:3px; }
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] { color:#171915!important; border-bottom-color:#e5654b; }
    [data-testid="stTextArea"] [data-testid="stWidgetLabel"],[data-testid="stTextArea"] [data-testid="stWidgetLabel"] * { color:#171915!important; }
    .stTextInput input,.stTextArea textarea,[data-testid="stTextArea"] textarea,[data-baseweb="textarea"] textarea { background:#fbf9f4!important; border:1px solid #cbc6ba; border-radius:4px; color:#171915!important; -webkit-text-fill-color:#171915!important; caret-color:#171915; }
    .stTextArea textarea::placeholder,[data-testid="stTextArea"] textarea::placeholder,[data-baseweb="textarea"] textarea::placeholder { color:#65655e!important; opacity:1!important; -webkit-text-fill-color:#65655e!important; }
    .stButton button { border-radius:999px; background:#e5654b; color:#fffaf2; border:0; font-weight:700; padding:.58rem 1.3rem; transition:transform .18s ease,filter .18s ease; }
    .stButton button:hover { transform:translateY(-2px); filter:brightness(1.05); color:#fffaf2; border:0; }
    .st-key-url_clear_control button { background:transparent!important; color:#171915!important; border:1px solid #cbc6ba!important; }
    .st-key-url_clear_control button:hover { background:#ebe7dd!important; color:#171915!important; border-color:#aaa69c!important; }
    [data-testid="stExpander"], [data-testid="stDataFrame"] { border-color:#d7d3c9; }
    [data-testid="stAlert"] { border-radius:14px; }
    [data-testid="stSpinner"] { position:fixed!important; inset:0!important; z-index:99999!important; width:100vw!important; height:100vh!important; margin:0!important; padding:30px!important; transform:none!important; border:0!important; background:#f4f1e9!important; box-shadow:none!important; display:flex!important; flex-direction:column!important; align-items:center!important; justify-content:center!important; text-align:center; }
    [data-testid="stSpinner"]::before { content:"VERIFY / NEWS"; display:block; min-height:38px; padding-left:48px; background-image:url("__VN_MARK_DATA_URI__"); background-repeat:no-repeat; background-position:left center; background-size:38px; color:#e5654b; font:800 .72rem 'DM Mono',monospace; letter-spacing:.15em; line-height:38px; margin-bottom:30px; }
    [data-testid="stSpinner"] svg { display:none!important; }
    [data-testid="stSpinner"] p { width:100%; color:transparent!important; font-size:0!important; margin:0!important; display:flex!important; flex-direction:column!important; align-items:center!important; justify-content:center!important; text-align:center!important; }
    [data-testid="stSpinner"] p::before { content:"READ BETWEEN THE WORDS"; display:block; width:100%; color:#171915; font:800 clamp(1.55rem,5vw,3.4rem)/.96 'Manrope',sans-serif; letter-spacing:-.07em; text-align:center; }
    [data-testid="stSpinner"] p::after { content:"LEARNING WORD PATTERNS"; display:block; width:100%; margin-top:18px; color:#77766e; font:500 .64rem 'DM Mono',monospace; letter-spacing:.13em; text-align:center; animation:vn-loader-copy 4.8s steps(1,end) infinite; }
    [data-testid="stSpinner"]::after { content:""; display:block; width:min(280px,65vw); height:3px; margin-top:28px; transform-origin:left; background:linear-gradient(90deg,#e5654b 0 28%,#f0b6a8 28% 42%,#e5654b 42% 50%,transparent 50%); background-size:240% 100%; animation:vn-loading 1.8s linear infinite; }
    @keyframes vn-loader-copy { 0%,32% { content:"LOADING CLAIM DATA"; } 33%,65% { content:"MATCHING EVIDENCE SOURCES"; } 66%,100% { content:"PREPARING THE VERIFIER"; } }
    @keyframes vn-loading { from { background-position:100% 0; } to { background-position:-100% 0; } }
    @media(max-width:800px) { .block-container{padding:1rem 1rem 3rem}.vn-hero{grid-template-columns:1fr;gap:10px}.vn-copy{padding:24px 0 5px}.vn-title{font-size:clamp(3.4rem,13vw,6rem)}.vn-visual{min-height:0;width:100%;max-width:590px;padding:clamp(18px,5vw,32px)}.vn-nav-right{font-size:.56rem} }
    @media(max-width:480px) { .vn-nav-right{max-width:145px;line-height:1.5}.vn-title{font-size:clamp(3rem,13vw,4.7rem)}.vn-paper{padding:22px 18px;box-shadow:8px 8px 0 #d9d4c8}.vn-paper-head{font-size:.5rem}.vn-excerpt{font-size:1.55rem}.vn-meta{grid-template-columns:1fr;gap:14px}.vn-meta-item{grid-template-columns:80px 1fr;align-items:center}.vn-actions{gap:15px} }
    @media(max-width:480px) { .vn-nav-right{max-width:145px;line-height:1.5}.vn-title{font-size:clamp(3rem,13vw,4.7rem)}.vn-paper{padding:22px 18px;box-shadow:8px 8px 0 #d9d4c8}.vn-paper-head{font-size:.5rem}.vn-excerpt{font-size:1.55rem} }
    @media(prefers-reduced-motion:reduce) { *,*::before,*::after{scroll-behavior:auto!important;transition:none!important;animation:none!important} }
    </style>
    <header class="vn-nav"><div class="vn-brand">__VN_MARK__<span class="vn-brand-copy"><span class="vn-brand-main">VERIFY<span class="vn-brand-slash">/</span>NEWS</span><span class="vn-brand-sub">CLAIMS · EVIDENCE · CONTEXT</span></span></div><div class="vn-nav-right"><i></i> Claim evidence · research preview</div></header>
    <section class="vn-hero">
      <div class="vn-copy"><div class="vn-eyebrow">Claims first · free source lookup</div>
        <h1 class="vn-title">NEWS,<br>READ BETWEEN<br><em>THE LINES.</em></h1>
        <p class="vn-deck">Paste an article or analyze a link to extract factual claims, search 34,000+ claim-and-evidence records, and retrieve fuller Wikipedia passages. The verifier shows a rating estimate only when it has evidence to inspect.</p>
        <p class="vn-note">One source provider is not enough for a verdict. The app shows context and abstains until it can compare independent sources.</p>
        <div class="vn-actions"><a class="vn-primary" href="#analyze-an-article">Analyze an article <span>↗</span></a><a class="vn-secondary" href="#model-evaluation">How the model reads ↓</a></div>
      </div>
      <div class="vn-visual" aria-label="Illustrative editorial card showing a phrase highlighted for language analysis">
        <div class="vn-paper">
          <div class="vn-paper-head"><span>VERIFY / NEWS — FIELD NOTE 01</span><span>ILLUSTRATIVE SAMPLE</span></div>
          <p class="vn-paper-kicker">CLAIM + EVIDENCE</p>
          <p class="vn-excerpt">A claim needs sources and <mark>context</mark> worth examining.</p>
          <div class="vn-sample-lines" aria-hidden="true"><i></i><i></i><i></i><i></i></div>
          <div class="vn-readout"><span class="vn-readout-index">01</span><span class="vn-readout-copy"><strong>Free source lookup</strong><small>Related Wikipedia context, not an automatic verdict.</small></span><span class="vn-readout-mark" aria-hidden="true">↗</span></div>
        </div>
      </div>
    </section>
    <div class="vn-meta" aria-label="How VerifyNews works">
      <div class="vn-meta-item"><span>INPUT</span><strong>Article URL or text</strong></div>
      <div class="vn-meta-item"><span>CLAIM + EVIDENCE</span><strong>34,000+ · X-FACT + AVeriTeC</strong></div>
      <div class="vn-meta-item"><span>LIVE CONTEXT</span><strong>Dated Wikipedia extracts · free API</strong></div>
    </div>
    <div class="vn-ribbon" aria-label="How to use claim lookup">Click Analyze an article to search candidate claims <span>✳</span> No API key required</div>
    """).replace("__VN_MARK__", BRAND_MARK_SVG).replace("__VN_MARK_DATA_URI__", BRAND_MARK_DATA_URI), unsafe_allow_html=True)

    st.markdown('<div class="vn-section"></div>', unsafe_allow_html=True)
    news_heading, news_refresh = st.columns([4, 1], vertical_alignment="bottom")
    with news_heading:
        st.subheader("Current headlines")
        st.caption("Recent stories · headlines are not fact checks")
    with news_refresh:
        if st.button("Refresh headlines", key="refresh_current_news", use_container_width=True):
            load_current_news.clear()
    try:
        current_news = load_current_news()
        if current_news["articles"]:
            provider = html.escape(str(current_news.get("provider", "News feed")))
            feed_timestamp = pd.to_datetime(current_news.get("updated_at", ""), utc=True, errors="coerce")
            fetched_at = feed_timestamp.strftime("%d %b · %H:%M UTC") if not pd.isna(feed_timestamp) else ""
            updated_label = f" &nbsp;·&nbsp; Updated {html.escape(fetched_at)}" if fetched_at else ""
            st.markdown(f'<p class="vn-news-updated">{provider}{updated_label}</p>', unsafe_allow_html=True)
            news_cards = []
            for index, article in enumerate(current_news["articles"]):
                title = html.escape(str(article.get("title", "")))
                source_name = html.escape(str((article.get("source") or {}).get("name") or "News source"))
                description = html.escape(str(article.get("description") or ""))
                raw_url = str(article.get("url") or "")
                parsed_url = urlparse(raw_url)
                if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
                    continue
                safe_url = html.escape(raw_url, quote=True)
                raw_date = article.get("publishedAt", "")
                timestamp = pd.to_datetime(raw_date, utc=True, errors="coerce")
                published = timestamp.strftime("%d %b · %H:%M UTC") if not pd.isna(timestamp) else "Date unavailable"
                card_class = "vn-news-card--lead" if index == 0 else ("vn-news-card--side" if index == 1 else "vn-news-card--standard")
                has_useful_summary = not str(current_news.get("provider", "")).startswith("Google News RSS")
                description_markup = f'<p class="vn-news-description">{description}</p>' if description and has_useful_summary else ""
                news_cards.append(
                    f'<article class="vn-news-card {card_class}">'
                    f'<div><div class="vn-news-meta"><span class="vn-news-index">{index + 1:02}</span>'
                    f'<span class="vn-news-source">{source_name}</span><time class="vn-news-time">{published}</time></div>'
                    f'<h3 class="vn-news-title"><a href="{safe_url}" target="_blank" rel="noopener noreferrer">{title}</a></h3>'
                    f'{description_markup}</div>'
                    f'<a class="vn-news-link" href="{safe_url}" target="_blank" rel="noopener noreferrer">Read story <span aria-hidden="true">↗</span></a>'
                    '</article>'
                )
            if news_cards:
                st.markdown('<section class="vn-news-grid" aria-label="Current news stories">' + "".join(news_cards) + '</section>', unsafe_allow_html=True)
            else:
                st.info("No headlines with usable source links were returned.")
        elif current_news["configured"]:
            st.info("The current news feed is configured, but no headlines are available right now.")
        else:
            st.info("No current headlines were returned. Refresh the feed or try again later.")
    except Exception as error:
        st.warning(f"Could not load current headlines ({type(error).__name__}). Article analysis remains available.")

    # Each Streamlit browser session gets one short intro, even when the shared model
    # is already cached. Returning interactions in the same tab do not replay it.
    if not st.session_state.get("entry_splash_seen", False):
        st.session_state.entry_splash_seen = True
        st.html("""
    <style>
    #verifynews-intro { position:fixed; inset:0; z-index:100001; width:100vw; height:100vh; height:100dvh; display:grid; place-items:center; overflow:hidden; background:#f4f1e9; color:#171915; opacity:1; transition:opacity .42s ease, visibility .42s ease; }
    #verifynews-intro.is-leaving { opacity:0; visibility:hidden; }
    #verifynews-intro .vn-splash-wrap { width:min(760px,calc(100% - 44px)); text-align:center; }
    #verifynews-intro .vn-splash-brand { display:flex; align-items:center; justify-content:center; gap:14px; margin-bottom:44px; color:#171915; text-align:left; }
    #verifynews-intro .vn-splash-brand .vn-brand-mark { width:48px; height:48px; }
    #verifynews-intro .vn-splash-copy { display:grid; gap:4px; }
    #verifynews-intro .vn-splash-name { color:#171915; font:800 .74rem 'DM Mono',monospace; letter-spacing:.15em; }
    #verifynews-intro .vn-splash-name i { color:#e5654b; font-style:normal; padding:0 3px; }
    #verifynews-intro .vn-splash-tag { color:#77766e; font:500 .49rem 'DM Mono',monospace; letter-spacing:.09em; }
    #verifynews-intro .vn-splash-kicker { margin:0 0 20px; color:#77766e; font:500 .64rem 'DM Mono',monospace; letter-spacing:.14em; text-transform:uppercase; }
    #verifynews-intro h2 { margin:0; color:#171915; font:800 clamp(3.3rem,10vw,7.2rem)/.84 'Manrope',sans-serif; letter-spacing:-.09em; }
    #verifynews-intro h2 em { color:#e5654b; font-style:normal; }
    #verifynews-intro .vn-splash-state { min-height:1.3em; margin:27px 0 20px; color:#55564f; font:500 .72rem 'DM Mono',monospace; letter-spacing:.1em; text-transform:uppercase; transition:opacity .18s ease; }
    #verifynews-intro .vn-splash-steps { display:flex; align-items:center; justify-content:center; gap:15px; color:#77766e; font:500 .59rem 'DM Mono',monospace; letter-spacing:.1em; }
    #verifynews-intro .vn-splash-steps b { color:#e5654b; animation:vn-spark 1.1s ease-in-out infinite alternate; }
    #verifynews-intro .vn-splash-track { width:min(280px,70vw); height:3px; background:#ded9cf; margin:24px auto 0; overflow:hidden; }
    #verifynews-intro .vn-splash-track span { display:block; height:100%; width:38%; background:#e5654b; animation:vn-sweep .95s ease-in-out infinite alternate; }
    #verifynews-intro .vn-splash-foot { margin:24px 0 0; color:#77766e; font:500 .57rem 'DM Mono',monospace; letter-spacing:.1em; }
    #verifynews-intro .vn-splash-skip { position:absolute; top:24px; right:28px; border:0; padding:9px 12px; background:transparent; color:#55564f; font:500 .7rem 'DM Mono',monospace; cursor:pointer; text-decoration:underline; text-underline-offset:4px; }
    #verifynews-intro .vn-splash-skip:focus-visible { outline:2px solid #e5654b; outline-offset:4px; }
    @keyframes vn-sweep { from { transform:translateX(-30%); } to { transform:translateX(190%); } }
    @keyframes vn-spark { from { opacity:.35; transform:scale(.85) rotate(-18deg); } to { opacity:1; transform:scale(1.12) rotate(18deg); } }
    @media(prefers-reduced-motion:reduce) { #verifynews-intro, #verifynews-intro * { animation:none!important; transition:none!important; } }
    </style>
    <section id="verifynews-intro" role="status" aria-live="polite" aria-label="Preparing VerifyNews">
      <button class="vn-splash-skip" type="button" aria-label="Skip intro animation">Skip intro ↗</button>
      <div class="vn-splash-wrap">
        <div class="vn-splash-brand">__VN_MARK__<span class="vn-splash-copy"><span class="vn-splash-name">VERIFY <i>/</i> NEWS</span><span class="vn-splash-tag">CLAIMS · EVIDENCE · CONTEXT</span></span></div>
        <p class="vn-splash-kicker">Fresh tab. Fresh read.</p>
        <h2>HOLD THAT<br><em>HEADLINE.</em></h2>
        <p class="vn-splash-state" data-state>Scanning the words…</p>
        <div class="vn-splash-steps" aria-hidden="true"><span>WORDS</span><b>✳</b><span>PATTERNS</span><b>✳</b><span>CONTEXT</span></div>
        <div class="vn-splash-track" aria-hidden="true"><span></span></div>
      <p class="vn-splash-foot">A MODEL ESTIMATE IS NOT A VERDICT.</p>
      </div>
    </section>
    <script>
    (() => {
      const splash = document.getElementById("verifynews-intro");
      if (!splash) return;
      const state = splash.querySelector("[data-state]");
      const skip = splash.querySelector(".vn-splash-skip");
      const messages = ["Loading claim data…", "Matching evidence sources…", "Keeping context in view…"];
      let index = 0;
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const rotate = reducedMotion ? null : window.setInterval(() => {
        index = (index + 1) % messages.length;
        state.textContent = messages[index];
      }, 620);
      let removed = false;
      const dismiss = () => {
        if (removed) return;
        removed = true;
        if (rotate) window.clearInterval(rotate);
        splash.classList.add("is-leaving");
        window.setTimeout(() => splash.remove(), reducedMotion ? 0 : 440);
      };
      skip.addEventListener("click", dismiss, { once: true });
      window.setTimeout(dismiss, reducedMotion ? 1100 : 2300);
    })();
    </script>
    """.replace("__VN_MARK__", BRAND_MARK_SVG), unsafe_allow_javascript=True)

    claim_vectorizer = claim_model = claim_evaluation = None
    xlmr_verifier = None
    try:
        claim_vectorizer, claim_model, claim_evaluation = load_claim_model()
        xlmr_verifier = load_xlmr_verifier()
    except Exception as error:
        st.error(f"Could not load the claim-and-evidence models: {error}")
    st.session_state.claim_vectorizer = claim_vectorizer
    st.session_state.claim_model = claim_model
    st.session_state.claim_evaluation = claim_evaluation
    st.session_state.xlmr_verifier = xlmr_verifier

    st.markdown('<div class="vn-section"></div>', unsafe_allow_html=True)
    if claim_evaluation:
        st.subheader("Claim-and-evidence model results")
        training_sources = " + ".join(f"{count:,} {name}" for name, count in claim_evaluation["train_sources"].items())
        st.caption(f"LinearSVC research baseline · {claim_evaluation['train_rows']:,} claim/evidence pairs · {claim_evaluation['train_languages']} languages · Sources: {training_sources}")
        st.caption("Ratings: Supported, Refuted, Mixed, and Not enough evidence. Metrics are research results, not guarantees for current news.")
        split_labels = {"in_domain": "In-domain X-FACT", "out_of_domain": "New fact-check sites", "zero_shot": "Zero-shot languages"}
        score_columns = st.columns(3)
        for column, (split, label) in zip(score_columns, split_labels.items()):
            scores = claim_evaluation["splits"][split]
            column.metric(f"LinearSVC · {label} macro-F1", f"{scores['macro_f1']:.1%}", help=f"{scores['rows']:,} held-out claims · {scores['languages']} languages")
        if xlmr_verifier:
            report_path = Path("models/xlmr_claim_verifier/evaluation.json")
            if report_path.exists():
                try:
                    xlmr_report = json.loads(report_path.read_text(encoding="utf-8"))
                    xlmr_columns = st.columns(3)
                    xlmr_splits = (("x_fact_in_domain", "In-domain X-FACT"), ("x_fact_new_sites", "New fact-check sites"), ("x_fact_zero_shot_languages", "Zero-shot languages"))
                    for column, (key, label) in zip(xlmr_columns, xlmr_splits):
                        score = xlmr_report.get("splits", {}).get(key, {}).get("macro_f1")
                        if score is not None:
                            column.metric(f"XLM-R · {label} macro-F1", f"{score:.1%}")
                except Exception as error:
                    st.caption(f"XLM-R is installed for predictions; its saved evaluation report could not be read ({type(error).__name__}).")
            else:
                st.caption("Fine-tuned XLM-R is installed for predictions. No saved evaluation report was found.")
        else:
            st.caption("Fine-tuned XLM-R is not installed; the LinearSVC baseline is the available claim/evidence model.")
        with st.expander("LinearSVC evaluation details"):
            for split, label in split_labels.items():
                scores = claim_evaluation["splits"][split]
                st.write(f"**{label}:** {scores['accuracy']:.1%} accuracy · {scores['macro_f1']:.1%} macro-F1 · {scores['rows']:,} claims · {scores['languages']} languages")
            validation = claim_evaluation["splits"]["validation"]
            st.write(f"**Mixed validation (X-FACT dev + AVeriTeC dev):** {validation['accuracy']:.1%} accuracy · {validation['macro_f1']:.1%} macro-F1 · {validation['rows']:,} claims")
            averitec = claim_evaluation["splits"]["averitec_dev"]
            st.write(f"**AVeriTeC dev transfer check:** {averitec['accuracy']:.1%} accuracy · {averitec['macro_f1']:.1%} macro-F1 · {averitec['rows']:,} claims · English")
            st.caption("The claim model returns estimates only when it has readable evidence. Wikipedia is one provider, so the site does not present its results as independent corroboration or a final verdict.")
    else:
        st.info("The prepared multilingual claim/evidence data are unavailable. Add datasets/verification/*.csv to enable model evaluation and estimates.")

    if message := st.session_state.pop("case_created_flash", None):
        st.success(message)
        st.page_link(casebook_page, label="Open casebook", icon="📂")
    st.subheader("Check article claims")
    tab_url, tab_text, tab_compare = st.tabs(["Analyze a link", "Paste article text", "Compare articles"])
    with tab_url:
        if Article is None:
            st.info("URL extraction unavailable. Install newspaper3k to enable it; pasted text works without it.")
        url_evidence_language = st.selectbox("Evidence search language", list(WIKIPEDIA_LANGUAGES), key="url_evidence_language", help="Choose the Wikipedia edition closest to the article's language.", on_change=clear_last_analysis)
        st.markdown('<div id="analyze-an-article"></div>', unsafe_allow_html=True)
        url = st.text_input("Article URL", placeholder="https://example.com/news-article", key="article_url_input", on_change=clear_last_analysis)
        analyze_col, clear_col = st.columns([3.8, 1.2], vertical_alignment="center")
        with analyze_col:
            analyze_link = st.button("Analyze link", disabled=not url.strip(), key="analyze_url", use_container_width=True)
        with clear_col:
            with st.container(key="url_clear_control"):
                st.button("Clear URL", key="clear_article_url_button", on_click=clear_article_url, use_container_width=True, help="Clear the current URL")
        if analyze_link:
            if Article is None:
                st.warning("URL extraction is unavailable because newspaper3k is not installed. Install the project requirements or paste the article text instead.")
            else:
                parsed = urlparse(url.strip())
                if parsed.scheme not in ("http", "https") or not parsed.netloc:
                    st.warning("Enter a complete http:// or https:// URL.")
                else:
                    try:
                        with st.spinner("Downloading and parsing article…"):
                            article = Article(url.strip(), request_timeout=15)
                            article.download()
                            article.parse()
                        if len((article.text or "").strip()) < MIN_ARTICLE_CHARS:
                            st.warning("The page did not provide enough readable article text. Try pasting the article manually.")
                        else:
                            st.session_state["analysis_payload"] = {
                                "text": article.text, "input_type": "URL", "title": article.title or "",
                                "publisher": parsed.netloc, "published_at": article.publish_date.isoformat() if article.publish_date else "",
                                "article_url": url.strip(), "evidence_language": WIKIPEDIA_LANGUAGES[url_evidence_language],
                            }
                    except Exception as error:
                        st.warning(f"Could not read this page ({type(error).__name__}). Try another article or paste its text.")
        saved_analysis = st.session_state.get("analysis_payload")
        if saved_analysis and saved_analysis["input_type"] == "URL":
            show_result(
                saved_analysis["text"], "URL", saved_analysis["title"], saved_analysis["publisher"],
                pd.to_datetime(saved_analysis["published_at"], errors="coerce") if saved_analysis["published_at"] else None,
                saved_analysis["evidence_language"], saved_analysis["article_url"],
            )
    with tab_text:
        text_evidence_language = st.selectbox("Evidence search language", list(WIKIPEDIA_LANGUAGES), key="text_evidence_language", help="Choose the Wikipedia edition closest to the article's language.", on_change=clear_last_analysis)
        text = st.text_area("Paste article text", height=220, placeholder="Paste the complete article body…", key="pasted_article_text", on_change=clear_last_analysis)
        if st.button("Analyze text", key="analyze_text"):
            st.session_state["analysis_payload"] = {
                "text": text, "input_type": "Text", "title": "", "publisher": "",
                "published_at": "", "article_url": "",
                "evidence_language": WIKIPEDIA_LANGUAGES[text_evidence_language],
            }
        saved_analysis = st.session_state.get("analysis_payload")
        if saved_analysis and saved_analysis["input_type"] == "Text":
            show_result(saved_analysis["text"], "Text", evidence_language=saved_analysis["evidence_language"])
    with tab_compare:
        st.caption("Enter up to three article URLs, one per line. A candidate claim from each is searched against free Wikipedia sources.")
        compare_evidence_language = st.selectbox("Evidence search language", list(WIKIPEDIA_LANGUAGES), key="compare_evidence_language", help="Choose the Wikipedia edition closest to the article's language.")
        urls = st.text_area("Article URLs", height=100, placeholder="https://source-one.example/article\nhttps://source-two.example/article")
        if st.button("Compare articles", disabled=(Article is None or not urls.strip())):
            rows = []
            for candidate in [line.strip() for line in urls.splitlines() if line.strip()][:3]:
                parsed = urlparse(candidate)
                if parsed.scheme not in ("http", "https") or not parsed.netloc:
                    st.warning(f"Skipped invalid URL: {candidate}")
                    continue
                try:
                    article = Article(candidate, request_timeout=15)
                    article.download()
                    article.parse()
                    candidate_claims = extract_claims(article.text or "", limit=1)
                    rows.append({"Domain": parsed.netloc, "Title": article.title or "Untitled", "Published": str(article.publish_date.date()) if article.publish_date else "Unknown", "Candidate claim": candidate_claims[0] if candidate_claims else "No claim extracted"})
                    if candidate_claims:
                        st.markdown(f"**{article.title or 'Article'} — claim lookup**")
                        render_claim_check(
                            candidate_claims[0], st.session_state.get("claim_vectorizer"),
                            st.session_state.get("claim_model"), WIKIPEDIA_LANGUAGES[compare_evidence_language],
                            st.session_state.get("xlmr_verifier"),
                        )
                except Exception as error:
                    st.warning(f"Could not analyze {parsed.netloc} ({type(error).__name__}).")
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.divider()
    st.caption("Educational prototype · Model estimates and related pages are research aids, not verified verdicts or source-credibility ratings.")

def render_casebook_page():
    st.markdown(textwrap.dedent(f"""
    <style>
    :root {{ color-scheme: light; }}
    .stApp {{ background:#f4f1e9; color:#171915; font-family:'Manrope',sans-serif; }}
    .block-container {{ max-width:1460px; padding:1rem 2.25rem 4rem; }}
    .casebook-brand {{ display:flex; align-items:center; gap:12px; padding:8px 0 20px; border-bottom:1px solid #d7d3c9; margin-bottom:24px; color:#171915; font:800 .9rem 'Manrope',sans-serif; letter-spacing:.12em; }}
    .casebook-brand img {{ width:40px; height:40px; }}
    [data-testid="stMetric"] {{ border:1px solid #d7d3c9; border-radius:3px; background:#ebe7dd; padding:16px 18px; }}
    [data-testid="stMetricLabel"] p {{ color:#65655e; }}
    [data-testid="stMetricValue"] {{ color:#e5654b; }}
    [data-testid="stRadio"] label,[data-testid="stRadio"] label * {{ color:#171915!important; opacity:1!important; }}
    .stButton button {{ background:#e5654b!important; color:#fffaf2!important; border:0!important; font-weight:700; }}
    .stButton button:hover {{ background:#b7432f!important; color:#fffaf2!important; }}
    </style>
    <header class="casebook-brand"><img src="{BRAND_MARK_DATA_URI}" alt="" /> VERIFY / NEWS · CASEBOOK</header>
    """), unsafe_allow_html=True)
    render_casebook()
    st.divider()
    st.caption("Educational prototype · Retrieved context and reviewer labels are not verified verdicts or source-credibility ratings.")


casebook_page = None

def run_app():
    global casebook_page
    st.set_page_config(page_title="VerifyNews AI", page_icon=str(BRAND_MARK_PATH), layout="wide")
    home_page = st.Page(render_main_page, title="Analyze", icon="📰", url_path="home", default=True)
    casebook_page = st.Page(render_casebook_page, title="Casebook", icon="🗂️", url_path="casebook")
    navigation = st.navigation([home_page, casebook_page], position="top")
    navigation.run()
