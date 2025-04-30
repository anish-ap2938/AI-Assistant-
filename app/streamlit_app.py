import os
import random
import streamlit as st
import requests
from pathlib import Path

# ─── Configuration ────────────────────────────────────────────────────────
INTERNAL_API_URL = os.getenv("INTERNAL_API_URL", "http://127.0.0.1:8000")
EXTERNAL_API_URL = os.getenv("EXTERNAL_API_URL", INTERNAL_API_URL)

# ─── Page & Layout Config ─────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Simple Password Gate (demo) ──────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.sidebar.title("🔒 Login")
    pwd = st.sidebar.text_input("Password:", type="password")
    if pwd == "password123":
        st.session_state.authenticated = True
    else:
        st.sidebar.error("Incorrect password.")
        st.stop()

# ─── Navigation ───────────────────────────────────────────────────────────
st.sidebar.title("🗂️ Navigation")
page = st.sidebar.radio("Go to", ["Chatbot", "Document Analyzer", "Faculty Onboarding"])

# ─── Cache wrapper for queries ─────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def post_query(payload: dict) -> dict:
    resp = requests.post(f"{INTERNAL_API_URL}/query/", json=payload)
    resp.raise_for_status()
    return resp.json()

# ─── Chatbot Page ─────────────────────────────────────────────────────────
if page == "Chatbot":
    st.title("📚 Private Document QA Chatbot")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    q = st.text_input("Ask a question about your documents:", key="chat_question")
    if st.button("Submit", key="chat_submit") and q:
        with st.spinner("Thinking..."):
            data = post_query({"question": q, "use_agent": False})
        answer = data.get("answer", "No answer returned.")
        st.session_state.chat_history.append((q, answer))

    for i, (user_q, bot_a) in enumerate(st.session_state.chat_history, 1):
        st.markdown(f"**Q{i}:** {user_q}")
        st.markdown(f"**A{i}:** {bot_a}")
        st.markdown("---")

# ─── Document Analyzer ────────────────────────────────────────────────────
elif page == "Document Analyzer":
    st.title("🔍 Document Analyzer Agent")
    st.write("Flags outdated or redundant policies.")
    if st.button("Run Document Analyzer", key="analyzer_submit"):
        with st.spinner("Analyzing…"):
            data = post_query({
                "question":   "Analyze all policies",
                "use_agent":  True,
                "agent_type": "analyzer"
            })
        issues = data.get("issues_found", 0)
        st.success(f"Found **{issues}** issues.")
        report = data.get("report_path") or data.get("filename")
        if report:
            fname = Path(report).name
            st.markdown(f"[⬇️ Download Report]({EXTERNAL_API_URL}/reports/{fname})")

# ─── Faculty Onboarding ────────────────────────────────────────────────────
elif page == "Faculty Onboarding":
    st.title("🎓 Faculty Onboarding Agent")
    st.write("Generates a Week 1 checklist (downloadable) and a 5-question mini-quiz.")

    ss = st.session_state

    # Step-tracker
    if "quiz_step" not in ss:
        ss.quiz_step = 0     
    if "checklist_file" not in ss:
        ss.checklist_file = None
    if "onboard_quiz" not in ss:
        ss.onboard_quiz = []
    if "onboard_answers" not in ss:
        ss.onboard_answers = []
    if "onboard_score" not in ss:
        ss.onboard_score = 0

    # Cached fetch so we don't re-call on every rerun
    @st.cache_data(show_spinner=False)
    def _fetch_onboarding():
        return post_query({
            "question":   "Generate faculty onboarding materials",
            "use_agent":  True,
            "agent_type": "onboarding"
        })

    def _next_step():
        ss.quiz_step += 1
        if ss.quiz_step > 2:
            # reset everything
            ss.quiz_step = 0
            ss.checklist_file = None
            ss.onboard_quiz = []
            ss.onboard_answers = []
            ss.onboard_score = 0
        st.rerun()

    # Buttons
    col1, col2 = st.columns([4,1])
    with col1:
        st.markdown("""
            **How it works**  
            1. Click **Generate** to fetch your Week 1 checklist and a 5-question quiz.  
            2. Download the checklist Excel.  
            3. Answer all five questions.  
            4. Click **Submit** to see the correct answers.  
            5. Click **Reload** to start over.
        """)
    with col2:
        labels = ["Generate", "Submit", "Reload"]
        st.button(labels[ss.quiz_step], on_click=_next_step)

    st.markdown("---")

    # ─── Step 1: Generate & cache checklist+quiz ─────────────────────────────
    if ss.quiz_step == 1 and ss.checklist_file is None:
        with st.spinner("Fetching onboarding materials…"):
            data = _fetch_onboarding()
        # only expose the checklist via Excel
        ss.checklist_file = data.get("filename")
        # sample the quiz
        full_quiz = data.get("quiz", [])
        ss.onboard_quiz = random.sample(full_quiz, min(5, len(full_quiz)))

    # ─── Step 2: Download checklist ──────────────────────────────────────────
    if ss.checklist_file:
        st.subheader("✅ Week 1 Checklist")
        # fetch the file from your API
        url = f"{EXTERNAL_API_URL}/reports/{ss.checklist_file}"
        st.markdown(f"[⬇️ Download Checklist Excel]({url})")
        st.markdown("---")

    # ─── Step 3: Display Quiz ─────────────────────────────────────────────────
    if ss.quiz_step >= 1 and ss.onboard_quiz:
        st.subheader("📝 Mini Quiz")
        for idx, q in enumerate(ss.onboard_quiz):
            st.markdown(f"**Q{idx+1}. {q['question']}**")
            choice = st.radio("Select:", options=q["options"], key=f"onb_q_{idx}")

            if ss.quiz_step == 2:
                if len(ss.onboard_answers) < len(ss.onboard_quiz):
                    ss.onboard_answers.append(choice == q["answer"])
                letter = "N/A"
                if q["answer"] in q["options"]:
                    letter = chr(65 + q["options"].index(q["answer"]))
                st.info(f"▶️ Correct answer: **{letter}**")

        if ss.quiz_step == 2:
            ss.onboard_score = sum(ss.onboard_answers)
            st.markdown(f"### 🎯 Your Score: {ss.onboard_score} / {len(ss.onboard_quiz)}")


st.sidebar.markdown("---")
st.sidebar.caption("© 2025 Anish Panicker")