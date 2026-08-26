import json
import os
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

st.set_page_config(page_title="Стратсессия · ТРИ ЦЕНЫ", page_icon="✦", layout="wide", initial_sidebar_state="collapsed")

SESSION_CODE = "TRI2026"
STAGES = {
    1: ("СТАРТ", 10),
    2: ("ПРЕЗЕНТАЦИЯ", 14),
    3: ("КАРТА ПРИЧИН", 10),
    4: ("ГЕНЕРАЦИЯ", 22),
    5: ("РАЗВИТИЕ", 8),
    6: ("УСИЛЕНИЕ", 23),
    7: ("ПРОВОКАЦИИ", 15),
    8: ("КЛАСТЕРЫ", 12),
    9: ("ПРИОРИТЕТ", 7),
    10: ("ПЛАН", 15),
}
TARGETS = {"Сентябрь": 552_500, "Октябрь": 571_950}
MOTIVES = [
    "Мне это нужно", "Там выгодно", "Интересно, что появилось", "Надо успеть",
    "Зайду по пути", "Мне рассказали", "Давно не был — посмотрю"
]
PROVOCATIONS = [
    ("БЮДЖЕТ = 0", "Что можем сделать, используя только магазины, фасады, сотрудников, ассортимент, покупателей и партнёров?"),
    ("ТОЛЬКО 500 МЕТРОВ", "Как превратить конкретный магазин в заметную точку района?"),
    ("У ТЕБЯ 3 СЕКУНДЫ", "Что человек должен увидеть у входа, чтобы решить: «я хочу зайти»?"),
    ("ВЕРНИ ЧЕРЕЗ 7 ДНЕЙ", "Что должно обновляться каждую неделю, чтобы появился повод вернуться?"),
    ("ПРИВЕДИ ЕЩЁ ОДНОГО", "Что заставит покупателя рассказать о нас или прийти с кем-то ещё?"),
    ("КАЖДУЮ НЕДЕЛЮ УДИВЛЯЕМ", "Что может сформировать привычку: «надо зайти — интересно, что появилось»?"),
    ("СЕНТЯБРЬ–ОКТЯБРЬ", "Какие сезонные изменения поведения можно превратить в повод для дополнительного визита?"),
]

st.markdown("""
<style>
:root{
  --ink:#17223A; --ink2:#2A3855; --teal:#13A7A7; --teal2:#EAF9F8;
  --bg:#F3F6F9; --card:#FFFFFF; --line:#DDE5EC; --muted:#748094;
  --red:#E96C7B; --redbg:#FFF0F3; --green:#3BAA83; --greenbg:#EAF7F2;
  --amber:#F1B94A; --amberbg:#FFF7DB; --violet:#9170D7; --violetbg:#F2ECFF;
  --blue:#4A9EEB; --bluebg:#EAF4FE; --shadow:0 14px 36px rgba(34,51,80,.08);
}
html,body,[class*="css"]{font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.stApp{background:linear-gradient(180deg,#F7F9FB 0%,#F1F5F8 100%)}
.block-container{padding-top:.8rem;padding-bottom:2.5rem;max-width:1580px}
#MainMenu,footer,header{visibility:hidden}
.topline{height:6px;background:linear-gradient(90deg,var(--teal),#65CFC5);border-radius:999px;margin:2px 0 18px}
.hero{font-size:2.15rem;font-weight:900;color:var(--ink);line-height:1.03;letter-spacing:-.035em;margin:0 0 7px}
.sub{color:var(--muted);font-size:1.02rem;margin-bottom:14px}
.kicker{font-size:.74rem;letter-spacing:.11em;font-weight:900;color:#078B8B;text-transform:uppercase;margin-bottom:5px}
.bigq{font-size:1.68rem;font-weight:900;line-height:1.16;color:var(--ink);margin:5px 0 12px;letter-spacing:-.025em}
.board-card{background:rgba(255,255,255,.96);border:1px solid var(--line);border-radius:19px;padding:18px 20px;box-shadow:var(--shadow)}
.soft-card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:15px 16px;box-shadow:0 7px 18px rgba(34,51,80,.045)}
.note{border-left:4px solid var(--teal);background:var(--teal2);border-radius:11px;padding:12px 14px;color:#34435B;line-height:1.4}
.note.warn{border-left-color:var(--red);background:var(--redbg)}
.note.success{border-left-color:var(--green);background:var(--greenbg)}
.note.amber{border-left-color:var(--amber);background:var(--amberbg)}
.stagebar{display:flex;gap:7px;overflow-x:auto;padding:5px 1px 12px;scrollbar-width:thin}
.stagepill{min-width:122px;padding:9px 10px;border:1px solid var(--line);border-radius:13px;background:rgba(255,255,255,.9);color:var(--ink2);font-size:.72rem;font-weight:800;box-shadow:0 4px 11px rgba(34,51,80,.035)}
.stagepill.active{background:var(--teal2);border-color:#80D9D3;color:#087E7E;box-shadow:0 7px 20px rgba(18,166,166,.12)}
.stagepill.done{background:#F2F5F7;color:#9AA4B4}
.stage-num{font-size:.95rem;font-weight:950;margin-bottom:2px}
.stage-min{font-weight:600;color:#8C98AA;font-size:.68rem;margin-top:2px}
.sticky{border-radius:14px;padding:14px 14px 12px;min-height:110px;border:1px solid rgba(23,34,58,.07);box-shadow:0 8px 17px rgba(34,51,80,.07);margin-bottom:11px;word-break:break-word}
.sticky .body{font-size:.92rem;line-height:1.35;color:#283650;font-weight:660}
.sticky .author{margin-top:9px;font-size:.72rem;color:#7D8798;font-weight:650}
.yellow{background:#FFF2A8}.green{background:#DFF3C7}.pink{background:#FFD9DF}.purple{background:#ECDDFF}.blue{background:#DDF2FF}.white{background:#fff}
.section-label{font-weight:900;font-size:.96rem;color:var(--ink);margin:4px 0 9px}
.chip{display:inline-block;padding:6px 9px;border:1px solid #D9E1EA;border-radius:999px;background:#fff;color:#5D6A7E;font-size:.75rem;font-weight:750;margin:3px 4px 3px 0}
.metricbox{background:#fff;border:1px solid var(--line);border-radius:16px;padding:14px 16px;box-shadow:0 6px 18px rgba(34,51,80,.04)}
.metricbox .label{font-size:.72rem;text-transform:uppercase;letter-spacing:.075em;color:#7A8799;font-weight:850}.metricbox .value{font-size:1.7rem;color:var(--ink);font-weight:950;margin-top:3px}
.participant{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border:1px solid var(--line);border-radius:999px;background:#fff;margin:3px 4px 3px 0;font-size:.78rem;font-weight:720;color:#4D5B70}.dot{width:7px;height:7px;background:#43B98C;border-radius:50%}
.syncbox{background:#fff;border:1px dashed #BFCBDA;border-radius:12px;padding:9px 12px;color:#617087;font-size:.80rem}
.adminbadge{display:inline-block;padding:5px 9px;border-radius:8px;background:#17223A;color:white;font-size:.72rem;font-weight:800}
hr{border:none;border-top:1px solid #E1E7EE;margin:1rem 0}
div[data-testid="stButton"] button,div[data-testid="stDownloadButton"] button,div[data-testid="stLinkButton"] a{border-radius:11px;font-weight:800;min-height:42px}
div[data-testid="stForm"]{border:1px solid #E0E7EE;border-radius:16px;padding:15px 15px 4px;background:rgba(255,255,255,.78)}
div[data-testid="stTextArea"] textarea,div[data-testid="stTextInput"] input{border-radius:10px;border-color:#D6E0E9}
.stTabs [data-baseweb="tab-list"]{gap:8px}.stTabs [data-baseweb="tab"]{border-radius:10px;padding:8px 14px;background:#fff;border:1px solid var(--line)}
@media(max-width:760px){.hero{font-size:1.55rem}.bigq{font-size:1.28rem}.block-container{padding-left:.8rem;padding-right:.8rem}.stagepill{min-width:106px}.sticky{min-height:90px}}
</style>
""", unsafe_allow_html=True)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    def __init__(self):
        self.lock = threading.RLock()
        self.reset()

    def reset(self):
        with getattr(self, "lock", threading.RLock()):
            self.state = {
                "session": {
                    "code": SESSION_CODE,
                    "title": "Стратегическая сессия · Трафик ТРИ ЦЕНЫ",
                    "current_stage": 1,
                    "stage_started_at": utcnow(),
                    "presentation_url": "",
                    "active_provocation": 0,
                },
                "participants": [], "cards": [], "votes": [], "action_plan": [], "next_card_id": 1,
            }

    def snapshot(self):
        with self.lock:
            return deepcopy(self.state)

    def restore(self, data):
        with self.lock:
            required = {"session", "participants", "cards", "votes", "action_plan"}
            if not isinstance(data, dict) or not required.issubset(data.keys()):
                raise ValueError("Файл не похож на резервную копию этой доски.")
            data.setdefault("next_card_id", max([c.get("id", 0) for c in data.get("cards", [])] + [0]) + 1)
            data["session"].setdefault("presentation_url", "")
            data["session"].setdefault("active_provocation", 0)
            self.state = deepcopy(data)


@st.cache_resource
def get_store():
    return MemoryStore()


store = get_store()


def snapshot(): return store.snapshot()
def get_session(): return snapshot()["session"]

def set_stage(stage):
    with store.lock:
        store.state["session"]["current_stage"] = int(stage)
        store.state["session"]["stage_started_at"] = utcnow()

def set_presentation_url(url):
    with store.lock: store.state["session"]["presentation_url"] = url.strip()

def set_provocation(idx):
    with store.lock: store.state["session"]["active_provocation"] = max(0, min(idx, len(PROVOCATIONS)-1))

def add_or_touch_participant(token, name):
    with store.lock:
        for p in store.state["participants"]:
            if p["token"] == token:
                p["name"] = name; p["last_seen"] = utcnow(); return
        store.state["participants"].append({"session_code":SESSION_CODE,"name":name,"token":token,"last_seen":utcnow()})

def participants(): return snapshot()["participants"]

def add_card(stage, body, lane=None, title=None, parent_id=None):
    if not body.strip(): return
    with store.lock:
        cid=store.state["next_card_id"]; store.state["next_card_id"]+=1
        store.state["cards"].append({
            "id":cid,"session_code":SESSION_CODE,"stage":int(stage),"author_token":st.session_state.get("token"),
            "author_name":st.session_state.get("name", ""),"lane":lane,"title":title,"body":body.strip(),
            "parent_id":parent_id,"cluster":None,"created_at":utcnow(),
        })

def get_cards(stage=None):
    cards=snapshot()["cards"]
    return cards if stage is None else [c for c in cards if int(c.get("stage",0))==int(stage)]

def update_card(card_id, **kwargs):
    with store.lock:
        for c in store.state["cards"]:
            if c["id"]==card_id:
                c.update(kwargs); return

def get_votes(): return snapshot()["votes"]

def add_vote(card_id, voter_token):
    with store.lock:
        votes=store.state["votes"]; mine=[v for v in votes if v["voter_token"]==voter_token]
        if len(mine)>=5 or any(v["voter_token"]==voter_token and v["card_id"]==card_id for v in votes): return False
        votes.append({"session_code":SESSION_CODE,"voter_token":voter_token,"card_id":card_id,"created_at":utcnow()}); return True

def remove_vote(card_id,voter_token):
    with store.lock:
        store.state["votes"]=[v for v in store.state["votes"] if not(v["voter_token"]==voter_token and v["card_id"]==card_id)]

def get_plans(): return sorted(snapshot()["action_plan"], key=lambda x:x["rank"])

def upsert_plan(rank,payload):
    with store.lock:
        existing=next((p for p in store.state["action_plan"] if p["rank"]==rank),None)
        if existing: existing.update(payload)
        else:
            row={"rank":rank,"session_code":SESSION_CODE}; row.update(payload); store.state["action_plan"].append(row)

def rerun(): st.rerun()

def fmt_num(n): return f"{int(n):,}".replace(","," ")


def timer_component(start_iso, minutes):
    html=f"""
    <div style='font-family:Inter,Arial,sans-serif;background:#fff;border:1px solid #DDE5EC;border-radius:15px;padding:12px 14px;display:flex;align-items:center;justify-content:space-between'>
      <div><div style='font-size:11px;color:#7A8799;font-weight:800;letter-spacing:.08em'>ТАЙМЕР ЭТАПА</div><div id='timer' style='font-size:28px;color:#17223A;font-weight:900'>--:--</div></div>
      <div id='status' style='font-size:12px;color:#748094;font-weight:700'>идёт работа</div>
    </div>
    <script>
      const start=new Date('{start_iso}'); const total={minutes}*60;
      function tick(){{
        const passed=Math.floor((Date.now()-start.getTime())/1000); const left=total-passed;
        const el=document.getElementById('timer'), status=document.getElementById('status');
        if(left<=0){{el.innerText='00:00'; el.style.color='#E96C7B'; status.innerText='время вышло'; return;}}
        const m=String(Math.floor(left/60)).padStart(2,'0'), s=String(left%60).padStart(2,'0'); el.innerText=m+':'+s;
      }}
      tick(); setInterval(tick,1000);
    </script>"""
    components.html(html,height=72)


def chips(items):
    st.markdown("".join([f'<span class="chip">{x}</span>' for x in items]), unsafe_allow_html=True)


def card_list(cards, color="yellow", show_author=True, cols_count=4, show_parent=False):
    if not cards:
        st.caption("Пока пусто — добавьте первую карточку."); return
    cols=st.columns(min(cols_count,max(1,len(cards))))
    parent_map={c["id"]:c for c in get_cards()}
    for i,item in enumerate(cards):
        with cols[i%len(cols)]:
            parent=""
            if show_parent and item.get("parent_id"):
                p=parent_map.get(item["parent_id"])
                if p: parent=f'<div style="font-size:.70rem;color:#7E889A;margin-bottom:7px">↳ развитие #{p["id"]}: {p["body"][:52]}…</div>'
            author=f'<div class="author">{item.get("author_name") or ""} · #{item["id"]}</div>' if show_author else ""
            st.markdown(f'<div class="sticky {color}">{parent}<div class="body">{item["body"]}</div>{author}</div>',unsafe_allow_html=True)


# LOBBY
if "token" not in st.session_state:
    st.markdown('<div class="topline"></div>',unsafe_allow_html=True)
    c1,c2=st.columns([1.65,1],gap="large")
    with c1:
        st.markdown('<div class="hero">СТРАТЕГИЧЕСКАЯ СЕССИЯ · ТРАФИК ТРИ ЦЕНЫ</div>',unsafe_allow_html=True)
        st.markdown('<div class="sub">Рабочая доска для совместной сессии · 8 участников · сентябрь–октябрь</div>',unsafe_allow_html=True)
        st.markdown('<div class="board-card"><div class="kicker">Главный вопрос</div><div class="bigq">Что заставит человека, который иначе НЕ пришёл бы в ТРИ ЦЕНЫ, решить зайти в магазин?</div><div class="note">На выходе: несколько инициатив, которые можно взять в работу в ближайшие недели и измерить по дополнительному трафику.</div></div>',unsafe_allow_html=True)
        st.write("")
        chips(["Сначала количество", "Идеи не критикуем", "1 карточка = 1 идея", "Думаем про физический трафик"])
    with c2:
        st.markdown('<div class="board-card"><div class="kicker">Вход участника</div><div style="font-size:1.1rem;font-weight:850;color:#17223A;margin-bottom:12px">Как вас показывать на доске?</div>',unsafe_allow_html=True)
        name=st.text_input("Имя",placeholder="Например, Анна",label_visibility="collapsed")
        if st.button("Присоединиться к сессии",use_container_width=True,type="primary",disabled=not name.strip()):
            token=str(uuid.uuid4()); st.session_state.token=token; st.session_state.name=name.strip(); add_or_touch_participant(token,name.strip()); rerun()
        st.markdown('<div class="small" style="margin-top:10px">Ссылка одна для всех. Никакой регистрации и отдельного аккаунта не требуется.</div></div>',unsafe_allow_html=True)
    st.stop()

add_or_touch_participant(st.session_state.token,st.session_state.name)
session=get_session(); current_stage=int(session["current_stage"])

# gentle auto sync every 6 sec, does not require DB
if st_autorefresh:
    st_autorefresh(interval=6000,key="board_autorefresh")

st.markdown('<div class="topline"></div>',unsafe_allow_html=True)
head1,head2=st.columns([4,1],gap="large")
with head1:
    st.markdown(f'<div class="hero">{session["title"]}</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="sub">Вы: <b>{st.session_state.name}</b> · этап {current_stage}/10 · общая доска обновляется автоматически</div>',unsafe_allow_html=True)
with head2:
    admin_pin=st.text_input("PIN ведущего",type="password",key="admin_pin",placeholder="PIN")
    try: configured_pin=st.secrets.get("ADMIN_PIN","2026")
    except Exception: configured_pin=os.getenv("ADMIN_PIN","2026")
    is_admin=bool(admin_pin) and admin_pin==configured_pin
    if is_admin: st.markdown('<span class="adminbadge">РЕЖИМ ВЕДУЩЕГО</span>',unsafe_allow_html=True)

pills=''.join([
    f'<div class="stagepill {"active" if n==current_stage else "done" if n<current_stage else ""}"><div class="stage-num">{n:02d}</div>{name}<div class="stage-min">{mins} мин</div></div>'
    for n,(name,mins) in STAGES.items()
])
st.markdown(f'<div class="stagebar">{pills}</div>',unsafe_allow_html=True)

ppl=participants()
left,mid,right=st.columns([2.25,1,1],gap="medium")
with left:
    st.markdown(''.join([f'<span class="participant"><span class="dot"></span>{p["name"]}</span>' for p in ppl]),unsafe_allow_html=True)
with mid:
    if st.button("↻ Обновить",use_container_width=True): rerun()
with right:
    if is_admin:
        nav=st.columns(2)
        with nav[0]:
            if st.button("←",disabled=current_stage<=1,use_container_width=True): set_stage(current_stage-1); rerun()
        with nav[1]:
            if st.button("Следующий →",disabled=current_stage>=10,use_container_width=True,type="primary"): set_stage(current_stage+1); rerun()

if is_admin:
    with st.expander("⚙️ Ведущий · управление и резервная копия"):
        a,b,c=st.columns([1.05,1.3,.85])
        backup=json.dumps(store.snapshot(),ensure_ascii=False,indent=2).encode("utf-8")
        with a: st.download_button("Скачать backup",backup,file_name="strategy_board_backup.json",mime="application/json",use_container_width=True)
        with b:
            upload=st.file_uploader("Восстановить JSON",type=["json"],label_visibility="collapsed")
            if upload is not None and st.button("Восстановить",use_container_width=True):
                try: store.restore(json.load(upload)); st.success("Доска восстановлена"); rerun()
                except Exception as exc: st.error(str(exc))
        with c:
            if st.button("Очистить",use_container_width=True): store.reset(); add_or_touch_participant(st.session_state.token,st.session_state.name); rerun()

stage_name,stage_mins=STAGES[current_stage]
bar1,bar2=st.columns([4,1],gap="medium")
with bar1:
    st.markdown(f'<div class="kicker">ЭТАП {current_stage:02d} · {stage_name}</div>',unsafe_allow_html=True)
with bar2:
    timer_component(session["stage_started_at"],stage_mins)

# STAGES
if current_stage==1:
    st.markdown('<div class="bigq">Почему человек может зайти в ТРИ ЦЕНЫ в сентябре–октябре?</div>',unsafe_allow_html=True)
    st.markdown('<div class="note amber">Сейчас не придумываем рекламу и акции. Нужны <b>мотивы визита</b>: что должно произойти в жизни человека или в его голове, чтобы он решил зайти?</div>',unsafe_allow_html=True)
    st.write("")
    c1,c2=st.columns([1,2],gap="large")
    with c1:
        with st.form("s1",clear_on_submit=True):
            body=st.text_area("Одна причина — одна карточка",placeholder="Например: похолодало, нужно докупить вещи для дома…",height=120)
            if st.form_submit_button("Добавить стикер",type="primary",use_container_width=True) and body.strip(): add_card(1,body); rerun()
        st.markdown('<div class="section-label">Подсказки, если мысли закончились</div>',unsafe_allow_html=True); chips(MOTIVES)
    with c2: card_list(get_cards(1),"yellow",cols_count=3)

elif current_stage==2:
    st.markdown('<div class="bigq">Презентация Дениса · исходная ситуация</div>',unsafe_allow_html=True)
    c1,c2=st.columns([1.25,1],gap="large")
    with c1:
        st.markdown('<div class="board-card"><div class="kicker">Трансляция отдельно</div><div style="font-size:1.35rem;font-weight:900;color:#17223A;margin:5px 0 10px">Презентация не дублируется на доске</div><div class="sub">Ведущий открывает её и транслирует участникам. На доске остаётся только переход к следующей работе.</div></div>',unsafe_allow_html=True)
        url=session.get("presentation_url","")
        if is_admin:
            new_url=st.text_input("Ссылка на презентацию",value=url,placeholder="https://...")
            if st.button("Сохранить ссылку"): set_presentation_url(new_url); rerun()
        if url: st.link_button("▶ Открыть презентацию",url,use_container_width=True)
    with c2:
        st.markdown('<div class="board-card"><div class="kicker">Переход</div><div class="bigq">Цифры показали, ГДЕ проблема.</div><div class="note">Теперь ищем <b>ПОЧЕМУ человек должен прийти</b> и <b>КАК превратить этот мотив в механику</b>.</div></div>',unsafe_allow_html=True)

elif current_stage==3:
    st.markdown('<div class="bigq">Какие причины посещения мы недоиспользуем?</div>',unsafe_allow_html=True)
    st.markdown('<div class="note">Берём причины из разогрева и раскладываем их по зрелости. Не обсуждаем инструменты — только силу самого мотива.</div>',unsafe_allow_html=True)
    source=get_cards(1)
    if is_admin and source:
        option_map={f'#{c["id"]} · {c["body"][:90]}':c["id"] for c in source}
        a,b,c=st.columns([2.2,1.4,1])
        with a: selected=st.selectbox("Причина",list(option_map.keys()),key="s3source")
        with b: lane=st.selectbox("Куда",["Уже хорошо используем","Можем использовать сильнее","Почти не используем"])
        with c:
            st.write("")
            if st.button("Разместить",use_container_width=True): update_card(option_map[selected],lane=lane); rerun()
    lanes=[("Уже хорошо используем","green"),("Можем использовать сильнее","yellow"),("Почти не используем","pink")]
    cols=st.columns(3,gap="medium")
    for idx,(lane,color) in enumerate(lanes):
        with cols[idx]:
            st.markdown(f'<div class="section-label">{lane}</div>',unsafe_allow_html=True)
            assigned=[c for c in source if c.get("lane")==lane]
            card_list(assigned,color,cols_count=1)

elif current_stage==4:
    st.markdown('<div class="bigq">Тихая генерация · трафиковые гипотезы</div>',unsafe_allow_html=True)
    st.markdown('<div class="note amber">Формула карточки обязательна: <b>что делаем → почему из-за этого человек придёт</b>. Сейчас не оцениваем бюджет, сложность и согласования.</div>',unsafe_allow_html=True)
    tabs=st.tabs(["Новые клиенты","Текущая база / частота"])
    configs=[
        ("Новые клиенты","blue","Что заставит человека, который сейчас НЕ ходит в ТРИ ЦЕНЫ, прийти?",["сильный товар","сезонный повод","фасад","500 м вокруг ТО","digital","партнёры","изменить маршрут"]),
        ("Текущая база","purple","Что заставит существующего покупателя прийти ЧАЩЕ?",["через 7 дней","CRM","купон","новинки","регулярная механика","приведи друга"])
    ]
    for tab,(lane,color,prompt,hints) in zip(tabs,configs):
        with tab:
            st.markdown(f'<div class="section-label">{prompt}</div>',unsafe_allow_html=True); chips(hints)
            st.write("")
            a,b=st.columns([1,1.8],gap="large")
            with a:
                with st.form(f"s4_{lane}",clear_on_submit=True):
                    what=st.text_input("Что делаем",key=f"what_{lane}")
                    why=st.text_input("Почему человек придёт",key=f"why_{lane}")
                    if st.form_submit_button("Добавить идею",type="primary",use_container_width=True) and what.strip() and why.strip(): add_card(4,f"{what.strip()} → {why.strip()}",lane=lane); rerun()
            with b: card_list([c for c in get_cards(4) if c.get("lane")==lane],color,cols_count=3)

elif current_stage==5:
    st.markdown('<div class="bigq">Не придумывай новую идею. Усиль чужую.</div>',unsafe_allow_html=True)
    st.markdown('<div class="note">Выберите карточку коллеги и создайте новую версию рядом. Не исправляйте исходную — пусть будет видна эволюция мысли.</div>',unsafe_allow_html=True)
    source=[c for c in get_cards(4) if c.get("author_token")!=st.session_state.token] or get_cards(4)
    a,b=st.columns([1,2],gap="large")
    with a:
        options={f'#{c["id"]} · {c["body"][:82]}':c["id"] for c in source}
        if options:
            selected=st.selectbox("Выберите исходную идею",list(options.keys()))
            chips(["локально","каждую неделю","без скидки","через фасад","через digital","другой сегмент","приведи друга","ограничить время"])
            with st.form("s5",clear_on_submit=True):
                body=st.text_area("Как вы её усиливаете?",height=120)
                if st.form_submit_button("Добавить развитие",type="primary",use_container_width=True) and body.strip(): add_card(5,body,parent_id=options[selected]); rerun()
    with b: card_list(get_cards(5),"purple",cols_count=3,show_parent=True)

elif current_stage==6:
    st.markdown('<div class="bigq">Лаборатория сильных идей</div>',unsafe_allow_html=True)
    st.markdown('<div class="note">Берём перспективные ходы и превращаем их в понятную механику. Единственный фильтр пока — усилить вероятность реального визита.</div>',unsafe_allow_html=True)
    a,b=st.columns([1.1,1.7],gap="large")
    with a:
        with st.form("s6",clear_on_submit=True):
            idea=st.text_input("Что делаем?")
            audience=st.text_input("Для кого?")
            why=st.text_input("Почему человек придёт?")
            stronger=st.text_input("Как сделать повод сильнее?")
            regular=st.text_input("Как сделать регулярным?")
            before=st.text_input("Как узнает ДО визита?")
            measure=st.text_input("Как измерим дополнительный визит?")
            if st.form_submit_button("Сохранить карточку",type="primary",use_container_width=True) and idea.strip():
                body=f"Что: {idea} | Для кого: {audience} | Почему придёт: {why} | Усиление: {stronger} | Регулярность: {regular} | До визита: {before} | Измерение: {measure}"
                add_card(6,body,title=idea); rerun()
    with b: card_list(get_cards(6),"blue",cols_count=3)

elif current_stage==7:
    idx=int(session.get("active_provocation",0)); title,prompt=PROVOCATIONS[idx]
    st.markdown('<div class="bigq">Провокации · ломаем привычные маршруты мышления</div>',unsafe_allow_html=True)
    if is_admin:
        pc=st.columns([1,1,3])
        with pc[0]:
            if st.button("← Карта",disabled=idx<=0,use_container_width=True): set_provocation(idx-1); rerun()
        with pc[1]:
            if st.button("Карта →",disabled=idx>=len(PROVOCATIONS)-1,use_container_width=True,type="primary"): set_provocation(idx+1); rerun()
    st.markdown(f'<div class="board-card" style="border-color:#F2BCC4;background:#FFF7F8"><div class="kicker" style="color:#D85568">КАРТА {idx+1}/7</div><div class="bigq">{title}</div><div style="color:#59667A;font-size:1rem;line-height:1.45">{prompt}</div></div>',unsafe_allow_html=True)
    st.write("")
    a,b=st.columns([1,2],gap="large")
    with a:
        with st.form("s7",clear_on_submit=True):
            body=st.text_area("Новый ход",placeholder="Запишите даже направление — не обязательно готовую акцию",height=135)
            if st.form_submit_button("Добавить идею",type="primary",use_container_width=True) and body.strip(): add_card(7,body,lane=title); rerun()
    with b: card_list([c for c in get_cards(7) if c.get("lane")==title],"pink",cols_count=3)

elif current_stage==8:
    st.markdown('<div class="bigq">Из множества идей — в 5–8 направлений</div>',unsafe_allow_html=True)
    source=get_cards(4)+get_cards(5)+get_cards(6)+get_cards(7)
    st.markdown('<div class="note">Группируем похожие идеи. Названия направлений не задаём заранее — они должны проявиться из материала команды.</div>',unsafe_allow_html=True)
    if is_admin and source:
        a,b,c=st.columns([2.4,1.4,1])
        option_map={f'#{x["id"]} · {(x.get("title") or x["body"])[:85]}':x["id"] for x in source}
        with a: selected=st.selectbox("Карточка",list(option_map.keys()))
        with b: cluster=st.text_input("Название направления",placeholder="Напр. локальный трафик")
        with c:
            st.write("")
            if st.button("В кластер",use_container_width=True) and cluster.strip(): update_card(option_map[selected],cluster=cluster.strip()); rerun()
    clustered=[c for c in source if c.get("cluster")]
    clusters=sorted(set(c["cluster"] for c in clustered))
    if clusters:
        cols=st.columns(min(3,len(clusters)),gap="medium")
        for i,cl in enumerate(clusters):
            with cols[i%len(cols)]:
                st.markdown(f'<div class="section-label">{cl}</div>',unsafe_allow_html=True)
                card_list([c for c in clustered if c["cluster"]==cl],"white",cols_count=1)
    else: st.info("Пока нет кластеров. Ведущий быстро группирует идеи вместе с командой.")

elif current_stage==9:
    st.markdown('<div class="bigq">Приоритизация · что реально стоит запускать?</div>',unsafe_allow_html=True)
    st.markdown('<div class="note">Смотрим на 4 критерия: <b>потенциал трафика · скорость запуска · масштабируемость · стоимость</b>. После этого у каждого 5 голосов.</div>',unsafe_allow_html=True)
    candidates=[c for c in get_cards() if c.get("cluster")] or get_cards(6)
    votes=get_votes(); mine={v["card_id"] for v in votes if v["voter_token"]==st.session_state.token}
    m1,m2=st.columns([1,3])
    with m1: st.markdown(f'<div class="metricbox"><div class="label">Ваши голоса</div><div class="value">{len(mine)} / 5</div></div>',unsafe_allow_html=True)
    with m2: chips(["потенциал трафика","скорость запуска","масштабируемость","стоимость"])
    st.write("")
    for c in candidates:
        count=sum(1 for v in votes if v["card_id"]==c["id"])
        x,y=st.columns([5,1],gap="medium")
        with x:
            st.markdown(f'<div class="soft-card"><div style="font-weight:900;color:#17223A">#{c["id"]} · {c.get("title") or c["body"][:160]}</div><div class="small" style="margin-top:6px">{c.get("cluster") or "без направления"} · {count} голосов</div></div>',unsafe_allow_html=True)
        with y:
            if c["id"] in mine:
                if st.button("✓ Голос",key=f"uv{c['id']}",use_container_width=True): remove_vote(c["id"],st.session_state.token); rerun()
            elif len(mine)<5:
                if st.button("+ Голос",key=f"v{c['id']}",use_container_width=True,type="primary"): add_vote(c["id"],st.session_state.token); rerun()
    ranking=sorted([(sum(1 for v in get_votes() if v["card_id"]==c["id"]),c) for c in candidates],key=lambda x:x[0],reverse=True)
    st.write(""); st.markdown('<div class="section-label">TOP-8 по голосам</div>',unsafe_allow_html=True)
    if ranking:
        topcols=st.columns(min(4,len(ranking[:8])))
        for i,(count,c) in enumerate(ranking[:8],1):
            with topcols[(i-1)%len(topcols)]:
                st.markdown(f'<div class="sticky green"><div class="body"><b>{i}. {count} голосов</b><br>{c.get("title") or c["body"][:90]}</div></div>',unsafe_allow_html=True)

elif current_stage==10:
    st.markdown('<div class="bigq">TOP-3 → ответственный → срок → измеримый эффект</div>',unsafe_allow_html=True)
    votes=get_votes(); counts={}
    for v in votes: counts[v["card_id"]]=counts.get(v["card_id"],0)+1
    cards={c["id"]:c for c in get_cards()}; top_ids=[cid for cid,_ in sorted(counts.items(),key=lambda kv:kv[1],reverse=True)[:3] if cid in cards]
    plans=get_plans(); by_rank={p["rank"]:p for p in plans}
    k1,k2,k3=st.columns(3,gap="medium")
    with k1: st.markdown(f'<div class="metricbox"><div class="label">Цель · сентябрь</div><div class="value">{fmt_num(TARGETS["Сентябрь"])}</div></div>',unsafe_allow_html=True)
    with k2: st.markdown(f'<div class="metricbox"><div class="label">Цель · октябрь</div><div class="value">{fmt_num(TARGETS["Октябрь"])}</div></div>',unsafe_allow_html=True)
    with k3:
        total=sum(int(p.get("extra_traffic") or 0) for p in plans)
        st.markdown(f'<div class="metricbox"><div class="label">Доп. трафик TOP-3</div><div class="value">+{fmt_num(total)}</div></div>',unsafe_allow_html=True)
    st.write("")
    tabs=st.tabs(["Инициатива 1","Инициатива 2","Инициатива 3"])
    for rank,tab in enumerate(tabs,1):
        with tab:
            default=""
            if len(top_ids)>=rank:
                c=cards[top_ids[rank-1]]; default=c.get("title") or c["body"][:120]
            e=by_rank.get(rank,{})
            with st.form(f"plan_{rank}"):
                c1,c2=st.columns(2)
                with c1:
                    initiative=st.text_input("Что запускаем",value=e.get("initiative") or default)
                    audience=st.text_input("Для кого",value=e.get("audience") or "")
                    reason=st.text_input("Почему придёт",value=e.get("reason") or "")
                    channel=st.text_input("Канал / как узнает",value=e.get("channel") or "")
                    start_date=st.text_input("Старт / срок",value=e.get("start_date") or "")
                with c2:
                    extra=st.number_input("Ожидаемый доп. трафик",min_value=0,value=int(e.get("extra_traffic") or 0),step=100)
                    budget=st.text_input("Бюджет",value=e.get("budget") or "")
                    owner=st.text_input("Ответственный",value=e.get("owner") or "")
                    measurement=st.text_input("Как измеряем",value=e.get("measurement") or "")
                    review=st.text_input("Дата первой проверки",value=e.get("review_date") or "")
                if st.form_submit_button("Сохранить инициативу",type="primary",use_container_width=True):
                    upsert_plan(rank,{"initiative":initiative,"audience":audience,"reason":reason,"channel":channel,"start_date":start_date,"extra_traffic":int(extra),"budget":budget,"owner":owner,"measurement":measurement,"review_date":review,"updated_at":utcnow()}); rerun()
    st.write("")
    plans=get_plans()
    if plans:
        st.markdown('<div class="section-label">Итоговый план</div>',unsafe_allow_html=True)
        df=pd.DataFrame(plans)
        show=[x for x in ["rank","initiative","owner","start_date","extra_traffic","budget","measurement","review_date"] if x in df.columns]
        st.dataframe(df[show],use_container_width=True,hide_index=True)
    cards_df=pd.DataFrame(get_cards()); votes_df=pd.DataFrame(get_votes()); plans_df=pd.DataFrame(plans); parts=[]
    if not cards_df.empty: parts.append("КАРТОЧКИ\n"+cards_df.to_csv(index=False))
    if not votes_df.empty: parts.append("\nГОЛОСА\n"+votes_df.to_csv(index=False))
    if not plans_df.empty: parts.append("\nПЛАН\n"+plans_df.to_csv(index=False))
    st.download_button("Скачать протокол CSV","\n".join(parts).encode("utf-8-sig"),file_name="strategy_session_protocol.csv",mime="text/csv",use_container_width=True)

st.markdown("---")
st.caption("Фокус сессии: дополнительный физический трафик в ТРИ ЦЕНЫ. Карточка считается сильной, если понятно, почему из-за неё человек реально придёт в магазин.")
