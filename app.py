import streamlit as st
import pandas as pd
import os
import json
import random
import hashlib
import gspread
from google.oauth2.service_account import Credentials

# --- 页面配置与极简 UI 样式注入 ---
st.set_page_config(page_title="😅", layout="centered")
# st.markdown("""
# <style>
#     /* 隐藏顶部默认菜单和底部水印 */
#     #MainMenu {visibility: hidden;}
#     footer {visibility: hidden;}
#     header {visibility: hidden;}
#     /* 优化单选框的间距 */
#     .stRadio > div {gap: 0.5rem;}
#     /* 弱化分割线 */
#     hr {margin-top: 1rem; margin-bottom: 1rem; border-top: 1px solid #f0f2f6;}
# </style>
# """, unsafe_allow_html=True)
st.markdown("""
<style>
    /* 隐藏右上角默认菜单，但保留整个 header 以显示手机端侧边栏按钮 */
    #MainMenu {visibility: hidden;}
    
    /* 强制隐藏底部 Streamlit 水印和广告 */
    footer {display: none !important;}
    
    /* 隐藏右上角的 Deploy 按钮 (如果有) */
    .stAppDeployButton {display: none;}
    
    /* 优化单选框的间距 */
    .stRadio > div {gap: 0.5rem;}
    /* 弱化分割线 */
    hr {margin-top: 1rem; margin-bottom: 1rem; border-top: 1px solid #f0f2f6;}
</style>
""", unsafe_allow_html=True)

# --- 网络代理与云数据库配置 ---
proxy_url = "http://127.0.0.1:7890"
os.environ["http_proxy"] = proxy_url
os.environ["https_proxy"] = proxy_url
os.environ["HTTP_PROXY"] = proxy_url
os.environ["HTTPS_PROXY"] = proxy_url

SPREADSHEET_NAME = "abc-error"
CREDENTIALS_FILE = "google_credentials.json"

# @st.cache_resource
# def init_gsheets():
#     try:
#         scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
#         creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
#         client = gspread.authorize(creds)
#         return client.open(SPREADSHEET_NAME).worksheet('Mistakes')
#     except Exception as e:
#         st.error(f"系统连接异常: {e}")
#         return None

@st.cache_resource
def init_gsheets():
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        
        # 优先尝试从 Streamlit 环境变量中读取密钥（用于云端部署）
        if "GOOGLE_CREDS" in st.secrets:
            creds_dict = json.loads(st.secrets["GOOGLE_CREDS"])
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        # 如果没有环境变量，则从本地文件读取（用于本地测试）
        else:
            creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
            
        client = gspread.authorize(creds)
        return client.open(SPREADSHEET_NAME).worksheet('Mistakes')
    except Exception as e:
        st.error(f"系统连接异常: {e}")
        return None

sheet = init_gsheets()

# --- 严谨的序列化存取逻辑 (使用题干 MD5 和 JSON) ---
def load_user_mistakes(username):
    if sheet:
        records = sheet.get_all_records()
        for row in records:
            if str(row.get('Username')) == username:
                raw_data = str(row.get('MistakesList', '[]'))
                try:
                    return set(json.loads(raw_data)) # 反序列化为集合
                except json.JSONDecodeError:
                    return set()
    return set()

def save_user_mistakes(username, mistakes_set):
    if sheet:
        mistakes_str = json.dumps(list(mistakes_set)) # 严格序列化为 JSON 文本
        records = sheet.get_all_records()
        row_idx = None
        for i, row in enumerate(records):
            if str(row.get('Username')) == username:
                row_idx = i + 2
                break
        if row_idx:
            sheet.update_cell(row_idx, 2, mistakes_str)
        else:
            sheet.append_row([username, mistakes_str])

# # --- 身份认证 ---
# if 'username' not in st.session_state:
#     st.session_state.username = None

# if not st.session_state.username:
#     st.subheader("Study!--by micoco")
#     with st.form("login"):
#         user_input = st.text_input("姓名")
#         if st.form_submit_button("login") and user_input.strip():
#             st.session_state.username = user_input.strip()
#             st.session_state.mistakes = load_user_mistakes(st.session_state.username)
#             st.rerun()
#     st.stop()

# if 'mistakes' not in st.session_state:
#     st.session_state.mistakes = load_user_mistakes(st.session_state.username)

# --- 身份认证 ---
# 👇 在这里填入你们 6 个人的真实姓名或工号
ALLOWED_USERS = ["micoco", "向欣怡", "牟正鑫", "吕昊霖", "李佳龙", "李小翔"] 

if 'username' not in st.session_state:
    st.session_state.username = None

if not st.session_state.username:
    st.subheader("😅")
    with st.form("login"):
        user_input = st.text_input("姓名")
        if st.form_submit_button("登录系统"):
            input_name = user_input.strip()
            if not input_name:
                st.warning("请输入姓名")
            elif input_name in ALLOWED_USERS:
                st.session_state.username = input_name
                st.session_state.mistakes = load_user_mistakes(st.session_state.username)
                st.rerun()
            else:
                st.error("未授权的用户，请联系管理员")
    st.stop()

if 'mistakes' not in st.session_state:
    st.session_state.mistakes = load_user_mistakes(st.session_state.username)
# -----------------------------

# --- 侧边栏导航 ---
st.sidebar.markdown(f"**用户:** {st.session_state.username}")
if st.sidebar.button("退出", use_container_width=True):
    st.session_state.username = None
    st.rerun()
st.sidebar.divider()
mode = st.sidebar.radio("系统功能", ["练习模式", "模拟考试", "错题本"], label_visibility="collapsed")

# --- 题库加载与 MD5 唯一标识生成 ---
@st.cache_data
def load_data():
    file1, file2 = "Q1.xlsx", "Q2.xlsx"
    if not os.path.exists(file1) or not os.path.exists(file2):
        st.error("题库文件缺失")
        return pd.DataFrame()
    try:
        df1 = pd.read_excel(file1).rename(columns={"试题题干(必填)": "题干", "试题类型(必填，题型请用下拉菜单实现）": "题型", "选项（用'|'隔开）": "选项", "答案（填空题用'|'隔开）(必填)": "答案", "试题解析": "解析"})
        df2 = pd.read_excel(file2).rename(columns={"试题题干": "题干", "试题类型": "题型", "选项（用'|'隔开）": "选项", "答案": "答案"})
        df2['解析'] = '无'
        df = pd.concat([df1[['题干', '题型', '选项', '答案', '解析']], df2[['题干', '题型', '选项', '答案', '解析']]], ignore_index=True).dropna(subset=['题干', '题型', '答案'])
        df['题型'] = df['题型'].str.strip()
        # 核心：生成题干的 MD5 作为题目绝对唯一标识
        df['题ID'] = df['题干'].apply(lambda x: hashlib.md5(str(x).encode('utf-8')).hexdigest())
        return df.set_index('题ID') # 将哈希值设为索引
    except:
        return pd.DataFrame()

df = load_data()
if df.empty: st.stop()

# --- 辅助函数 ---
def handle_mistake(q_id, action="add"):
    if action == "add" and q_id not in st.session_state.mistakes:
        st.session_state.mistakes.add(q_id)
        save_user_mistakes(st.session_state.username, st.session_state.mistakes)
    elif action == "remove" and q_id in st.session_state.mistakes:
        st.session_state.mistakes.remove(q_id)
        save_user_mistakes(st.session_state.username, st.session_state.mistakes)

def parse_opts(o_str, q_type):
    if q_type == "判断" or pd.isna(o_str): return ["正确", "错误"]
    return [o.strip() for o in str(o_str).split('|') if o.strip()]

# ================= 主体功能 =================

if mode == "练习模式":
    p_type = st.radio("题型分类", ["单选", "多选", "判断", "混合抽取"], horizontal=True, label_visibility="collapsed")
    st.write("---")

    def pick_q(t):
        pool = df if t == "混合抽取" else df[df['题型'] == t]
        st.session_state.cur_q = pool.sample(1).iloc[0]
        st.session_state.ans_status = False
        st.session_state.qk = f"q_{random.randint(1, 99999)}"

    if st.session_state.get('prev_t') != p_type or 'cur_q' not in st.session_state:
        st.session_state.prev_t = p_type
        pick_q(p_type)

    q = st.session_state.cur_q
    opts = parse_opts(q['选项'], q['题型'])
    st.markdown(f"**[{q['题型']}] {q['题干']}**")
    
    if not st.session_state.ans_status:
        user_a = ""
        if q['题型'] in ["单选", "判断"]:
            labels = [f"{chr(65+i)}. {o}" for i, o in enumerate(opts)] if q['题型'] == "单选" else opts
            sel = st.radio(" ", labels, index=None, key=st.session_state.qk, label_visibility="collapsed")
            if sel: user_a = sel if q['题型'] == "判断" else chr(65 + labels.index(sel))
        else:
            selected = [chr(65+i) for i, o in enumerate(opts) if st.checkbox(f"{chr(65+i)}. {o}", key=f"{st.session_state.qk}_{i}")]
            user_a = "".join(selected)

        if st.button("提交", type="primary"):
            if not user_a: st.warning("请选择答案")
            else:
                st.session_state.user_a = user_a
                st.session_state.ans_status = True
                st.rerun()
    else:
        u_ans = "".join(sorted(str(st.session_state.user_a).strip().upper()))
        r_ans = "".join(sorted(str(q['答案']).strip().upper()))
        is_right = (u_ans == r_ans)

        if q['题型'] in ["单选", "判断"]:
            labels = [f"{chr(65+i)}. {o}" for i, o in enumerate(opts)] if q['题型'] == "单选" else opts
            for i, lb in enumerate(labels):
                lt = lb if q['题型'] == "判断" else chr(65+i)
                if lt in r_ans: st.markdown(f"✅ <span style='color:#2e7d32; font-weight:bold;'>{lb}</span>", unsafe_allow_html=True)
                elif lt in u_ans and not is_right: st.markdown(f"❌ <span style='color:#c62828; text-decoration:line-through;'>{lb}</span>", unsafe_allow_html=True)
                else: st.write(lb)
        else:
            for i, o in enumerate(opts):
                lt = chr(65+i)
                lb = f"{lt}. {o}"
                if lt in r_ans: st.markdown(f"✅ <span style='color:#2e7d32; font-weight:bold;'>{lb}</span>", unsafe_allow_html=True)
                elif lt in u_ans and lt not in r_ans: st.markdown(f"❌ <span style='color:#c62828; text-decoration:line-through;'>{lb}</span>", unsafe_allow_html=True)
                else: st.write(lb)

        if is_right:
            st.success("回答正确")
        else:
            st.error(f"标准答案: {r_ans}")
            handle_mistake(q.name, "add")
            
        if pd.notna(q['解析']) and q['解析'] != '无': st.info(f"解析: {q['解析']}")

        if st.button("下一题", type="primary"):
            pick_q(p_type)
            st.rerun()

elif mode == "模拟考试":
    st.subheader("模拟考试")
    st.caption("限时 60 分钟 | 单选70 / 多选50 / 判断70")
    if st.button("生成试卷"):
        paper = pd.concat([
            df[df['题型'] == '单选'].sample(min(70, len(df[df['题型'] == '单选']))),
            df[df['题型'] == '多选'].sample(min(50, len(df[df['题型'] == '多选']))),
            df[df['题型'] == '判断'].sample(min(70, len(df[df['题型'] == '判断'])))
        ]).sample(frac=1)
        st.session_state.paper = paper
        st.session_state.submitted = False

    if 'paper' in st.session_state:
        with st.form("exam"):
            for i, (q_id, row) in enumerate(st.session_state.paper.iterrows()):
                st.markdown(f"**{i+1}. [{row['题型']}] {row['题干']}**")
                opts = parse_opts(row['选项'], row['题型'])
                if row['题型'] in ["单选", "判断"]:
                    labels = [f"{chr(65+j)}. {o}" for j, o in enumerate(opts)] if row['题型'] == "单选" else opts
                    st.radio(" ", labels, index=None, key=f"er_{i}", label_visibility="collapsed")
                else:
                    for j, o in enumerate(opts): st.checkbox(f"{chr(65+j)}. {o}", key=f"ec_{i}_{j}")
                st.write("---")
            if st.form_submit_button("交卷"): st.session_state.submitted = True
                
        if st.session_state.submitted:
            score = 0
            for i, (q_id, row) in enumerate(st.session_state.paper.iterrows()):
                u_a = ""
                if row['题型'] in ["单选", "判断"]:
                     sel = st.session_state.get(f"er_{i}")
                     if sel: u_a = sel if row['题型'] == "判断" else sel[0]
                else:
                     u_a = "".join([chr(65+j) for j in range(len(parse_opts(row['选项'], row['题型']))) if st.session_state.get(f"ec_{i}_{j}")])
                
                if "".join(sorted(u_a.strip().upper())) == "".join(sorted(str(row['答案']).strip().upper())) and u_a != "":
                    score += 1
                else:
                    handle_mistake(q_id, "add")
            st.success(f"考试结束，最终得分: {score} / 190")

elif mode == "错题本":
    st.subheader(f"错题收录 ({len(st.session_state.mistakes)} 题)")
    if not st.session_state.mistakes: st.caption("暂无错题记录。")
    else:
        for q_id in list(st.session_state.mistakes):
            if q_id not in df.index: continue
            q = df.loc[q_id]
            st.markdown(f"**[{q['题型']}] {q['题干']}**")
            opts, r_ans = parse_opts(q['选项'], q['题型']), "".join(sorted(str(q['答案']).strip().upper()))
            
            if q['题型'] in ["单选", "判断"]:
                labels = [f"{chr(65+i)}. {o}" for i, o in enumerate(opts)] if q['题型'] == "单选" else opts
                for i, lb in enumerate(labels):
                    lt = lb if q['题型'] == "判断" else chr(65+i)
                    if lt in r_ans: st.markdown(f"<span style='color:#2e7d32; font-weight:bold;'>✅ {lb}</span>", unsafe_allow_html=True)
                    else: st.write(lb)
            else:
                for i, o in enumerate(opts):
                    lt = chr(65+i)
                    if lt in r_ans: st.markdown(f"<span style='color:#2e7d32; font-weight:bold;'>✅ {lt}. {o}</span>", unsafe_allow_html=True)
                    else: st.write(f"{lt}. {o}")

            if pd.notna(q['解析']) and q['解析'] != '无': st.caption(f"解析: {q['解析']}")
            if st.button("移除此题", key=f"rm_{q_id}"):
                handle_mistake(q_id, "remove")
                st.rerun()
            st.write("---")