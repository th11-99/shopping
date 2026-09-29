from __future__ import annotations

import html
import json
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

DATA_FILE = Path(__file__).parent / "shopping_list.json"
MAX_NAME_LEN = 50


# ---------- 데이터 저장 ----------

def load_items() -> tuple[list, bool]:
    """JSON 파일에서 목록을 불러온다. (items, 손상 여부)를 반환한다."""
    if not DATA_FILE.exists():
        return [], False
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("list가 아님")
        return data, False
    except (json.JSONDecodeError, ValueError, OSError):
        try:
            DATA_FILE.replace(DATA_FILE.with_name(DATA_FILE.name + ".bak"))
        except OSError:
            pass
        return [], True


def save_items(items: list) -> None:
    """목록 전체를 JSON 파일에 저장한다."""
    DATA_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def new_item(name: str, quantity: int = 1) -> dict:
    return {
        "id": uuid.uuid4().hex[:8],
        "name": name,
        "quantity": int(quantity),
        "checked": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


# ---------- 상태 ----------

def refresh_items() -> None:
    """파일에서 최신 목록을 다시 읽는다.

    탭마다 session_state가 따로 있으므로, 변경 직전과 매 렌더링마다 다시 읽어야
    다른 탭의 변경을 덮어쓰지 않는다.
    """
    items, corrupted = load_items()
    st.session_state["items"] = items
    if corrupted:
        st.session_state["load_error"] = True


def init_state() -> None:
    st.session_state.setdefault("load_error", False)
    st.session_state.setdefault("editing_id", None)
    refresh_items()
    if _find(st.session_state["editing_id"]) is None:
        st.session_state["editing_id"] = None


# ---------- 추가·수정·삭제 ----------

def _find(item_id: str | None) -> dict | None:
    return next((i for i in st.session_state["items"] if i["id"] == item_id), None)


def _commit() -> None:
    save_items(st.session_state["items"])
    st.session_state["load_error"] = False


def flash(message: str, level: str = "warning") -> None:
    """콜백 안에서는 st.warning이 보이지 않으므로 다음 렌더링 때 표시한다."""
    st.session_state["flash"] = (level, message)


def validate_name(name: str) -> str | None:
    """이름이 올바르지 않으면 오류 메시지를, 올바르면 None을 반환한다."""
    if not name:
        return "아이템 이름을 입력해주세요."
    if len(name) > MAX_NAME_LEN:
        return f"아이템 이름은 {MAX_NAME_LEN}자 이하로 입력해주세요. (현재 {len(name)}자)"
    return None


def add_item(name: str, quantity: int) -> str | None:
    """아이템을 목록 끝에 추가한다. 실패하면 오류 메시지를 반환한다."""
    name = (name or "").strip()
    if error := validate_name(name):
        return error
    refresh_items()
    st.session_state["items"].append(new_item(name, quantity))
    _commit()
    return None


def update_item(item_id: str, name: str, quantity: int) -> str | None:
    """아이템의 이름과 수량을 수정한다. 실패하면 오류 메시지를 반환한다."""
    name = (name or "").strip()
    if error := validate_name(name):
        return error
    refresh_items()
    item = _find(item_id)
    st.session_state["editing_id"] = None
    if item is None:
        return "다른 곳에서 삭제된 아이템입니다."
    item["name"] = name
    item["quantity"] = int(quantity)
    _commit()
    return None


def delete_item(item_id: str) -> None:
    """아이템을 삭제한다."""
    refresh_items()
    st.session_state["items"] = [i for i in st.session_state["items"] if i["id"] != item_id]
    if st.session_state["editing_id"] == item_id:
        st.session_state["editing_id"] = None
    _commit()


def toggle_item(item_id: str) -> None:
    """아이템의 체크 상태를 반전한다."""
    refresh_items()
    item = _find(item_id)
    if item is not None:
        item["checked"] = st.session_state[f"chk_{item_id}"]
        _commit()


def clear_checked() -> None:
    """체크된 아이템을 모두 삭제한다."""
    refresh_items()
    items = st.session_state["items"]
    removed = {i["id"] for i in items if i["checked"]}
    st.session_state["items"] = [i for i in items if not i["checked"]]
    if st.session_state["editing_id"] in removed:
        st.session_state["editing_id"] = None
    _commit()


# ---------- 콜백 ----------

def on_add() -> None:
    if error := add_item(st.session_state["new_name"], st.session_state["new_qty"]):
        flash(error)


def on_start_edit(item_id: str) -> None:
    item = _find(item_id)
    if item is None:
        return
    st.session_state["editing_id"] = item_id
    st.session_state[f"edit_name_{item_id}"] = item["name"]
    st.session_state[f"edit_qty_{item_id}"] = item["quantity"]


def on_save_edit(item_id: str) -> None:
    name = st.session_state[f"edit_name_{item_id}"]
    qty = st.session_state[f"edit_qty_{item_id}"]
    if error := update_item(item_id, name, qty):
        flash(error)


def on_cancel_edit() -> None:
    st.session_state["editing_id"] = None


# ---------- 화면 ----------

CSS = """
<style>
:root {
    --accent: #2e9e6b;
    --row-bg: rgba(128, 128, 128, 0.07);
    --row-border: rgba(128, 128, 128, 0.18);
    --badge-bg: rgba(46, 158, 107, 0.14);
    --muted: rgba(128, 128, 128, 0.9);
}
[data-testid="stMainBlockContainer"] { max-width: 640px; padding-top: 3rem; }
h1 { padding-bottom: 0.25rem; }

/* 입력 영역 카드 */
.st-key-add_area {
    background: var(--row-bg);
    border: 1px solid var(--row-border);
    border-radius: 14px;
    padding: 12px;
}

/* 목록 행 */
[class*="st-key-row_"] {
    background: var(--row-bg);
    border: 1px solid transparent;
    border-radius: 12px;
    padding: 4px 6px 4px 12px;
    min-height: 48px;
}
[class*="st-key-row_edit_"] {
    border: 1.5px solid var(--accent);
    padding: 10px 12px;
}
/* 모바일에서 이름이 길어도 버튼이 다음 줄로 밀리지 않게: 이름 칸만 줄어들고 줄바꿈된다 */
[class*="st-key-row_todo_"], [class*="st-key-row_done_"] { flex-wrap: nowrap; }
[class*="st-key-row_"] [data-testid="stElementContainer"]:has(.item-name) {
    flex: 1 1 0;
    min-width: 0;
}
/* Streamlit 기본 음수 여백(-16px) 때문에 이름이 체크박스보다 아래로 처지는 것을 막는다 */
[class*="st-key-row_"] [data-testid="stMarkdownContainer"]:has(.item-name) { margin-bottom: 0; }
.item-name { line-height: 1.4; word-break: break-word; }
.item-name.done { text-decoration: line-through; color: var(--muted); opacity: 0.6; }
.qty {
    display: inline-block;
    margin-left: 6px;
    padding: 1px 8px;
    border-radius: 999px;
    background: var(--badge-bg);
    color: var(--accent);
    font-size: 0.8rem;
    font-weight: 600;
    white-space: nowrap;
}
.item-name.done .qty { background: var(--row-bg); color: var(--muted); }

/* 빈 상태 */
.empty {
    text-align: center;
    padding: 2.5rem 1rem;
    border: 1.5px dashed var(--row-border);
    border-radius: 14px;
    color: var(--muted);
}
.empty .icon { font-size: 2.5rem; }
.empty .title { font-weight: 600; margin-top: 0.5rem; }
.empty .hint { font-size: 0.9rem; }
</style>
"""


def render_summary(total: int, done: int) -> None:
    with st.container(horizontal=True, key="summary"):
        st.metric("전체", f"{total}개", border=True)
        st.metric("완료", f"{done}개", border=True)
        st.metric("남은", f"{total - done}개", border=True)
    st.progress(done / total if total else 0.0,
                text=f"전체 {total}개 · 완료 {done}개 · 남은 {total - done}개")


def render_add_form() -> None:
    with st.form("add_form", clear_on_submit=True, border=False):
        with st.container(key="add_area", horizontal=True, vertical_alignment="bottom"):
            st.text_input("아이템 이름", key="new_name",
                          placeholder="예: 우유, 계란, 사과", width="stretch")
            st.number_input("수량", key="new_qty", min_value=1, max_value=999,
                            value=1, step=1, width=96)
            st.form_submit_button("추가", on_click=on_add, type="primary", icon=":material/add:")


def render_row(item: dict) -> None:
    item_id = item["id"]
    if st.session_state["editing_id"] == item_id:
        with st.container(key=f"row_edit_{item_id}", horizontal=True, vertical_alignment="bottom"):
            st.text_input("이름", key=f"edit_name_{item_id}", width="stretch")
            st.number_input("수량", key=f"edit_qty_{item_id}", min_value=1, max_value=999,
                            step=1, width=96)
            st.button("저장", key=f"save_{item_id}", on_click=on_save_edit,
                      args=(item_id,), type="primary")
            st.button("취소", key=f"cancel_{item_id}", on_click=on_cancel_edit)
        return

    state = "done" if item["checked"] else "todo"
    # 다른 탭에서 바뀐 체크 상태가 이전 위젯 값에 가려지지 않도록 매번 맞춰준다
    st.session_state[f"chk_{item_id}"] = item["checked"]
    with st.container(key=f"row_{state}_{item_id}", horizontal=True,
                      vertical_alignment="center", gap="small"):
        st.checkbox("완료", key=f"chk_{item_id}", on_change=toggle_item,
                    args=(item_id,), label_visibility="collapsed", width="content")
        st.markdown(
            f'<div class="item-name {state}">{html.escape(item["name"])}'
            f'<span class="qty">x{item["quantity"]}</span></div>',
            unsafe_allow_html=True, width="stretch",
        )
        st.button("✏️", key=f"edit_{item_id}", on_click=on_start_edit, args=(item_id,),
                  help="수정", type="tertiary")
        st.button("🗑️", key=f"del_{item_id}", on_click=delete_item, args=(item_id,),
                  help="삭제", type="tertiary")


def render_empty() -> None:
    st.markdown(
        '<div class="empty"><div class="icon">🧺</div>'
        '<div class="title">쇼핑리스트가 비어 있습니다</div>'
        '<div class="hint">위에서 아이템을 추가해보세요</div></div>',
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="쇼핑리스트", page_icon="🛒")
    st.markdown(CSS, unsafe_allow_html=True)
    init_state()
    items = st.session_state["items"]
    done = sum(i["checked"] for i in items)

    st.title("🛒 쇼핑리스트", anchor=False)
    if st.session_state.get("load_error"):
        st.warning("저장 파일을 읽을 수 없어 빈 목록으로 시작합니다. "
                   "손상된 파일은 shopping_list.json.bak으로 보관했습니다.")
    render_summary(len(items), done)

    render_add_form()
    if flash_msg := st.session_state.pop("flash", None):
        getattr(st, flash_msg[0])(flash_msg[1])

    if not items:
        render_empty()
        return
    with st.container(key="item_list", gap="small"):
        for item in items:
            render_row(item)

    with st.container(horizontal=True, horizontal_alignment="right"):
        st.button("완료 항목 삭제", on_click=clear_checked, disabled=done == 0,
                  icon=":material/delete_sweep:")


main()
