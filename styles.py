"""Global CSS. Colors are applied through classes because Streamlit strips inline CSS variables."""
STAGE_COLORS = {"data": "#1F4E9A", "predict": "#1E7B45", "alert": "#F26B1D", "response": "#6B3FA0", "recovery": "#17357A"}

CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800&family=Inter:wght@400;500;600&display=swap');
:root{--ink:#0B2A5B;--orange:#F26B1D;--paper:#F3F6FB;--line:#D9E1EE}
html,body,[class*="css"],.stMarkdown{font-family:'Inter',sans-serif}
.block-container{padding-top:1.4rem;max-width:1280px}
#MainMenu,footer,header[data-testid="stHeader"]{visibility:hidden;height:0}

.hero{display:flex;justify-content:space-between;align-items:center;gap:24px;flex-wrap:wrap;
 background:linear-gradient(115deg,#fff 0%,#EAF1FB 55%,#FDE9DB 130%);border:1px solid var(--line);
 border-radius:22px;padding:24px 30px;box-shadow:0 16px 36px -28px rgba(11,42,91,.5)}
.hero h1{font-family:'Poppins';font-weight:800;font-size:3rem;line-height:1.05;margin:0;padding:0;color:var(--ink)}
.hero h1 span{color:var(--orange)}
.hero .sub{font-family:'Poppins';font-weight:600;color:#2b3f66;margin-top:6px;font-size:1.05rem}
.hero .tag{margin-top:8px;color:#52628a;letter-spacing:.5px;font-weight:600}
.hero .badge{font-family:'Poppins';font-weight:700;font-style:italic;color:var(--ink);text-align:right;line-height:1.2;
 border-right:5px solid var(--orange);padding-right:14px;font-size:1.2rem}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.chip{background:#fff;border:1px solid var(--line);border-radius:999px;padding:4px 12px;font-size:.82rem;font-weight:600;color:var(--ink)}

.pipe{display:grid;grid-template-columns:repeat(5,1fr);gap:16px;margin:16px 0 6px}
.step{position:relative;background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden}
.step .hd{background:var(--c);color:#fff;font-family:'Poppins';font-weight:700;font-size:.82rem;padding:9px 12px;min-height:44px}
.step .bd{padding:11px 12px;font-size:.82rem;color:#3a4a6e}
.step .ic{font-size:1.5rem}
.step b{display:block;color:var(--ink);font-size:.9rem;margin-top:2px}
.step .st{display:inline-block;margin-top:8px;font-size:.72rem;font-weight:700;color:var(--c)}
.step.done .st::before{content:"✔ "}
.step:not(:last-child)::after{content:"➜";position:absolute;right:-14px;top:9px;z-index:3;color:var(--ink);font-size:1rem}
@media (max-width:980px){.pipe{grid-template-columns:1fr}.step::after{display:none}}

.mrow{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:14px}
.mcard{background:var(--c);color:#fff;border-radius:14px;padding:14px 18px}
.mcard b{display:block;font-family:'Poppins';font-weight:800;font-size:2rem;line-height:1.1}
.mcard span{font-size:.85rem;opacity:.92}
.m-red{--c:#C62828}.m-blue{--c:#1F4E9A}.m-green{--c:#1E7B45}

.al{display:flex;align-items:center;gap:12px;background:#fff;border:1px solid var(--line);border-left:6px solid var(--lc);
 border-radius:12px;padding:9px 12px;margin-bottom:8px}
.al .ai{font-size:1.3rem}.al .at{flex:1;line-height:1.2}.al .at b{display:block;color:var(--ink);font-size:.92rem}
.al small{color:#5a6a8e}.al .av{text-align:right;font-weight:700;color:var(--lc);font-size:.85rem;line-height:1.2}
.lv-vh{--lc:#D62828}.lv-h{--lc:#F77F00}.lv-m{--lc:#E0A100}.lv-l{--lc:#4CAF50}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:.8rem;margin:4px 0 8px}
.legend i{display:inline-block;width:11px;height:11px;border-radius:50%;background:var(--lc);margin-right:5px}

.rh{display:flex;align-items:center;gap:12px;padding:12px 18px;border-radius:14px;background:var(--c);color:#fff;margin:6px 0 12px}
.rh .ic{font-size:1.6rem}.rh b{font-family:'Poppins';font-weight:700;font-size:1.15rem}.rh small{display:block;opacity:.88}

.phone{width:300px;max-width:100%;margin:6px auto;border:9px solid #14181f;border-radius:34px;background:#fff;overflow:hidden}
.phone .ph{background:#D62828;color:#fff;padding:16px 14px}
.phone .pa{font-weight:800;letter-spacing:1px;font-size:.95rem}
.phone .pt{font-family:'Poppins';font-weight:700;font-size:1.05rem;margin-top:2px}
.phone .pb{padding:12px 14px;font-size:.83rem;color:#1d2b4a}
.phone .pb p{margin:0 0 7px}
.phone .pr b{color:var(--lc)}
.phone ul{list-style:none;padding:0;margin:6px 0 0}
.phone li{padding-left:22px;position:relative;margin-bottom:4px}
.phone li::before{content:"✔";position:absolute;left:0;color:#1E7B45;font-weight:800}

.pill{display:inline-block;border-radius:999px;padding:2px 10px;font-size:.75rem;font-weight:700;color:#fff;background:var(--lc);margin-right:6px}
.tool{display:inline-block;background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:2px 9px;margin:2px 4px 2px 0;font-size:.8rem;font-weight:600;color:var(--ink)}
.disc{font-size:.8rem;color:#5a6a8e;border-top:1px solid var(--line);margin-top:22px;padding-top:10px}

.stTabs [data-baseweb="tab-list"]{gap:6px;background:#fff;border:1px solid var(--line);padding:5px;border-radius:14px;flex-wrap:wrap}
.stTabs [data-baseweb="tab"]{border-radius:10px;font-weight:600;padding:8px 14px}
.stTabs [aria-selected="true"]{background:var(--ink);color:#fff}
.stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{display:none}
.stButton>button[kind="primary"]{background:var(--ink);border:0;border-radius:12px;padding:.8rem 1rem;font-weight:700;transition:transform .15s}
.stButton>button[kind="primary"]:hover{transform:translateY(-1px);background:#143a7c}
[data-testid="stSidebar"]{background:#fff;border-right:1px solid var(--line)}
[data-testid="stChatMessage"]{background:#fff;border:1px solid var(--line);border-radius:14px}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:12px;padding:10px 14px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>"""

STAGE_CSS = "<style>" + "".join(f".c-{k}{{--c:{v}}}" for k, v in STAGE_COLORS.items()) + "</style>"
