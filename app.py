import json
import os
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Стратсессия · ТРИ ЦЕНЫ", page_icon="🧠", layout="wide")

SESSION_CODE = "TRI2026"
STAGES = {
    1: ("СТАРТ", 10),
    2: ("ПРЕЗЕНТАЦИЯ ДЕНИСА", 14),
    3: ("КАРТА ПРИЧИН", 10),
    4: ("ГЕНЕРАЦИЯ ИДЕЙ", 22),
    5: ("РАЗВИТИЕ ИДЕЙ", 8),
    6: ("ЛАБОРАТОРИЯ ИДЕЙ", 23),
    7: ("ПРОВОКАЦИИ", 15),
    8: ("СОБИРАЕМ НАПРАВЛЕНИЯ", 12),
    9: ("ЧТО СТОИТ ЗАПУСКАТЬ?", 7),
    10: ("ИЗ ИДЕИ В ПЛАН", 15),
}
TARGETS = {"Сентябрь": 552_500, "Октябрь": 571_950}
MOTIVES = [
    "Мне это нужно", "Там выгодно", "Интересно, что появилось", "Надо успеть",
    "Зайду по пути", "Мне рассказали", "Давно не был — посмотрю"
]
PROVOCATIONS = [
    "БЮДЖЕТ = 0",
    "ТОЛЬКО 500 МЕТРОВ",
    "У ТЕБЯ 3 СЕКУНДЫ",
    "ВЕРНИ ПОКУПАТЕЛЯ ЧЕРЕЗ 7 ДНЕЙ",
    "ПОКУПАТЕЛЬ ДОЛЖЕН ПРИВЕСТИ ЕЩЁ ОДНОГО",
    "КАЖДУЮ НЕДЕЛЮ МАГАЗИН ДОЛЖЕН УДИВЛЯТЬ",
    "ИСПОЛЬЗУЙ СЕНТЯБРЬ–ОКТЯБРЬ",
]

st.markdown("""
<style>
:root{--ink:#182136;--teal:#12a6a6;--bg:#f5f7fb;--card:#ffffff;--muted:#758096;--red:#ef6678;--green:#31a87c;--amber:#e9a328;--violet:#8f63d9}
.block-container{padding-top:1.2rem;padding-bottom:2rem;max-width:1500px}
body{background:var(--bg)}
.topline{height:7px;background:var(--teal);border-radius:99px;margin-bottom:18px}
.hero{font-size:2.25rem;font-weight:850;color:var(--ink);line-height:1.05;margin:0 0 6px}
.sub{color:var(--muted);font-size:1.05rem;margin-bottom:18px}
.stagebar{display:flex;gap:8px;overflow-x:auto;padding:4px 0 12px}
.stagepill{min-width:115px;padding:9px 10px;border:1px solid #dce3ef;border-radius:13px;background:#fff;color:var(--ink);font-size:.76rem;font-weight:750}
.stagepill.active{background:#e8fbfb;border-color:#82d7d7;color:#087a7a;box-shadow:0 6px 18px rgba(18,166,166,.12)}
.card{background:#fff;border:1px solid #e0e6ef;border-radius:16px;padding:16px;box-shadow:0 8px 26px rgba(24,33,54,.04);height:100%}
.kicker{font-size:.72rem;letter-spacing:.08em;font-weight:800;color:#0c8f8f;text-transform:uppercase}
.bigq{font-size:1.55rem;font-weight:850;line-height:1.18;color:var(--ink);margin:8px 0 14px}
.note{border-left:4px solid var(--teal);background:#f0fbfb;border-radius:10px;padding:12px 14px;color:#3b465b}
.warn{border-left-color:var(--red);background:#fff3f5}.success{border-left-color:var(--green);background:#f0faf6}
.sticky{border-radius:12px;padding:13px 14px;min-height:92px;border:1px solid rgba(0,0,0,.06);font-size:.92rem;box-shadow:0 5px 14px rgba(24,33,54,.06);margin-bottom:10px}
.yellow{background:#fff2a8}.green{background:#dff3c7}.pink{background:#ffd7dc}.purple{background:#eadbff}.blue{background:#d9f2ff}
.metric{font-size:2rem;font-weight:900;color:var(--ink)}
.small{font-size:.82rem;color:var(--muted)}
.syncbox{background:#fff;border:1px dashed #b9c7da;border-radius:12px;padding:9px 12px;color:#5f6c80;font-size:.82rem}
</style>
""", unsafe_allow_html=True)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    """Общее хранилище для всех пользователей одного процесса Streamlit.

    Не требует БД. Данные живут, пока приложение не перезапущено/не уснуло.
    Для защиты от потери есть экспорт/импорт JSON в панели ведущего.
    """
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
                },
                "participants": [],
                "cards": [],
                "votes": [],
                "action_plan": [],
                "next_card_id": 1,
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
            self.state = deepcopy(data)


@st.cache_resource
def get_store():
    return MemoryStore()


store = get_store()


def get_session():
    return store.snapshot()["session"]


def set_stage(stage):
    with store.lock:
        store.state["session"]["current_stage"] = int(stage)
        store.state["session"]["stage_started_at"] = utcnow()


def set_presentation_url(url):
    with store.lock:
        store.state["session"]["presentation_url"] = url.strip()


def add_or_touch_participant(token, name):
    with store.lock:
        for p in store.state["participants"]:
            if p["token"] == token:
                p["name"] = name
                p["last_seen"] = utcnow()
                return
        store.state["participants"].append({
            "session_code": SESSION_CODE, "name": name, "token": token, "last_seen": utcnow()
        })


def participants():
    return store.snapshot()["participants"]


def add_card(stage, body, lane=None, title=None, parent_id=None):
    if not body.strip():
        return
    with store.lock:
        cid = store.state["next_card_id"]
        store.state["next_card_id"] += 1
        store.state["cards"].append({
            "id": cid,
            "session_code": SESSION_CODE,
            "stage": int(stage),
            "author_token": st.session_state.get("token"),
            "author_name": st.session_state.get("name", ""),
            "lane": lane,
            "title": title,
            "body": body.strip(),
            "parent_id": parent_id,
            "cluster": None,
            "created_at": utcnow(),
        })


def get_cards(stage=None):
    cards = store.snapshot()["cards"]
    if stage is None:
        return cards
    return [c for c in cards if int(c.get("stage", 0)) == int(stage)]


def set_cluster(card_id, cluster):
    with store.lock:
        for c in store.state["cards"]:
            if c["id"] == card_id:
                c["cluster"] = cluster.strip()
                return


def get_votes():
    return store.snapshot()["votes"]


def add_vote(card_id, voter_token):
    with store.lock:
        votes = store.state["votes"]
        mine = [v for v in votes if v["voter_token"] == voter_token]
        if len(mine) >= 5:
            return False
        if any(v["voter_token"] == voter_token and v["card_id"] == card_id for v in votes):
            return False
        votes.append({"session_code": SESSION_CODE, "voter_token": voter_token, "card_id": card_id, "created_at": utcnow()})
        return True


def remove_vote(card_id, voter_token):
    with store.lock:
        store.state["votes"] = [
            v for v in store.state["votes"]
            if not (v["voter_token"] == voter_token and v["card_id"] == card_id)
        ]


def get_plans():
    return sorted(store.snapshot()["action_plan"], key=lambda x: x["rank"])


def upsert_plan(rank, payload):
    with store.lock:
        existing = next((p for p in store.state["action_plan"] if p["rank"] == rank), None)
        if existing:
            existing.update(payload)
        else:
            row = {"rank": rank, "session_code": SESSION_CODE}
            row.update(payload)
            store.state["action_plan"].append(row)


def rerun():
    st.rerun()


# ---------- lobby ----------
if "token" not in st.session_state:
    st.markdown('<div class="topline"></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.6, 1])
    with c1:
        st.markdown('<div class="hero">СТРАТЕГИЧЕСКАЯ СЕССИЯ · ТРАФИК ТРИ ЦЕНЫ</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub">Главный вопрос: что заставит человека, который иначе НЕ пришёл бы в ТРИ ЦЕНЫ, решить зайти в магазин?</div>', unsafe_allow_html=True)
        st.markdown('<div class="card"><div class="kicker">Наша цель</div><div class="bigq">Сформировать несколько инициатив, которые реально принесут дополнительный трафик в сентябре–октябре.</div><div class="note">Каждая идея должна отвечать на вопрос: почему из-за этого человек придёт в магазин?</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="card"><div class="kicker">Вход участника</div>', unsafe_allow_html=True)
        name = st.text_input("Имя", placeholder="Например, Анна")
        if st.button("Присоединиться", use_container_width=True, type="primary", disabled=not name.strip()):
            token = str(uuid.uuid4())
            st.session_state.token = token
            st.session_state.name = name.strip()
            add_or_touch_participant(token, name.strip())
            rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

add_or_touch_participant(st.session_state.token, st.session_state.name)

# ---------- header ----------
session = get_session()
current_stage = int(session["current_stage"])
st.markdown('<div class="topline"></div>', unsafe_allow_html=True)
left, right = st.columns([3, 1])
with left:
    st.markdown(f'<div class="hero">{session["title"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub">Участник: <b>{st.session_state.name}</b> · текущий этап {current_stage}/10</div>', unsafe_allow_html=True)
with right:
    admin_pin = st.text_input("PIN ведущего", type="password", key="admin_pin")
    try:
        configured_pin = st.secrets.get("ADMIN_PIN", "2026")
    except Exception:
        configured_pin = os.getenv("ADMIN_PIN", "2026")
    is_admin = bool(admin_pin) and admin_pin == configured_pin

pills = ''.join([
    f'<div class="stagepill {"active" if n == current_stage else ""}"><b>{n:02d}</b><br>{name}<br><span class="small">{mins} мин</span></div>'
    for n, (name, mins) in STAGES.items()
])
st.markdown(f'<div class="stagebar">{pills}</div>', unsafe_allow_html=True)

ppl = participants()
with st.expander(f"Участники · {len(ppl)}"):
    st.write(" · ".join(p["name"] for p in ppl) if ppl else "Пока никого")

controls = st.columns([1, 1, 1, 3])
with controls[0]:
    if st.button("↻ Синхронизировать", use_container_width=True):
        rerun()
if is_admin:
    with controls[1]:
        if st.button("← Этап", disabled=current_stage <= 1, use_container_width=True):
            set_stage(current_stage - 1); rerun()
    with controls[2]:
        if st.button("Следующий →", disabled=current_stage >= 10, type="primary", use_container_width=True):
            set_stage(current_stage + 1); rerun()

if is_admin:
    with st.expander("⚙️ Панель ведущего · резервная копия"):
        st.caption("База данных не используется. Данные общие для участников, пока приложение запущено. На случай перезапуска можно скачать резервную копию JSON и восстановить её здесь.")
        backup = json.dumps(store.snapshot(), ensure_ascii=False, indent=2).encode("utf-8")
        b1, b2, b3 = st.columns([1.1, 1.4, 1])
        with b1:
            st.download_button("Скачать резервную копию", backup, file_name="strategy_board_backup.json", mime="application/json", use_container_width=True)
        with b2:
            upload = st.file_uploader("Восстановить из JSON", type=["json"], label_visibility="collapsed")
            if upload is not None and st.button("Восстановить", use_container_width=True):
                try:
                    store.restore(json.load(upload))
                    st.success("Доска восстановлена.")
                    rerun()
                except Exception as exc:
                    st.error(f"Не удалось восстановить: {exc}")
        with b3:
            if st.button("Очистить доску", use_container_width=True):
                store.reset()
                add_or_touch_participant(st.session_state.token, st.session_state.name)
                rerun()

st.markdown('<div class="syncbox">Совместная работа без SQL: после добавления карточки она сразу хранится в общей памяти приложения. Чтобы увидеть изменения коллег без собственного действия, нажмите <b>↻ Синхронизировать</b>.</div>', unsafe_allow_html=True)
st.markdown("---")


def card_list(cards, color="yellow", show_author=True):
    if not cards:
        st.caption("Пока пусто — добавьте первую карточку.")
        return
    cols = st.columns(4)
    for i, item in enumerate(cards):
        with cols[i % 4]:
            author = f'<div class="small">{item.get("author_name") or ""}</div>' if show_author else ""
            st.markdown(f'<div class="sticky {color}">{item["body"]}{author}</div>', unsafe_allow_html=True)


if current_stage == 1:
    st.markdown('<div class="kicker">01 · старт · 10 минут</div><div class="bigq">Почему человек может зайти в ТРИ ЦЕНЫ в сентябре–октябре?</div>', unsafe_allow_html=True)
    st.info("Пока не придумываем рекламу, акции и механики. Думаем только о причине визита. Одна карточка = одна мысль.")
    with st.form("s1"):
        body = st.text_area("Моя причина визита", placeholder="Например: похолодало, нужно быстро докупить вещи для дома…")
        if st.form_submit_button("Добавить стикер", type="primary") and body.strip():
            add_card(1, body); rerun()
    card_list(get_cards(1), "yellow")
    st.caption("Подсказки: " + " · ".join(MOTIVES))

elif current_stage == 2:
    st.markdown('<div class="kicker">02 · исходная ситуация · 14 минут</div><div class="bigq">Презентация Дениса</div>', unsafe_allow_html=True)
    url = session.get("presentation_url", "")
    if is_admin:
        new_url = st.text_input("Ссылка на презентацию", value=url, placeholder="https://...")
        if st.button("Сохранить ссылку"):
            set_presentation_url(new_url); rerun()
    if url:
        st.link_button("▶ Открыть презентацию", url, use_container_width=True)
    else:
        st.info("Ведущий может вставить ссылку на презентацию прямо на этом экране.")
    st.markdown('<div class="note">Цифры показали, <b>ГДЕ</b> проблема. Теперь нам нужно ответить, <b>КАК</b> привести дополнительный трафик.</div>', unsafe_allow_html=True)

elif current_stage == 3:
    st.markdown('<div class="kicker">03 · карта причин · 10 минут</div><div class="bigq">Какие причины посещения мы недоиспользуем?</div>', unsafe_allow_html=True)
    lanes = [("Уже хорошо используем", "green"), ("Можем использовать сильнее", "yellow"), ("Почти не используем", "pink")]
    cols = st.columns(3)
    all_cards = get_cards(3)
    for idx, (lane, color) in enumerate(lanes):
        with cols[idx]:
            st.subheader(lane)
            with st.form(f"s3_{idx}"):
                body = st.text_area("Причина", key=f"reason_{idx}")
                if st.form_submit_button("Добавить") and body.strip():
                    add_card(3, body, lane=lane); rerun()
            card_list([c for c in all_cards if c.get("lane") == lane], color)

elif current_stage == 4:
    st.markdown('<div class="kicker">04 · тихая генерация · 22 минуты</div><div class="bigq">Генерируем трафиковые гипотезы</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    for col, lane, color, prompt in [
        (c1, "Новые клиенты", "blue", "Что заставит человека, который сейчас НЕ ходит в ТРИ ЦЕНЫ, прийти?"),
        (c2, "Текущая база", "purple", "Что заставит существующего покупателя прийти ЧАЩЕ?")
    ]:
        with col:
            st.subheader(lane)
            st.caption(prompt)
            with st.form(f"s4_{lane}"):
                what = st.text_input("Что делаем", key=f"what_{lane}")
                why = st.text_input("Почему из-за этого человек придёт", key=f"why_{lane}")
                if st.form_submit_button("Добавить идею") and what.strip() and why.strip():
                    add_card(4, f"{what.strip()} → {why.strip()}", lane=lane); rerun()
            card_list([c for c in get_cards(4) if c.get("lane") == lane], color)

elif current_stage == 5:
    st.markdown('<div class="kicker">05 · вторая волна · 8 минут</div><div class="bigq">Не придумывай новую идею. Усиль чужую.</div>', unsafe_allow_html=True)
    source = get_cards(4)
    options = {f'#{c["id"]} · {c["body"][:85]}': c["id"] for c in source}
    if options:
        selected = st.selectbox("Выбери идею коллеги", list(options.keys()))
        with st.form("s5"):
            body = st.text_area("Моя усиленная версия", placeholder="А если сделать локально / каждую неделю / без скидки / через фасад / через Digital…")
            if st.form_submit_button("Добавить развитие", type="primary") and body.strip():
                add_card(5, body, parent_id=options[selected]); rerun()
    card_list(get_cards(5), "purple")

elif current_stage == 6:
    st.markdown('<div class="kicker">06 · лаборатория идей · 23 минуты</div><div class="bigq">Разворачиваем сильную идею в механику</div>', unsafe_allow_html=True)
    with st.form("s6"):
        idea = st.text_input("Что делаем?")
        audience = st.text_input("Для кого?")
        why = st.text_input("Почему человек придёт?")
        stronger = st.text_input("Как сделать повод сильнее?")
        regular = st.text_input("Как сделать механику регулярной?")
        before = st.text_input("Как человек узнает об этом ДО визита?")
        measure = st.text_input("Как измерим дополнительный визит?")
        if st.form_submit_button("Сохранить карточку", type="primary") and idea.strip():
            body = f"Что: {idea} | Для кого: {audience} | Почему придёт: {why} | Усиление: {stronger} | Регулярность: {regular} | До визита: {before} | Измерение: {measure}"
            add_card(6, body, title=idea); rerun()
    card_list(get_cards(6), "blue")

elif current_stage == 7:
    st.markdown('<div class="kicker">07 · провокации · 15 минут</div><div class="bigq">Ломаем привычную логику</div>', unsafe_allow_html=True)
    prov = st.radio("Провокация", PROVOCATIONS, horizontal=True)
    st.markdown(f'<div class="note warn"><b>{prov}</b><br>Придумайте хотя бы один новый ход. Сейчас не оцениваем реалистичность.</div>', unsafe_allow_html=True)
    with st.form("s7"):
        body = st.text_area("Идея из провокации")
        if st.form_submit_button("Добавить") and body.strip():
            add_card(7, body, lane=prov); rerun()
    card_list(get_cards(7), "pink")

elif current_stage == 8:
    st.markdown('<div class="kicker">08 · кластеризация · 12 минут</div><div class="bigq">50 идей → 5–8 направлений</div>', unsafe_allow_html=True)
    source = get_cards(4) + get_cards(5) + get_cards(6) + get_cards(7)
    if is_admin and source:
        option_map = {f'#{c["id"]} · {c["body"][:90]}': c["id"] for c in source}
        selected = st.selectbox("Карточка", list(option_map.keys()))
        cluster = st.text_input("Название направления")
        if st.button("Назначить кластер") and cluster.strip():
            set_cluster(option_map[selected], cluster); rerun()
    clustered = [c for c in source if c.get("cluster")]
    if clustered:
        df = pd.DataFrame(clustered)[["cluster", "body", "author_name"]].sort_values("cluster")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Ведущий группирует карточки и даёт названия направлениям.")

elif current_stage == 9:
    st.markdown('<div class="kicker">09 · приоритизация · 7 минут</div><div class="bigq">Что действительно стоит запускать?</div>', unsafe_allow_html=True)
    candidates = [c for c in get_cards() if c.get("cluster")]
    if not candidates:
        candidates = get_cards(6)
    votes = get_votes()
    mine = {v["card_id"] for v in votes if v["voter_token"] == st.session_state.token}
    st.write(f"Ваши голоса: **{len(mine)}/5**")
    for c in candidates:
        count = sum(1 for v in votes if v["card_id"] == c["id"])
        with st.container(border=True):
            st.write(f'**#{c["id"]}** {c.get("title") or c["body"][:180]}')
            st.caption(f'Направление: {c.get("cluster") or "—"} · голосов: {count}')
            if c["id"] in mine:
                if st.button("Снять голос", key=f"unvote_{c['id']}"):
                    remove_vote(c["id"], st.session_state.token); rerun()
            elif len(mine) < 5:
                if st.button("Голосовать", key=f"vote_{c['id']}"):
                    add_vote(c["id"], st.session_state.token); rerun()
    votes = get_votes()
    ranking = []
    for c in candidates:
        ranking.append((sum(1 for v in votes if v["card_id"] == c["id"]), c))
    ranking.sort(key=lambda x: x[0], reverse=True)
    st.subheader("TOP-8")
    for i, (count, c) in enumerate(ranking[:8], 1):
        st.write(f"{i}. **{count} голосов** — {c.get('title') or c['body'][:130]}")

elif current_stage == 10:
    st.markdown('<div class="kicker">10 · из идеи в план · 15 минут</div><div class="bigq">TOP-3 → ответственный → срок → эффект</div>', unsafe_allow_html=True)
    votes = get_votes()
    counts = {}
    for v in votes:
        counts[v["card_id"]] = counts.get(v["card_id"], 0) + 1
    cards = {c["id"]: c for c in get_cards()}
    top_ids = [cid for cid, _ in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:3] if cid in cards]
    plans = get_plans()
    by_rank = {p["rank"]: p for p in plans}

    for rank in range(1, 4):
        default = ""
        if len(top_ids) >= rank:
            c = cards[top_ids[rank - 1]]
            default = c.get("title") or c["body"][:120]
        e = by_rank.get(rank, {})
        with st.expander(f"Инициатива {rank}", expanded=True):
            with st.form(f"plan_{rank}"):
                initiative = st.text_input("Что запускаем", value=e.get("initiative") or default)
                audience = st.text_input("Для кого", value=e.get("audience") or "")
                reason = st.text_input("Почему придёт", value=e.get("reason") or "")
                channel = st.text_input("Канал / как узнает", value=e.get("channel") or "")
                start_date = st.text_input("Старт / срок", value=e.get("start_date") or "")
                extra = st.number_input("Ожидаемый дополнительный трафик", min_value=0, value=int(e.get("extra_traffic") or 0), step=100)
                budget = st.text_input("Бюджет", value=e.get("budget") or "")
                owner = st.text_input("Ответственный", value=e.get("owner") or "")
                measurement = st.text_input("Как измеряем", value=e.get("measurement") or "")
                review = st.text_input("Дата первой проверки", value=e.get("review_date") or "")
                if st.form_submit_button("Сохранить"):
                    upsert_plan(rank, {
                        "initiative": initiative, "audience": audience, "reason": reason, "channel": channel,
                        "start_date": start_date, "extra_traffic": int(extra), "budget": budget, "owner": owner,
                        "measurement": measurement, "review_date": review, "updated_at": utcnow()
                    })
                    rerun()

    plans = get_plans()
    total = sum(int(p.get("extra_traffic") or 0) for p in plans)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Целевой трафик · Сентябрь", f"{TARGETS['Сентябрь']:,}".replace(",", " "))
    with c2:
        st.metric("Целевой трафик · Октябрь", f"{TARGETS['Октябрь']:,}".replace(",", " "))
    with c3:
        st.metric("Доп. трафик TOP-3", f"+{total:,}".replace(",", " "))

    cards_df = pd.DataFrame(get_cards())
    votes_df = pd.DataFrame(get_votes())
    plans_df = pd.DataFrame(plans)
    csv_parts = []
    if not cards_df.empty:
        csv_parts.append("КАРТОЧКИ\n" + cards_df.to_csv(index=False))
    if not votes_df.empty:
        csv_parts.append("\nГОЛОСА\n" + votes_df.to_csv(index=False))
    if not plans_df.empty:
        csv_parts.append("\nПЛАН\n" + plans_df.to_csv(index=False))
    st.download_button(
        "Скачать протокол CSV",
        "\n".join(csv_parts).encode("utf-8-sig"),
        file_name="strategy_session_protocol.csv",
        mime="text/csv",
    )

st.markdown("---")
st.caption("Наша цель: сформировать инициативы, которые приведут дополнительного человека в ТРИ ЦЕНЫ — и измерить результат.")
