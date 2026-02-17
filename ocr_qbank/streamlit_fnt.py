import streamlit as st
import requests
import uuid
import os
import re
import asyncio
import boto3
from dotenv import load_dotenv
from botocore.exceptions import NoCredentialsError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import text
import classes

# Load environment variables
load_dotenv()

# Logger setup
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL_2")
engine = create_async_engine(
    DATABASE_URL,
    pool_size=100,
    max_overflow=50,
    pool_recycle=1800,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 600}
)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

def get_session():
    return AsyncSessionLocal()

# AWS S3 setup
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_S3_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_S3_REGION")
)
s3_bucket_name = "neetguide"
s3_folder = "ocr/pdfs"
image_url = "https://neetguide.s3.ap-south-1.amazonaws.com/ocr/question_images/"

# Streamlit UI setup
st.set_page_config(page_title="PDF to Question Viewer", layout="wide")
st.title("📄 Upload PDF & View Questions")

# Session state setup
for key in ['processed_uuid', 'question_data', 'total_tokens_used', 'uploaded_file_name']:
    if key not in st.session_state:
        st.session_state[key] = None if key != 'question_data' else []

# Render function for mixed Markdown/LaTeX

def render_mixed_content(text: str):
    if not text:
        st.markdown("*No content available.*")
        return

    # Pre-clean escape characters
    text = text.replace("\\\\", "\\")     # Replace double backslashes
    text = text.replace("$$", "")         # Remove $$ to support st.latex
    text = text.replace("\\$", "$")       # Optional: fix escaped dollar signs

    lines = text.split("\\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            st.markdown(" ")
            continue

        # Clean HTML-like line breaks and common errors
        stripped = stripped.replace("&nbsp;", " ")

        # Detect if the whole line looks like a LaTeX expression
        try:
            is_latex = re.match(r'^[\\a-zA-Z0-9_{}\^+=*/(). -]+$', stripped)
        except re.error as e:
            st.warning(f"(Regex error: {e})")
            is_latex = False

        # Render appropriately
        if is_latex:
            try:
                st.latex(rf"{stripped}")  # raw formatted string for LaTeX
            except Exception as e:
                st.warning(f"(LaTeX rendering error: {e})")
                st.code(stripped, language="latex")
        else:
            st.markdown(stripped)



# Async DB fetch
async def question_det(uuid: str):
    session: AsyncSession = get_session()
    question_data = []
    try:
        async with session.begin():
            query = text("""
                SELECT q.question, q.correct_opt, q.option_a, q.option_b, q.option_c, q.option_d, q.difficulty, q.q_image,
                       q.option_1_image, q.option_2_image, q.option_3_image, q.option_4_image,
                       q.t_id, q.c_id, q.s_id, q.estimated_time, q.QC, q.answer_desc, q.question_type,
                       q.keywords, t.t_name AS topic_name, s.s_name AS subject_name, c.c_name AS chapter_name,
                       q.cognitive_level
                FROM neetguide.ai_pdf_questions q
                JOIN neetguide.topics t ON q.t_id = t.s_no
                JOIN neetguide.subjects s ON q.s_id = s.s_no
                JOIN neetguide.chapters c ON q.c_id = c.s_no
                WHERE q.uuid = :uuid
                ORDER BY q.s_no
            """)
            result = await session.execute(query, {"uuid": uuid})
            rows = result.fetchall()
            for row in rows:
                ques_dict = {
                    "question": row.question,
                    "correct_option": row.correct_opt,
                    "options": [row.option_a, row.option_b, row.option_c, row.option_d],
                    "explanation": row.answer_desc,
                    "difficulty": next((k for k, v in classes.difficulty_level.items() if v == row.difficulty), None),
                    "estimated_time": row.estimated_time,
                    "subject_name": row.subject_name,
                    "chapter_name": row.chapter_name,
                    "topic_name": row.topic_name,
                    "cognitive_level": next((k for k, v in classes.cognitive_levels.items() if v == row.cognitive_level), None),
                    "question_type": next((k for k, v in classes.question_types.items() if v == row.question_type), None),
                    "concepts": row.keywords,
                    "q_image": row.q_image,
                    "option_1_image": row.option_1_image,
                    "option_2_image": row.option_2_image,
                    "option_3_image": row.option_3_image,
                    "option_4_image": row.option_4_image,
                }
                question_data.append(ques_dict)
    except Exception as e:
        logger.warning(f"Database fetch error: {e}")
    finally:
        await session.close()
    return question_data

# Upload UI
uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])
if uploaded_file:
    if st.session_state.uploaded_file_name != uploaded_file.name:
        st.session_state.uploaded_file_name = uploaded_file.name
        st.session_state.processed_uuid = None
        st.session_state.question_data = []
        st.session_state.total_tokens_used = 0
        st.info(f"File '{uploaded_file.name}' ready for processing.")

    if st.button("Process PDF"):
        current_unique_id = str(uuid.uuid4())
        file_key = f"{s3_folder}/{current_unique_id}-{uploaded_file.name}"
        try:
            s3.upload_fileobj(uploaded_file, s3_bucket_name, file_key)
            s3_url = f"https://neetguide.s3.ap-south-1.amazonaws.com/{file_key}"
            st.success("File Uploaded")
        except NoCredentialsError:
            st.error("Missing AWS credentials")
            st.stop()
        except Exception as e:
            st.error(f"Upload failed: {e}")
            st.stop()

        payload = {"user_id": 3, "uuid": current_unique_id, "file_path": s3_url, "file_name": uploaded_file.name}
        with st.spinner("Processing PDF..."):
            response = requests.post("https://doubts.collegesuggest.com/pdf_question_bank", json=payload)
            #response = requests.post("http://192.168.0.144:8000/pdf_question_bank", json=payload)
            response.raise_for_status()
            data = response.json()

        if data.get("total_questions_processed"):
            st.session_state.total_tokens_used = data.get("total_tokens_info", {}).get('total_tokens', 0)
            with st.spinner("Fetching questions from DB..."):
                st.session_state.question_data = asyncio.run(question_det(current_unique_id))
                st.session_state.processed_uuid = current_unique_id
            st.success(f"Fetched {len(st.session_state.question_data)} questions!")
        else:
            st.warning("No questions found in PDF")

# Display
if st.session_state.question_data:
    st.subheader("Extracted Questions:")
    for i, q in enumerate(st.session_state.question_data, 1):
        with st.expander(f"Q{i}", expanded=True):
            render_mixed_content(q.get("question", ""))
            if q.get("q_image"):
                st.image(f"{image_url}{q['q_image']}", caption="Question Image", width=300)
            st.markdown("#### Options:")
            for idx, opt in enumerate(q.get("options", []), 1):
                opt_img = q.get(f"option_{idx}_image")
                label = f"Option {chr(64+idx)}"
                if str(idx) == str(q.get("correct_option")):
                    st.markdown(f"✅ **{label}:**")
                else:
                    st.markdown(f"**{label}:**")
                render_mixed_content(opt)
                if opt_img:
                    st.image(f"{image_url}{opt_img}", caption=f"{label} Image", width=300)
            st.markdown("#### Explanation:")
            render_mixed_content(q.get("explanation", ""))
            st.markdown(f"**Estimated Time:** `{q.get('estimated_time', 'N/A')}`")
            st.markdown(f"**Subject:** `{q.get('subject_name', 'N/A')}` | **Chapter:** `{q.get('chapter_name', 'N/A')}` | **Topic:** `{q.get('topic_name', 'N/A')}`")
            st.markdown(f"**Difficulty:** `{q.get('difficulty', 'N/A')}` | **Type:** `{q.get('question_type', 'N/A')}` | **Cognitive Level:** `{q.get('cognitive_level', 'N/A')}`")
            st.markdown(f"**Concepts:** `{q.get('concepts', 'N/A')}`")
