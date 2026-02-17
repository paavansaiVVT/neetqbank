
# app.py
import streamlit as st
from datetime import date
#import classes
import boto3
# from uuid import uuid4
import uuid, requests
import os
from tenacity import retry, wait_fixed, stop_after_attempt, before_sleep_log
from typing import Iterable, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func, text
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv
import plotly.graph_objects as go
import plotly.express as px
import os, logging
from sqlalchemy import create_engine, Column, Integer, String, Text, JSON,BLOB,ARRAY,Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
Base= declarative_base()
import asyncio

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL_8")
engine = create_async_engine(DATABASE_URL,pool_size=100,max_overflow=50,pool_recycle=1800, pool_pre_ping=True, connect_args={"connect_timeout": 600})
AsyncSessionLocal = sessionmaker(bind=engine,class_=AsyncSession,expire_on_commit=False)

Base = declarative_base()
retry_on_failure = retry(stop=stop_after_attempt(3),wait=wait_fixed(5),before_sleep=before_sleep_log(logger, logging.WARNING))

def get_session():
    return AsyncSessionLocal()

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_S3_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_S3_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_S3_REGION")
)
s3_bucket_name = "neetguide"
s3_folder = "ocr/pdfs"
image_url = "https://neetguide.s3.ap-south-1.amazonaws.com/ocr/question_images/"
# ----------------------------
# Page setup & light styling
# ----------------------------

class DbQuestionData(Base):
    __tablename__ = 'ocr_question_paper'
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String, nullable=False)
    question_paper_name = Column(String, nullable=False)
    pdf_url = Column(String, nullable=False)
    class_name = Column(String, nullable=False)
    subject_name = Column(String, nullable=False)
    exam_name = Column(String, nullable=False)
    exam_date = Column(String, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    question_paper_json = Column(JSONB, nullable=True)
    contain_image_list = Column(ARRAY(String), nullable=True)
    instruction_set = Column(JSONB, nullable=True)
    md_list = Column(ARRAY(JSONB), nullable=True)

@retry_on_failure
async def fetch_all_question_details():
    session = get_session()
    try:
        async with session.begin():
            result = await session.execute(
                select(DbQuestionData)
            )
            all_questions = result.scalars().all()
            
            if all_questions:
                # Return list of tuples with all question details
                return [
                    {
                        "q_id": question.id,
                        "class_name": question.class_name, 
                        "exam_name": question.exam_name,
                        "subject_name": question.subject_name,
                        "pdf_url": question.pdf_url,
                        "question_paper_name": question.question_paper_name
                    } 
                    for question in all_questions
                ]
            else:
                return []
    except OperationalError as e:
        logger.error(f"Database operation (fetch_all_question_details) failed: {str(e)}")
        raise
    finally:
        await session.close()

st.set_page_config(page_title="Create New Exam", layout="wide", initial_sidebar_state="collapsed")
st.markdown(
    """
    <style>
      .stForm {border: 1px solid #e8e8e8; padding: 1.25rem; border-radius: 12px; background: #fff;}
      .section {margin-top: 1rem; margin-bottom: 0.75rem;}
      .muted {color:#6b7280; font-size:0.9rem;}
      .footer-note {font-size: 0.9rem; color: #6b7280;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Create New Exam")
st.caption("Fill in the details below to set up an exam and attach the question paper PDF.")

# ----------------------------
# Form
# ----------------------------
with st.form("create_exam_form"):
    st.subheader("Exam Details", anchor=False)
    st.caption("Basic information about the exam")

    c1, c2 = st.columns(2)
    exam_title = c1.text_input("Exam Title", placeholder="e.g., Mid-term Mathematics Exam")
    subject = c2.text_input("Subject", placeholder="e.g., Mathematics")

    c3, c4 = st.columns(2)
    cls = c3.text_input("Class", placeholder="e.g., 10th Grade")
    grade_options = [
        "Select grade level",
        "Elementry", "Middle School", "High School", "College"
    ]
    grade_level = c4.selectbox("Grade Level", grade_options, index=0)

    # Optional: show a custom grade field when "Other" is selected
    custom_grade = None
    if grade_level == "Other":
        custom_grade = st.text_input("Specify Grade Level (custom)", placeholder="e.g., Diploma / Foundation Year")

    c5, c6 = st.columns(2)
    exam_date = c5.date_input("Exam Date", value=None, min_value=date(2000, 1, 1))
    duration = c6.number_input("Duration (minutes)", min_value=1, step=5, value=120)

    description = st.text_area("Description (Optional)", placeholder="Additional details about the exam...")

    st.divider()

    st.subheader("Question Paper", anchor=False)
    st.caption("Upload a PDF of the question paper. (You can process it later to auto-generate answer keys.)")
    question_paper = st.file_uploader("Upload Question Paper", type=["pdf"], accept_multiple_files=False)


    # st.divider()

    # st.subheader("Answer Paper", anchor=False)
    # st.caption("Upload a PDF of the answer paper. (This will be used to evaluate the student's answers.)")
    # answer_paper = st.file_uploader("Upload Answer Paper", type=["pdf"], accept_multiple_files=False)

    submitted = st.form_submit_button("Submit", use_container_width=True)

# def upload_pdf_to_s3(file_obj, filename):
#     # Generate a unique filename to avoid collisions
#     current_unique_id = str(uuid.uuid4())
#     file_key = f"{s3_folder}/{current_unique_id}"
#     st.info(f"File '{filename}' ready for processing.")
#     try:
#         s3.upload_fileobj(file_obj,s3_bucket_name, file_key)
#         s3_url= f"https://neetguide.s3.ap-south-1.amazonaws.com/{file_key}.pdf"
#         st.success("File uploaded successfully.")
#         return s3_url
#     except Exception as e:
#         st.error(f"Error uploading file to S3: {e}")
#         return None

def upload_pdf_to_s3(file_obj, filename):
    current_unique_id = str(uuid.uuid4())
    # Always keep the original extension
    ext = os.path.splitext(filename)[1] or ".pdf"
    file_key = f"{s3_folder}/{current_unique_id}{ext}"
    #st.info(f"File '{filename}' ready for processing.")
    try:
        s3.upload_fileobj(file_obj, s3_bucket_name, file_key)
        s3_url = f"https://neetguide.s3.ap-south-1.amazonaws.com/{file_key}"
        st.success("File uploaded successfully.")
        return s3_url
    except Exception as e:
        st.error(f"Error uploading file to S3: {e}")
        return None
    
if "step" not in st.session_state:
    st.session_state.step = 1

# submitted = st.form_submit_button("Create Exam", use_container_width=True)


# ----------------------------
# Submit handling
# ----------------------------
if submitted:
    # Basic validation
    errors = []
    if not exam_title.strip():
        errors.append("• Exam Title is required.")
    if not subject.strip():
        errors.append("• Subject is required.")
    if not cls.strip():
        errors.append("• Class is required.")
    if grade_level == "Select grade level":
        errors.append("• Please choose a Grade Level.")
    if grade_level == "Other" and not (custom_grade or "").strip():
        errors.append("• Please specify the custom Grade Level.")
    if exam_date is None:
        errors.append("• Exam Date is required.")

    if errors:
        st.error("Please fix the following:\n" + "\n".join(errors))
    else:
        pdf_url = None
        if question_paper:
            question_paper.seek(0)
            pdf_url = upload_pdf_to_s3(question_paper, question_paper.name)

        # Build a clean payload
        payload = {
            "uuid": str(uuid.uuid4()),  # ← REQUIRED by your Pydantic model
            "exam_title": exam_title.strip(),
            "subject": subject.strip(),
            "class_name": cls.strip(),  # will map to class_name via alias
            "grade_level": (custom_grade.strip() if grade_level == "Other" else grade_level),
            "exam_date": exam_date.isoformat() if exam_date else None,  # you're already validating exam_date is set
            "duration_minutes": int(duration),
            "description": description.strip() if description else "",
            "question_paper_name": getattr(question_paper, "name", None),
            "pdf_url": pdf_url,
        }

        with st.spinner("Processing PDF..."):

            # response = requests.post("https://doubts.collegesuggest.com/ocr/question_paper_ocr", json=qp_payload)
            response = requests.post("http://localhost:8000/ocr/question_paper_ocr", json=payload)

            response.raise_for_status()
            data = response.json()
            markdown_response = data["md_results"]
            for md in markdown_response:
                st.markdown(md["content"], unsafe_allow_html=True)

        # qpr = QuestionPaperRequest(**payload)
        # print(qpr)
        if data:
            st.success("Exam created (preview below).")
            st.json(payload)

        if question_paper:
            # Preview filename and size; you can persist this to disk or cloud as needed.
            st.info(
                f"Received file: **{question_paper.name}** and its URL: {pdf_url} "
                # f"({len(question_paper.getvalue())/1024:.1f} KB)."
                #f"PDF URL: {pdf_url}"
                #f"Payload sent to OCR API:\n{payload}"
                #f"\n\nResponse from OCR API:\n{data}"
            )

st.markdown("---")
col1, col2 = st.columns([4, 1])
next_button = col2.button("Next", use_container_width=True, key="next_btn")

# go to step 2 when Next is clicked
if next_button:
    st.session_state["step"] = 2  # Streamlit will rerun automatically
    st.rerun()

@st.cache_data(ttl=60, show_spinner=False) # Cache for 60 seconds to avoid frequent DB calls
def get_question_data():
    """Wrapper to handle async call in Streamlit"""
    try:
        result = asyncio.run(fetch_all_question_details())
        return result
    except Exception as e:
        st.error(f"Error fetching question data: {e}")
        return []
    # finally:
    #     loop.close()

# Replace the step 2 section with this updated code:
# show Answer Paper page only on step 2

# show Answer Paper page only on step 2
if st.session_state.get("step") == 2:
    st.subheader("Answer Paper", anchor=False)
    st.caption("Upload a PDF of the answer paper and select existing question details.")
    cdl_options = ["EASY", "MEDIUM", "HARD"]
    cdl_level = c4.selectbox("Correction Level", cdl_options, index=0)
    # Fetch question data for dropdowns
    question_data = get_question_data()
    
    if question_data:
        # Extract unique values for dropdowns
        unique_classes = sorted(list(set([q["class_name"] for q in question_data])))
        unique_exams = sorted(list(set([q["exam_name"] for q in question_data])))
        unique_subjects = sorted(list(set([q["subject_name"] for q in question_data])))
        unique_question_papers = sorted(list(set([q["question_paper_name"] for q in question_data])))
        unique_pdf_urls = sorted(list(set([q["pdf_url"] for q in question_data])))
        unique_ids = sorted(list(set([q["q_id"] for q in question_data])))
        
        # Create four columns for the dropdowns
        col_class, col_exam, col_subject, col_paper,col_cdl= st.columns(5)
        
        with col_class:
            selected_class = st.selectbox(
                "Select Class",
                ["Select a class"] + unique_classes,
                key="class_dropdown"
            )
        
        with col_exam:
            selected_exam = st.selectbox(
                "Select Exam",
                ["Select an exam"] + unique_exams,
                key="exam_dropdown"
            )
            
        with col_subject:
            selected_subject = st.selectbox(
                "Select Subject",
                ["Select a subject"] + unique_subjects,
                key="subject_dropdown"
            )
            
        with col_paper:
            selected_question_paper = st.selectbox(
                "Select Question Paper",
                ["Select a paper"] + unique_question_papers,
                key="paper_dropdown"
            )

        with col_cdl:
            cdl_options = ["EASY", "MEDIUM", "HARD"]
            cdl_level = st.selectbox(
                "Correction Level",
                cdl_options,
                index=0,  # Defaults to "EASY"
                key="cdl_level_main"
            )
        
        # Filter questions based on selections
        filtered_questions = question_data
        if selected_class != "Select a class":
            filtered_questions = [q for q in filtered_questions if q["class_name"] == selected_class]
        if selected_exam != "Select an exam":
            filtered_questions = [q for q in filtered_questions if q["exam_name"] == selected_exam]
        if selected_subject != "Select a subject":
            filtered_questions = [q for q in filtered_questions if q["subject_name"] == selected_subject]
        if selected_question_paper != "Select a paper":
            filtered_questions = [q for q in filtered_questions if q["question_paper_name"] == selected_question_paper]
        
        # Show filtered results info
        if any([selected_class != "Select a class", selected_exam != "Select an exam", 
                selected_subject != "Select a subject", selected_question_paper != "Select a paper"]):
            st.info(f"Found {len(filtered_questions)} matching question papers")
            
            # Show a table of matching questions with all fields
            if filtered_questions:
                st.write("**Matching Question Papers:**")
                import pandas as pd
                # Select specific columns to display
                display_data = [{
                    "ID": q["q_id"],
                    "Class": q["class_name"],
                    "Exam": q["exam_name"],
                    "cdl_level": cdl_level,
                    "Subject": q["subject_name"],
                    "Question Paper": q["question_paper_name"],
                    "PDF URL": q["pdf_url"][:50] + "..." if len(q["pdf_url"]) > 50 else q["pdf_url"]  # Truncate long URLs
                } for q in filtered_questions]
                df = pd.DataFrame(display_data)
                st.dataframe(df, use_container_width=True)                
                
                # If only one result, show more details
                if len(filtered_questions) == 1:
                    selected_question = filtered_questions[0]
                    selected_question["cdl_level"] = cdl_level
                    st.info(f"**Selected Question Paper:** {selected_question['question_paper_name']}")
                    with st.expander("View Full Details"):
                        st.json(selected_question)
    else:
        st.warning("No question data available. Please ensure the database contains question papers.")
    
    # File uploader for answer paper
    st.divider()
    answer_paper = st.file_uploader(
        "Upload Answer Paper",
        type=["pdf"],
        accept_multiple_files=False,
        key="answer_paper_uploader",
        help="Upload the PDF containing the answer key for the selected question paper"
    )
    
    # Navigation buttons
    colA, colB = st.columns([1, 1])
    back = colA.button("⬅ Back", use_container_width=True, key="back_btn")
    finish = colB.button("Submit", use_container_width=True, key="finish_btn")
    
    if finish:
        # Handle the submission logic here
        validation_conditions = [
            answer_paper is not None,
            selected_class != "Select a class",
            selected_exam != "Select an exam",
            selected_subject != "Select a subject"
        ]
        
        if all(validation_conditions):
            st.session_state["selected_question"] = filtered_questions[0]
            # st.session_state["answer_pdf_url"] = answer_pdf_url
            st.session_state["cdl_level"] = cdl_level
            st.session_state["ready_to_process"] = True
            st.success("Answer paper uploaded successfully!")
            # st.info(f"**Selected Question Paper:** {selected_question['question_paper_name']}")
            # st.info(f"**Answer Paper URL:** {answer_pdf_url}")

    if st.session_state.get("ready_to_process", False):
        st.subheader("Processing Options", anchor=False)            
                # Required input fields for processing
        answer_pdf_url = upload_pdf_to_s3(answer_paper, answer_paper.name)
        input_col1, input_col2 = st.columns(2)

        with input_col1:
            student_rollno = st.text_input(
                "Student Roll No (Optional)",
                key="student_rollno",
                placeholder="Enter student roll number"
            )
        
        with input_col2:
            # Display selected CDL level (read-only info)
            st.info(f"CDL Level: {cdl_level}")
        
        # Process button
        if st.button("Process Answer Sheet", use_container_width=True, type="primary"):
            # Validate CDL level is selected
            # Create payload with user inputs
            updated_payload = {
                "pdf_url": answer_pdf_url,
                "question_id": selected_question["q_id"],
                "standard": selected_question["class_name"],
                "subject": selected_question["subject_name"],
                "cdl_level": cdl_level,
                "student_rollno": student_rollno if student_rollno.strip() else None,
                "model": 2
            }
            
            # Display the payload
            with st.expander("View Answer Sheet Payload"):
                st.json(updated_payload)
            
            with st.spinner("Processing answer sheet..."):
                try:
                    # Call your answer sheet processing API
                    # response = requests.post("http://localhost:8000/ocr/answer_paper_ocr",json=updated_payload)
                    # response.raise_for_status()
                    response = {'response': [{'section': 'A', 'question_number': '1', 'question_text': 'Which among the following is (are) double displacement reaction(s)?\n1. $\\mathrm{Pb}+\\mathrm{CuCl}_{2} \\rightarrow \\mathrm{PbCl}_{2}+\\mathrm{Cu}$\n2. $\\mathrm{Na}_{2} \\mathrm{SO}_{4}+\\mathrm{BaCl}_{2} \\rightarrow \\mathrm{BaSO}_{4}+2 \\mathrm{NaCl}$\n3. $\\mathrm{C}+\\mathrm{O}_{2} \\rightarrow \\mathrm{CO}_{2}$\n4. $\\mathrm{CH}_{4}+2 \\mathrm{O}_{2} \\rightarrow \\mathrm{CO}_{2}+2 \\mathrm{H}_{2} \\mathrm{O}$\na) 1 and 4 b) only 2 c) 1 and 2 d) 3 and 4', 'student_answer_text': '(b) Only a', 'actual_answer': 'Double displacement reactions involve the exchange of ions between two compounds.\n1. $\\mathrm{Pb}+\\mathrm{CuCl}_{2} \\rightarrow \\mathrm{PbCl}_{2}+\\mathrm{Cu}$ (Displacement reaction)\n2. $\\mathrm{Na}_{2} \\mathrm{SO}_{4}+\\mathrm{BaCl}_{2} \\rightarrow \\mathrm{BaSO}_{4}+2 \\mathrm{NaCl}$ (Double displacement reaction)\n3. $\\mathrm{C}+\\mathrm{O}_{2} \\rightarrow \\mathrm{CO}_{2}$ (Combination reaction)\n4. $\\mathrm{CH}_{4}+2 \\mathrm{O}_{2} \\rightarrow \\mathrm{CO}_{2}+2 \\mathrm{H}_{2} \\mathrm{O}$ (Combustion reaction)\nTherefore, only reaction 2 is a double displacement reaction.\nCorrect option: (b) only 2', 'feedback': 'Your choice of option (b) is correct, indicating that only reaction 2 is a double displacement reaction.', 'maximum_marks': 1, 'marks_awarded': 1}, {'section': 'A', 'question_number': '2', 'question_text': 'A metal M of moderate reactivity is present as its sulphide $\\mathbf{X}$. On heating in air, $\\mathbf{X}$ converts into its oxide $Y$ and a gas evolves. On heating $Y$ and $X$ together, the metal $M$ is produced. $X$ and $Y$ respectively are\n(a) $X$ cuprous sulphide, $Y$ cuprous oxide\n(b) $X$ cuprous sulphide, $Y$ cupric oxide\n(c) $X$ sodium sulphide, $Y$ sodium oxide\n(d) $X$ calcium sulphide, $Y$ calcium oxide', 'student_answer_text': '(b) X cuprous sulphide, Y cupric oxfetal', 'actual_answer': 'The metal M is of moderate reactivity, present as its sulphide X. Heating X in air (roasting) converts it to oxide Y. Heating Y and X together produces metal M (auto-reduction).\nThis describes the extraction of copper from copper glance (cuprous sulphide).\n$\\mathrm{2Cu_2S}(s) + 3\\mathrm{O_2}(g) \\xrightarrow{heat} \\mathrm{2Cu_2O}(s) + 2\\mathrm{SO_2}(g)$ (X to Y)\n$\\mathrm{2Cu_2O}(s) + \\mathrm{Cu_2S}(s) \\xrightarrow{heat} \\mathrm{6Cu}(s) + \\mathrm{SO_2}(g)$ (Y and X to M)\nSo, X is cuprous sulphide ($\\mathrm{Cu_2S}$) and Y is cuprous oxide ($\\mathrm{Cu_2O}$).\nCorrect option: (a) X cuprous sulphide, Y cuprous oxide', 'feedback': 'Your chosen option (b) is incorrect. The auto-reduction process involves cuprous oxide, not cupric oxide. Also, ensure precise spelling for chemical compounds.', 'maximum_marks': 1, 'marks_awarded': 0}, {'section': 'A', 'question_number': '3', 'question_text': 'Arrange the following in the increasing order of pH values according to the given pH scale\n[DIAGRAM: pH scale showing values from 0 to 14, with acidic, neutral, and alkaline ranges.]\nA. NaOH solution B. Blood C. Lemon juice D. Milk of magnesia\n(a) $\\mathrm{C}<\\mathrm{B}<\\mathrm{D}<\\mathrm{A}$\n(b) $A<B<C<D$\n(c) $D<C<B<A$\n(d) $A<B<D<C$', 'student_answer_text': '(c) DCCLBLAX', 'actual_answer': 'The pH scale ranges from 0 (very acidic) to 14 (very alkaline), with 7 being neutral.\nLemon juice: pH 2-3 (Acidic)\nBlood: pH 7.35-7.45 (Slightly alkaline)\nMilk of Magnesia: pH 10.5 (Alkaline)\nNaOH solution: pH 13-14 (Strongly alkaline)\nIncreasing order of pH values: Lemon juice < Blood < Milk of Magnesia < NaOH solution (C < B < D < A)\nCorrect option: (a) $\\mathrm{C}<\\mathrm{B}<\\mathrm{D}<\\mathrm{A}$', 'feedback': 'Your chosen option (c) is incorrect. The correct increasing order of pH values is C < B < D < A. Please review the pH values of common substances.', 'maximum_marks': 1, 'marks_awarded': 0}, {'section': 'A', 'question_number': '4', 'question_text': 'Which of the following are correctly matched in the given table?\n| 1. | Acid + salt | Metal + hydrogen |\n| 2. | Acid + metal carbonate | salt $+\\mathrm{CO}_{2}+$ water |\n| 3. | Metal oxide + acid | Salt + water |\na) 1 and 2 (b) 2 and 3 (c) 1 and 3 (d) 1, 2 and 3', 'student_answer_text': '(b) 2 and 3', 'actual_answer': '1. Acid + salt: This reaction generally does not produce Metal + hydrogen. Acids react with *metals* to produce salt and hydrogen. So, 1 is incorrect.\n2. Acid + metal carbonate: Produces salt + $\\mathrm{CO_2}$ + water. (e.g., $\\mathrm{CaCO_3} + 2\\mathrm{HCl} \\rightarrow \\mathrm{CaCl_2} + \\mathrm{CO_2} + \\mathrm{H_2O}$). So, 2 is correct.\n3. Metal oxide + acid: Produces salt + water. (e.g., $\\mathrm{CuO} + 2\\mathrm{HCl} \\rightarrow \\mathrm{CuCl_2} + \\mathrm{H_2O}$). So, 3 is correct.\nCorrect option: (b) 2 and 3', 'feedback': 'Your answer is correct. Both statements 2 and 3 correctly describe the reactions.', 'maximum_marks': 1, 'marks_awarded': 1}, {'section': 'A', 'question_number': '5', 'question_text': 'A metal rod (M) was dipped in a coloured solution (Y). After sometime it was observed that the metal rod starts dissolving in the solution and the solution starts fading in colour. However, a coloured precipitate (Z) was seen at the bottom of the beaker. (M), (Y) and (Z) could be\n[DIAGRAM: A beaker with a metal rod (M) dipped into a colored solution (Y), showing a precipitate (Z) at the bottom.]\na) $M=Z n, Y=F e S O_{4}, Z=F e$\nb) $M=\\mathrm{Cu}, \\mathrm{Y}=\\mathrm{Al}_{2}\\left(\\mathrm{SO}_{4}\\right)_{3}, \\mathrm{Z}=\\mathrm{Al}$\nc) $M=A g, Y=C u S O_{4}, Z=C u$\nd) $M=F e, Y=Z n S O_{4}, Z=Z n$', 'student_answer_text': '(a) M = Zn, Y = FeSO₄, Z = FeS₂O₄', 'actual_answer': 'The observation describes a displacement reaction where a more reactive metal (M) displaces a less reactive metal (Z) from its salt solution (Y). The solution fades in color if the original solution was colored and the new solution is less colored or colorless. A colored precipitate (Z) is formed.\na) $\\mathrm{M=Zn}$, $\\mathrm{Y=FeSO_4}$ (green solution), $\\mathrm{Z=Fe}$ (grey/black precipitate). $\\mathrm{Zn}$ is more reactive than $\\mathrm{Fe}$. $\\mathrm{Zn}$ dissolves, $\\mathrm{FeSO_4}$ solution fades (from green to colorless $\\mathrm{ZnSO_4}$), and $\\mathrm{Fe}$ precipitates. This matches the description.\nb) $\\mathrm{M=Cu}$, $\\mathrm{Y=Al_2(SO_4)_3}$, $\\mathrm{Z=Al}$. $\\mathrm{Cu}$ is less reactive than $\\mathrm{Al}$, so no reaction.\nc) $\\mathrm{M=Ag}$, $\\mathrm{Y=CuSO_4}$ (blue solution), $\\mathrm{Z=Cu}$ (reddish-brown precipitate). $\\mathrm{Ag}$ is less reactive than $\\mathrm{Cu}$, so no reaction.\nd) $\\mathrm{M=Fe}$, $\\mathrm{Y=ZnSO_4}$, $\\mathrm{Z=Zn}$. $\\mathrm{Fe}$ is less reactive than $\\mathrm{Zn}$, so no reaction.\nCorrect option: (a) $\\mathrm{M=Zn, Y=FeSO_4, Z=Fe}$', 'feedback': 'Your choice of option (a) is correct, but your written chemical formula for Z ($\\mathrm{FeS_2O_4}$) is incorrect. Z should be Fe (iron metal).', 'maximum_marks': 1, 'marks_awarded': 0}, {'section': 'A', 'question_number': '6', 'question_text': 'Generally metals react with acids to give salt and hydrogen gas.\n[DIAGRAM: An image showing a reaction of metal with acid producing hydrogen gas.]\nWhich of the following acids does not give hydrogen gas on reacting with metals (except Mg and Mn )?\na) $\\mathrm{H}_{2} \\mathrm{SO}_{4}$ b) HCl c) $\\mathrm{HNO}_{3}$ d) All of these', 'student_answer_text': '(c) AMO₃', 'actual_answer': 'Generally, metals react with acids to give salt and hydrogen gas. However, nitric acid ($\\mathrm{HNO_3}$) is a strong oxidizing agent. It oxidizes the $\\mathrm{H_2}$ produced to water and itself gets reduced to any of the nitrogen oxides ($\\mathrm{NO_2}$, $\\mathrm{NO}$, $\\mathrm{N_2O}$). Only very dilute $\\mathrm{HNO_3}$ reacts with Mg and Mn to produce $\\mathrm{H_2}$ gas.\nCorrect option: (c) $\\mathrm{HNO_3}$', 'feedback': 'Your choice of option (c) is correct, but the chemical formula you wrote is incorrect. It should be $\\mathrm{HNO_3}$ for nitric acid.', 'maximum_marks': 1, 'marks_awarded': 0}, {'section': 'A', 'question_number': '7', 'question_text': 'Which of the following is the structural formulae of ethyne?\n(a) $\\mathrm{H}-\\mathrm{C} \\equiv \\mathrm{C}-\\mathrm{H}$\n(b) $\\mathrm{H}_{2}-\\mathrm{C} \\equiv \\mathrm{C}-\\mathrm{H}$\n(c) $\\mathrm{H}_{2} \\mathrm{C}=\\mathrm{CH}_{2}$\n(d) $\\mathrm{H}_{2} \\mathrm{C}-\\mathrm{CH}_{3}$', 'student_answer_text': '(c) "C = C"', 'actual_answer': 'Ethyne is an alkyne with the molecular formula $\\mathrm{C_2H_2}$. It has a carbon-carbon triple bond.\nIts structural formula is $\\mathrm{H-C \\equiv C-H}$.\nCorrect option: (a) $\\mathrm{H-C \\equiv C-H}$', 'feedback': 'Your chosen option (c) represents ethene ($\\mathrm{H_2C=CH_2}$), not ethyne. Ethyne has a carbon-carbon triple bond.', 'maximum_marks': 1, 'marks_awarded': 0}, {'section': 'A', 'question_number': '8', 'question_text': 'In holozoic organisms food is digested and absorbed within the body of organisms. Identify the structure that helps in absorbtion.\n(a) liver (b) villi (c) small intestine (d) large intestine', 'student_answer_text': '(b) VIVI', 'actual_answer': 'In holozoic organisms, after digestion in the stomach and small intestine, the absorption of digested food primarily occurs in the small intestine. The inner lining of the small intestine has millions of tiny, finger-like projections called villi, which increase the surface area for efficient absorption of nutrients.\nCorrect option: (b) villi', 'feedback': "Your answer is correct, though there's a minor spelling error. The correct term is 'villi'.", 'maximum_marks': 1, 'marks_awarded': 1}, {'section': 'A', 'question_number': '9', 'question_text': 'Receptors are neurons specialised for a particular stimuli. Where are gustatory receptors located?\n(a) eye (b) nose (c) tongue (d) ear', 'student_answer_text': '(c) Tongue', 'actual_answer': 'Gustatory receptors are specialized sensory receptors responsible for the sense of taste. They are primarily located in the taste buds on the **tongue**.\nCorrect option: (c) tongue', 'feedback': 'Your answer is correct.', 'maximum_marks': 1, 'marks_awarded': 1}, {'section': 'A', 'question_number': '10', 'question_text': 'A farmer wants to grow banana plant genetically similar to the plants already available in his field. Which of the following methods would you suggest for this purpose?\na) regeneration b) vegetative propagation c) budding d) sexual reproduction', 'student_answer_text': '(b) Vegetative propagation', 'actual_answer': 'To grow banana plants genetically similar to existing ones, the farmer should use methods of asexual reproduction. Vegetative propagation is a type of asexual reproduction that produces genetically identical offspring from vegetative parts of the plant. Banana plants commonly reproduce through suckers, a form of vegetative propagation.\nCorrect option: (b) vegetative propagation', 'feedback': 'Your answer is correct.', 'maximum_marks': 1, 'marks_awarded': 1}, {'section': 'A', 'question_number': '11', 'question_text': 'Height of a plant is regulated by:\na) DNA influenced by growth hormone\nb) Genes which regulate proteins\nc) Growth hormones under the influence of the enzyme coded by a gene\nd) Growth hormones directly under the influence of gene', 'student_answer_text': '(d) Grownth hormone directly under the influence of gene', 'actual_answer': 'The height of a plant, like many other traits, is regulated by genes. Genes contain the information for synthesizing proteins, which can include enzymes. These enzymes, in turn, control the production or activity of growth hormones (like gibberellins and auxins). Thus, growth hormones work under the influence of enzymes coded by genes.\nCorrect option: (c) Growth hormones under the influence of the enzyme coded by a gene', 'feedback': 'Your answer is incorrect. Height is regulated by growth hormones, but these are influenced by enzymes coded by genes, not directly by genes.', 'maximum_marks': 1, 'marks_awarded': 0}, {'section': 'A', 'question_number': '12', 'question_text': 'A sportsman, after a long session of his regular rigorous exercise, experienced muscle cramps. This happened due to:\na) lack of carbon dioxide and formation of pyruvate\nb) presence of oxygen and formation of ethanol\nc) lack of oxygen and formation of lactic acid\nd) lack of oxygen and formation of carbondioxide', 'student_answer_text': '(c) Lack of oxygen and formation of lactic acid', 'actual_answer': 'During rigorous exercise, the demand for oxygen by muscle cells increases. If the oxygen supply is insufficient, muscle cells switch to anaerobic respiration to produce energy. In this process, glucose is incompletely broken down into lactic acid, which accumulates in the muscles and causes muscle cramps.\nCorrect option: (c) lack of oxygen and formation of lactic acid', 'feedback': 'Your answer is correct.', 'maximum_marks': 1, 'marks_awarded': 1}, {'section': 'A', 'question_number': '13', 'question_text': 'Some waste products are listed below:\n- Grass Cutting\n- Polythene Bag\n- Plastic Toys\n- Used Tea Bags\n- Old Clothes\n- Paper Straw\nWhich group of waste materials can be classified as non-biodegradable?\na) Plant waste, used tea bags\nb) Polythene bags, plastic toys\nc) Used tea bags, paper straw\nd) Old clothes, broken footwear', 'student_answer_text': '(b) Polythene bags, plastic toys', 'actual_answer': 'Non-biodegradable waste materials are those that cannot be broken down by natural processes (like action of microorganisms).\n- Grass Cutting: Biodegradable\n- Polythene Bag: Non-biodegradable\n- Plastic Toys: Non-biodegradable\n- Used Tea Bags: Biodegradable\n- Old Clothes: Biodegradable (if made of natural fibers)\n- Paper Straw: Biodegradable\nThe group of non-biodegradable waste materials is polythene bags and plastic toys.\nCorrect option: (b) Polythene bags, plastic toys', 'feedback': 'Your answer is correct.', 'maximum_marks': 1, 'marks_awarded': 1}, {'section': 'A', 'question_number': '14', 'question_text': 'Which statement shows the interaction of an abiotic component with a biotic component in an ecosystem?\na) A grasshopper feeding on a leaf\nb) Rainwater running down into the lake\nc) An earthworm making a burrow in the soil\nd) A mouse fighting with another mouse for food', 'student_answer_text': '(a) A grasshopper feeding on a leaf', 'actual_answer': 'An ecosystem consists of biotic (living) and abiotic (non-living) components. An interaction between them involves a living organism interacting with a non-living factor.\na) A grasshopper (biotic) feeding on a leaf (biotic) - Biotic-Biotic interaction.\nb) Rainwater (abiotic) running down into the lake (abiotic) - Abiotic-Abiotic interaction.\nc) An earthworm (biotic) making a burrow in the soil (abiotic) - Biotic-Abiotic interaction. This fits the description.\nd) A mouse (biotic) fighting with another mouse (biotic) for food - Biotic-Biotic interaction.\nCorrect option: (c) An earthworm making a burrow in the soil', 'feedback': 'Your answer is incorrect. A grasshopper feeding on a leaf is a biotic-biotic interaction. The question asks for an abiotic-biotic interaction.', 'maximum_marks': 1, 'marks_awarded': 0}, {'section': 'A', 'question_number': '15', 'question_text': 'In the diagram shown below, a beam of light is travelling from inside a glass slab to air. Which of the marked paths will the ray of light take as it emerges from the glass slab?\n[DIAGRAM: A glass slab with a light ray entering, and then emerging into air. Three possible paths (P, Q, R) are marked for the emergent ray.]\nA. $P$\nB. Q\nC. $R$\nD. None of them as light splits into its many colours.', 'student_answer_text': '(c) R', 'actual_answer': 'When a beam of light travels from a denser medium (glass) to a rarer medium (air), it bends away from the normal. The angle of refraction will be greater than the angle of incidence. Path R shows the ray bending away from the normal.\nCorrect option: (c) R', 'feedback': 'Your answer is correct.', 'maximum_marks': 1, 'marks_awarded': 1}, {'section': 'A', 'question_number': '16', 'question_text': 'The current flowing through a resistor connected in an electrical circuit and the potential difference developed across its ends are shown in the given ammeter and voltmeter. The voltage and the current across the given resistor are respectively:\n[DIAGRAM: An ammeter showing current reading and a voltmeter showing voltage reading.]\n(a) $2.1 \\mathrm{~V}, 0.3 \\mathrm{~A}$\n(b) $3.1 \\mathrm{~V}, 1.3 \\mathrm{~A}$\n(c) $1.1 \\mathrm{~V}, 0.6 \\mathrm{~A}$\n(d) $0.1 \\mathrm{~V}, 0.2 \\mathrm{~A}$', 'student_answer_text': '(a) 2.1 V, 0.2 A correct', 'actual_answer': 'From the image:\nAmmeter reading (current, I): The scale has 10 divisions between 0 and 0.5 A. So each division is 0.5/10 = 0.05 A. The needle is at 6 divisions after 0, which is 0.05 * 6 = 0.3 A.\nVoltmeter reading (voltage, V): The scale has 10 divisions between 0 and 1 V. So each division is 1/10 = 0.1 V. The needle is at 1 division after 2 V, which is 2 + 0.1 = 2.1 V.\nTherefore, the voltage is 2.1 V and the current is 0.3 A.\nCorrect option: (a) 2.1 V, 0.3 A', 'feedback': 'Your identified voltage (2.1 V) is correct, but your current reading (0.2 A) is incorrect. The ammeter reads 0.3 A.', 'maximum_marks': 1, 'marks_awarded': 0}, {'section': 'A', 'question_number': '17', 'question_text': 'Questions 17-20 consists of 2 statements- Assertion(A) and Reason.(R) Answer these questions selecting the appropriate option given below.\n(a) Both $A$ and $R$ are true and $R$ is the correct explanation of $A$.\n(b) Both $A$ and $R$ are true but $R$ is not the correct explanation of $A$.\n(c) $A$ is true but $R$ is false.\n(d) $A$ is false but $R$ is true.\n17. ASSERTION (A): Danger signals are made of red colour.\nREASON (R): Velocity of red light in air is maximum, so signals are visible even in dark.', 'student_answer_text': '(a) Both A and R are correct and R is the correct explanation of A', 'actual_answer': 'ASSERTION (A): Danger signals are made of red colour. (True)\nREASON (R): Red light is scattered the least by atmospheric particles (due to its longer wavelength) and can travel farthest without much loss of intensity. Therefore, it is visible even in foggy or smoky conditions. Velocity of red light in air is not maximum; all colors of light travel at approximately the same speed in a vacuum (and nearly so in air). The reason stated is incorrect.\nSo, A is true, but R is false.\nCorrect option: (c) A is true but R is false.', 'feedback': "Your answer is incorrect. While Assertion (A) is true, Reason (R) is false. Red light's velocity is not maximum in air; its visibility is due to minimal scattering.", 'maximum_marks': 1, 'marks_awarded': 0}, {'section': 'A', 'question_number': '18', 'question_text': '18. ASSERTION (A): Biodegradable substances result in the formation of compost and natural replenishment.\nREASON (R): It is due to breakdown of complex inorganic substances into simple organic substances.', 'student_answer_text': '(a) Both A and R are correct and R is the explanation of A', 'actual_answer': 'ASSERTION (A): Biodegradable substances result in the formation of compost and natural replenishment. (True)\nREASON (R): It is due to breakdown of complex inorganic substances into simple organic substances. (False, decomposers break down complex *organic* substances into simpler *inorganic* substances, which enrich the soil.)\nSo, A is true, but R is false.\nCorrect option: (c) A is true but R is false.', 'feedback': 'Your answer is incorrect. Assertion (A) is true, but Reason (R) is false. Decomposers break down complex *organic* substances into simple *inorganic* ones.', 'maximum_marks': 1, 'marks_awarded': 0}, {'section': 'A', 'question_number': '19', 'question_text': '19. ASSERTION (A): Probability of survival of an organism produced through sexual reproduction is more than that of organism produced through asexual mode.\nREASON (R): Variations provide advantages to individuals for survival.', 'student_answer_text': '(b) Both A and R are correct but R is not the correct explanation of A', 'actual_answer': 'ASSERTION (A): Probability of survival of an organism produced through sexual reproduction is more than that of organism produced through asexual mode. (True)\nREASON (R): Variations provide advantages to individuals for survival. (True)\nSexual reproduction introduces variations, which are crucial for adaptation and survival in changing environments. Therefore, R is the correct explanation for A.\nCorrect option: (a) Both A and R are true and R is the correct explanation of A.', 'feedback': 'Your answer is incorrect. Both A and R are true, and R *is* the correct explanation of A because variations from sexual reproduction enhance survival.', 'maximum_marks': 1, 'marks_awarded': 0}, {'section': 'A', 'question_number': '20', 'question_text': '20. ASSERTION (A): The following chemical equation, $2 \\mathrm{C}_{4} \\mathrm{H}_{6}+7 \\mathrm{O}_{2} \\rightarrow 4 \\mathrm{CO}_{2}+6 \\mathrm{H}_{2} \\mathrm{O}$ is a balanced chemical equation\nREASON (R): In a balanced chemical equation, the total number of atoms of each element will be equal on both the sides of the equation.', 'student_answer_text': '(d) A is false, but R is true', 'actual_answer': 'ASSERTION (A): The following chemical equation, $2 \\mathrm{C}_{4} \\mathrm{H}_{6}+7 \\mathrm{O}_{2} \\rightarrow 4 \\mathrm{CO}_{2}+6 \\mathrm{H}_{2} \\mathrm{O}$ is a balanced chemical equation.\nLHS: C = 2*4 = 8, H = 2*6 = 12, O = 7*2 = 14\nRHS: C = 4*1 = 4, H = 6*2 = 12, O = (4*2) + (6*1) = 8 + 6 = 14\nCarbon atoms (8 on LHS, 4 on RHS) are not balanced. So, Assertion A is FALSE.\nREASON (R): In a balanced chemical equation, the total number of atoms of each element will be equal on both the sides of the equation. (True, this is the definition of a balanced equation).\nSo, A is false but R is true.\nCorrect option: (d) A is false but R is true.', 'feedback': 'Your answer is correct.', 'maximum_marks': 1, 'marks_awarded': 1}, {'section': 'B', 'question_number': '21', 'question_text': 'Why does it take some time to see the objects in a dim-lit room when we enter the room from bright sunlight outside?\nOR\nA person cannot see objects nearer than 75 cm from his eyes while a person with normal\nvision can see objects up to 25 cm from his eyes. Find the nature, the focal length and the power of the correcting lens used for the defective vision.', 'student_answer_text': '[DIAGRAM: A cross-out calculation for the OR part of Q21.]\nA person outside takes some time to see the objects in a dim-lit room when he enters the room from bright sunshine outside because it takes some time for our pupil to adjust to the dim-light as our pupil regulates the amount of light entering our eye.', 'actual_answer': 'When we enter a dim-lit room from bright sunlight, our pupils are initially constricted to limit light entry. To see objects in the dim room, the pupils need to dilate to allow more light to enter the eye. This adjustment takes some time, causing temporary difficulty in seeing.', 'feedback': 'Your explanation for pupil adjustment to dim light is accurate and well-described.', 'maximum_marks': 2, 'marks_awarded': 2}, {'section': 'B', 'question_number': '22', 'question_text': 'The linear magnification produced by a spherical mirror is +3 . Analyse this value and state the (i) type of mirror and (ii) position of the object with respect to the pole of the mirror. Draw ray diagram to show the formation of image in this case.', 'student_answer_text': 'm = +3\n(i) Convex mirror\n(ii) Virtual, erect diminished\n[DIAGRAM: A ray diagram showing a convex mirror with an object and its virtual, erect, and diminished image formed behind the mirror.]', 'actual_answer': 'A linear magnification of +3 indicates that the image is virtual, erect, and magnified. This type of image is formed by a concave mirror when the object is placed between its pole (P) and principal focus (F).\n(i) Type of mirror: Concave mirror\n(ii) Position of the object: Between the pole (P) and principal focus (F) of the concave mirror.\n[DIAGRAM: A ray diagram showing a concave mirror, an object placed between P and F, and a virtual, erect, and magnified image formed behind the mirror.]', 'feedback': 'Your analysis of magnification (+3) is incorrect. A magnification of +3 indicates a virtual, erect, and *magnified* image, formed by a concave mirror when the object is between P and F. Your stated mirror type, image nature, and diagram are all incorrect for this case.', 'maximum_marks': 2, 'marks_awarded': 0}, {'section': 'B', 'question_number': '23', 'question_text': 'State the post fertilisation changes that lead to fruit formation in plants.', 'student_answer_text': 'After reaching the ovary, the pollen grain fuses with the ovule forming zygote. Then the zygote gradually grows and this leads to a formation of a fruit.', 'actual_answer': 'After fertilization, the zygote develops into an embryo. The ovule develops into a seed, and the ovary develops into the fruit. The petals, sepals, stamens, and stigma usually wither and fall off.', 'feedback': 'Your answer partially explains the changes. While the zygote forms and grows, you missed key details: the ovule develops into the seed, and the ovary develops into the fruit.', 'maximum_marks': 2, 'marks_awarded': 1}, {'section': 'B', 'question_number': '24', 'question_text': 'What is the purpose of making urine in the human body? Name the organs that store and release urine.\nOR \nWhy do arteries have thick and elastic walls whereas veins have valves?', 'student_answer_text': "The purpose of making urine is to release out the waste products from our body. Shelley and Dunlary bladder stores the urine and release it out when there is a urge to pass it out.\n\nThe arteries have thick walls because the arteries carry blood that emerges from heart, under/high pressure. Sine Cairn carry deoxygenated blood from all over the body. Since the blood carried by Sine are no longer under pressure they don't have thick walls. Instead they have valves that ensure the blood flows in only one direction.", 'actual_answer': "The purpose of making urine in the human body is to filter out nitrogenous waste products (like urea, uric acid) and excess water, salts, and other metabolic wastes from the blood, maintaining the body's fluid and electrolyte balance. The urinary bladder stores urine, and the urethra releases it.", 'feedback': "You correctly identified the purpose of urine formation. However, the organs for storage and release were partially incorrect; it's the urinary bladder and urethra. Please be precise with anatomical terms.", 'maximum_marks': 2, 'marks_awarded': 1.5}, {'section': 'B', 'question_number': '25', 'question_text': 'State with reason any two possible consequences of elimination of decomposers from the earth.', 'student_answer_text': "The breakdown of complex substances - into simpler ones won't take place because decomposers breakdown complex substances into simpler ones.\n\nSoll degradation occurs as a result of the existence of complex substances.", 'actual_answer': 'If decomposers are eliminated:\n1.  **Nutrient Cycling will stop**: Decomposers break down dead organic matter, returning nutrients to the soil. Without them, nutrients would remain locked in dead organisms, making them unavailable for producers, thus disrupting the ecosystem.\n2.  **Accumulation of Dead Organic Matter**: Dead plants and animals would pile up, leading to an unclean environment and a shortage of space.', 'feedback': "You correctly identified that breakdown of complex substances wouldn't occur. Your second point on soil degradation is vague and needs more clarity regarding nutrient cycling and the accumulation of dead organic matter.", 'maximum_marks': 2, 'marks_awarded': 1.5}, {'section': 'B', 'question_number': '26', 'question_text': 'In the electrolysis of water:\na) Why is it that the volume of gas collected on one electrode is two times that of the other electrode?\nb) What would happen if dilute $\\mathrm{H}_{2} \\mathrm{SO}_{4}$ is not added to water?', 'student_answer_text': 'a) The volume of gas collected in one electrode is two times the other because the Hydrogen ions concentration is more.\nb) H2SO4 is an acid. If it is not added to water, electrolytes of water does not take place as electricity is conducted in the presence of Hydrogen ion.', 'actual_answer': 'a) Water ($\\mathrm{H_2O}$) is composed of two parts hydrogen and one part oxygen. During electrolysis, water decomposes into hydrogen gas ($\\mathrm{H_2}$) and oxygen gas ($\\mathrm{O_2}$) in a 2:1 molar ratio, according to the equation $2\\mathrm{H_2O}(l) \\rightarrow 2\\mathrm{H_2}(g) + \\mathrm{O_2}(g)$. Therefore, the volume of hydrogen gas collected is twice that of oxygen gas.\nb) Pure water is a poor conductor of electricity. Dilute $\\mathrm{H_2SO_4}$ (an acid) is added to water to make it acidic, which increases the concentration of ions ($\\mathrm{H^+}$ and $\\mathrm{SO_4^{2-}}$). These ions conduct electricity, facilitating the electrolysis process. Without the acid, electrolysis would be very slow or practically not occur.', 'feedback': "For part (a), your reason for the 2:1 gas volume ratio is incorrect; it's due to the chemical composition of water (H₂O). For part (b), you correctly stated that $\\mathrm{H_2SO_4}$ provides ions for conduction, but use the term 'electrolysis' instead of 'electrolytes'.", 'maximum_marks': 2, 'marks_awarded': 1}, {'section': 'C', 'question_number': '27', 'question_text': 'Out of the two hydrochloric acid and acetic acid, which one is considered a strong acid and why? Write the name and molecular formulae of one more strong acid.', 'student_answer_text': 'Hydrochloric acid is considered a strong acid as it is a hydrocarbon ion concentration.\n\nSulphuric acid is the more strong acid. Molecular formulae: H₂SO₄.', 'actual_answer': 'Hydrochloric acid (HCl) is considered a strong acid because it completely ionizes/dissociates in water to produce a high concentration of $\\mathrm{H^+}$ (or $\\mathrm{H_3O^+}$) ions. Acetic acid (CH₃COOH) is a weak acid as it only partially dissociates. Another strong acid is Nitric acid ($\\mathrm{HNO_3}$).', 'feedback': "You correctly identified hydrochloric acid as a strong acid and gave a correct example (sulphuric acid with formula). However, your reason for HCl being strong, 'hydrocarbon ion concentration', is incorrect; it should be 'high concentration of hydronium ions' due to complete ionization.", 'maximum_marks': 3, 'marks_awarded': 2}, {'section': 'C', 'question_number': '28', 'question_text': 'Give reasons for the following:\n(a) Ionic compounds in general have high melting and boiling points.\n(b) Highly reactive metals cannot be obtained from their oxides by heating them with carbon.\n(c) Copper containers get a green coat when left exposed to air in the rainy season\nOR\n(a) What is meant by reactivity series?\n(b) What is meant by thermit reaction? Write one suitable equation for the same.', 'student_answer_text': 'a) The series in which the metals are added from highly reactive metal to low reactive metal is called steel in their decreasing order is called steel in steel in steel.\nb) The reaction iron (II) or oxide and aluminium which is used to join ordinary or traceable and cracked machine parts is called thermit reaction.\n$$3Fe + Al_2 \\rightarrow Fe_3Al_2$$', 'actual_answer': 'a) The reactivity series is a list of metals arranged in decreasing order of their reactivity. A more reactive metal can displace a less reactive metal from its salt solution.\nb) The thermit reaction is a highly exothermic redox reaction involving a metal oxide (usually iron(III) oxide) and a more reactive metal (usually aluminium) powder. It is used for welding railway tracks or cracked machine parts.\nEquation: $\\mathrm{Fe_2O_3}(s) + 2\\mathrm{Al}(s) \\xrightarrow{heat} \\mathrm{Al_2O_3}(s) + 2\\mathrm{Fe}(l) + \\text{Heat}$', 'feedback': 'For part (a), your definition of reactivity series is conceptually correct, but the wording is repetitive. For part (b), your definition of the thermit reaction is good, but the chemical equation provided is incorrect.', 'maximum_marks': 3, 'marks_awarded': 1.5}, {'section': 'C', 'question_number': '29', 'question_text': 'What is the probability of a girl or a boy being born in a family? Justify', 'student_answer_text': 'The probability of a girl or a boy being born in a family is 50%. This is because the x chromosome can either fuse with x or a chromosome or 4 chromosomes of father.', 'actual_answer': 'The probability of a girl or a boy being born in a family is 50% for each.\nJustification: Human females have two X chromosomes (XX), and males have one X and one Y chromosome (XY). During reproduction, the female produces only X gametes (ova), while the male produces two types of gametes: X-sperm and Y-sperm in equal proportions. If an X-sperm fertilizes the ovum, the child will be a girl (XX). If a Y-sperm fertilizes the ovum, the child will be a boy (XY). Since the chances of an X-sperm or Y-sperm fertilizing the ovum are equal, the probability of having a boy or a girl is 50%.', 'feedback': "You correctly stated the probability (50%). However, your justification regarding chromosome fusion is unclear and incorrect. The probability depends on the father's X or Y chromosome fertilizing the ovum.", 'maximum_marks': 3, 'marks_awarded': 1}, {'section': 'C', 'question_number': '30', 'question_text': 'Why are we advised to take iodised salt in our diet by doctors?', 'student_answer_text': 'We are advised to take iodized salt in our diet by doctors because it maintains the iodine level in our body. Lack of iodine can cause goitre.', 'actual_answer': 'Doctors advise taking iodised salt because iodine is essential for the thyroid gland to produce thyroxin hormone. Thyroxin regulates carbohydrate, protein, and fat metabolism in the body, which is crucial for growth and development. A deficiency of iodine in the diet can lead to a condition called goitre, characterized by a swollen neck.', 'feedback': 'Your answer correctly links iodised salt to maintaining iodine levels and preventing goitre. This is a good, concise explanation.', 'maximum_marks': 3, 'marks_awarded': 3}, {'section': 'C', 'question_number': '31', 'question_text': 'A 3 cm tall object is placed 18 cm in front of a concave mirror of focal length 12 cm . At what distance from the mirror should a screen be placed to see a sharp image of the object on the screen. Also calculate the height of the image formed.', 'student_answer_text': 'U = -18 cm\nf = -12 cm\n$$ \\frac{1}{f} = \\frac{1}{V} - \\frac{1}{U} $$\n$$ \\frac{1}{-12} = \\frac{1}{V} - \\frac{1}{-18} $$\n$$ \\frac{1}{-12} + \\frac{1}{18} = \\frac{1}{V} $$\n$$ \\frac{-1 \\times 3 + 1 \\times 2}{36} = \\frac{1}{V} $$\n$$ \\frac{-3 + 2}{36} = \\frac{1}{V} $$\n$$ \\frac{-1}{36} = \\frac{1}{V} $$\n$$ V = -36 $$', 'actual_answer': "Given: Object height (h) = 3 cm, Object distance (u) = -18 cm, Focal length (f) = -12 cm (for concave mirror).\nUsing mirror formula: $1/f = 1/v + 1/u$\n$1/(-12) = 1/v + 1/(-18)$\n$1/v = 1/(-12) - 1/(-18) = -1/12 + 1/18$\n$1/v = (-3 + 2)/36 = -1/36$\n$v = -36 \\text{ cm}$\nThe screen should be placed at 36 cm in front of the mirror. The negative sign indicates a real and inverted image.\nMagnification (m) = $-v/u = h'/h$\n$m = -(-36)/(-18) = -2$\n$h' = m \\times h = -2 \\times 3 \\text{ cm} = -6 \\text{ cm}$\nThe height of the image formed is 6 cm. The negative sign indicates that the image is inverted.", 'feedback': 'You correctly calculated the position of the image (v = -36 cm). However, you did not calculate the height of the image formed, which was also required by the question.', 'maximum_marks': 3, 'marks_awarded': 1.5}, {'section': 'C', 'question_number': '32', 'question_text': 'The flow of current in a circular loop of wire creates a magnetic field at its center.\n[DIAGRAM: A circular loop of wire with current flowing, generating magnetic field lines.]\nHow the existence of this magnetic field be detected? State the rule which helps to predict the direction of this magnetic field.', 'student_answer_text': "The existence of this magnetic field can be detected using a compass.\n\nRule: Maxwell's weight hand thumb rule:\n\nImagine that you are holding a current carrying straight condo conductor. If the thumb faces in the direction of a magnet, then your fingers will wrap around the conductor in the direction of the magnetic field lines.", 'actual_answer': "The existence of the magnetic field can be detected using a magnetic compass. The compass needle will deflect when placed near the current-carrying circular loop.\nRule: **Maxwell's Right-Hand Thumb Rule** (or Right-Hand Thumb Rule).\nFor a current-carrying circular loop: If we curl the palm of our right hand in the direction of the current through the circular loop, the direction of the extended thumb will give the direction of the magnetic field lines inside the loop (which is uniform and perpendicular to the plane of the loop).", 'feedback': 'You correctly identified using a compass for detection. However, you misnamed the rule and described it for a straight conductor, not specifically for the magnetic field inside a circular loop.', 'maximum_marks': 3, 'marks_awarded': 1.5}, {'section': 'C', 'question_number': '33', 'question_text': 'Find the total resistance and also the current drawn from the battery by the network of four resistors as shown in the figure.\n[DIAGRAM: A circuit diagram showing two parallel pairs of 10 Ohm resistors connected in series, powered by a 3V battery.]', 'student_answer_text': 'R = ?\n[DIAGRAM: A hand-drawn circuit diagram similar to the question paper, showing two parallel pairs of 10 Ohm resistors connected in series to a 3V battery.]\nR1 and R2 are connected in parallel.\n$$ \\frac{1}{R_p} = \\frac{1}{10} + \\frac{1}{10} $$\n$$ \\frac{1}{R_p} = \\frac{2}{10} $$\n$$ R_p = 5 \\mu $$\nR3 and R4 are connected in parallel.\n$$ \\frac{1}{R_p} = \\frac{1}{10} + \\frac{5 \\mu}{1} $$\n[Crossed out calculation]\nTotal resistance: Rp + Rp = 5 + 1.5 = 10μ.\n\n(i) Current: T\n$$ R=\\frac{1}{T} $$\n$$ 10=\\frac{3}{T} $$\n$$ 10I=3 $$\n$$ T=\\frac{3}{10} $$\n$$ T=0.3 A $$', 'actual_answer': 'For the first pair of 10Ω resistors in parallel:\n$1/R_{p1} = 1/10 + 1/10 = 2/10$\n$R_{p1} = 10/2 = 5 \\Omega$\nFor the second pair of 10Ω resistors in parallel:\n$1/R_{p2} = 1/10 + 1/10 = 2/10$\n$R_{p2} = 10/2 = 5 \\Omega$\nTotal resistance ($\\mathrm{R_{total}}$) in the circuit:\n$\\mathrm{R_{total}} = R_{p1} + R_{p2} = 5 \\Omega + 5 \\Omega = 10 \\Omega$\nCurrent drawn from the battery (I):\n$I = V / \\mathrm{R_{total}} = 3 \\text{ V} / 10 \\Omega = 0.3 \\text{ A}$', 'feedback': "You correctly calculated the equivalent resistance for the first parallel combination and the final current. However, there's a unit error (μ instead of Ω) and an incorrect intermediate step for the second parallel resistance calculation, even though the final total resistance value was correct.", 'maximum_marks': 3, 'marks_awarded': 1.5}, {'section': 'D', 'question_number': '34', 'question_text': '(a) Write the names and structures of (i) a ketone, and (ii) an aldehyde with three carbon atoms in their molecules.\n(b) List two differences between saturated and unsaturated hydrocarbons and give one example for each.', 'student_answer_text': 'a) Three carbon atom: propane\n?) ketone:\n$$ \\begin{aligned} & H-C-C-C-H \\\\ & \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\text{O} \\\\ & \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad || \\\\ & \\text{Name: Propanone} \\end{aligned} $$\n(17) Aldehyde\n$$ \\begin{aligned} & \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\text{O} \\\\ & \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad \\quad || \\\\ & H-C-C-C-H \\\\ & \\text{Name: Propenal.} \\end{aligned} $$\nb) Saturated Unsaturated\n* Sth: These are: # These are: double or\nsingle bonded triple bonded.\n* Brives clean: # Grives: Hellnir: flame\nflame when burnt when burnt.\n* Ex = Methane, Ethane. * Ex: FtBene, Ethyne.', 'actual_answer': 'a) (i) Ketone with three carbon atoms:\n    Name: Propanone (or Acetone)\n    Structure: $\\mathrm{CH_3-CO-CH_3}$\n          $\\mathrm{H \\quad O \\quad H}$\n          $\\mathrm{| \\quad || \\quad |}$\n          $\\mathrm{H-C-C-C-H}$\n          $\\mathrm{| \\quad \\quad |}$\n          $\\mathrm{H \\quad \\quad H}$\n(ii) Aldehyde with three carbon atoms:\n    Name: Propanal (or Propionaldehyde)\n    Structure: $\\mathrm{CH_3-CH_2-CHO}$\n          $\\mathrm{H \\quad H \\quad O}$\n          $\\mathrm{| \\quad | \\quad ||}$\n          $\\mathrm{H-C-C-C-H}$\n          $\\mathrm{| \\quad |}$\n          $\\mathrm{H \\quad H}$\nb) Differences between Saturated and Unsaturated Hydrocarbons:\n| Feature | Saturated Hydrocarbons | Unsaturated Hydrocarbons |\n|---|---|---|\n| Bond Type | Contain only single C-C bonds. | Contain at least one double (C=C) or triple (C$\\equiv$C) bond. |\n| Reactivity | Less reactive (undergo substitution reactions). | More reactive (undergo addition reactions). |\n| Flame (burning)| Burn with a clean, blue flame. | Burn with a sooty, yellow flame. |\nExamples:\nSaturated: Methane ($\\mathrm{CH_4}$), Ethane ($\\mathrm{C_2H_6}$)\nUnsaturated: Ethene ($\\mathrm{C_2H_4}$), Ethyne ($\\mathrm{C_2H_2}$)', 'feedback': "For part (a), your name and structure for the ketone are correct. However, for the aldehyde, both the name ('Propenal' instead of 'Propanal') and the structure (you drew a ketone again) are incorrect. For part (b), your differences and examples are generally correct, though 'Hellnir' for sooty flame is a misspelling and 'FtBene' for Ethene is also a misspelling.", 'maximum_marks': 5, 'marks_awarded': 4}, {'section': 'D', 'question_number': '35', 'question_text': '(i) A security mirror used in a big showroom has radius of curvature 5 m . If a customer is standing at a distance of 20 m from the cash counter, find the position, nature and size of the image formed in the security mirror.\n(ii) Neha visited a dentist in his clinic. She observed that the dentist was holding an instrument fitted with a mirror. State the nature of this mirror and reason for its use in the instrument used by dentist\nOR\nRishi went to a palmist to show his palm. The palmist used a special lens for this purpose.\n(i) State the nature of the lens and the reason for its use.\n(ii) Where should the palmist place/hold the lens so as to have a real and magnified image of an object?\n(iii) If the focal length of this lens is 10 cm and the lens is held at a distance of 5 cm from the palm, use the lens formula to find the position and size of the image.', 'student_answer_text': '9) $R=5m$\n$0=20 \\mathrm{~m}$\n$R_{2}$\n$R=2f$\n$f=R$\n$f=5 \\sqrt{1}$\n$f/4$\n$1 \\quad \\frac{1}{V} \\frac{1}{2}$\n$f1=1 \\quad 2$\n$f5 \\frac{1}{V} \\frac{2}{20}$\n$\\frac{2}{5} \\frac{1}{V} \\frac{5}{20}$\n$\\frac{2+1}{5 \\times 4} \\frac{1}{20 \\times 1} \\frac{1}{V}$\n$8+1=1$\n$9 \\quad \\frac{9}{20}=1$\n$20=V$\n$2.22 \\mathrm{~cm}=V$\n36) The mirror used by dentists is\nconcave mirror.\nThe reason for this is of concave mirror gives a wider field of view.', 'actual_answer': '(i) For a security mirror (convex mirror):\n    Radius of curvature (R) = +5 m\n    Focal length (f) = R/2 = +5/2 = +2.5 m\n    Object distance (u) = -20 m (customer is in front of the mirror)\n    Using mirror formula: $1/f = 1/v + 1/u$\n    $1/2.5 = 1/v + 1/(-20)$\n    $1/v = 1/2.5 + 1/20 = 0.4 + 0.05 = 0.45$\n    $v = 1/0.45 = 20/9 \\approx +2.22 \\text{ m}$\n    Position: The image is formed at 2.22 m behind the mirror.\n    Nature: Virtual and erect.\n    Magnification (m) = $-v/u = -(+2.22)/(-20) = +0.111$.\n    Size: The image is diminished (much smaller than the object).\n(ii) The dentist uses a **concave mirror**.\n    Reason: A concave mirror, when held close to the tooth (object placed between its pole and principal focus), forms a **magnified and erect image** of the tooth. This allows the dentist to see a larger, clearer view of the tooth for examination.', 'feedback': "For part (i), your calculation for image position is incorrect, and the unit is wrong (cm instead of m). For part (ii), you correctly identified the concave mirror, but the reason given ('wider field of view') is incorrect; it should be to obtain a magnified image.", 'maximum_marks': 5, 'marks_awarded': 2.5}, {'section': 'D', 'question_number': '36', 'question_text': 'Given below are certain situations. Analyse and describe its possible impact on a person.\nA) Testes of a male boy are not able to descend into the scrotum during his embryonic development.\nB) Vas deferens of a man is plugged\nC) Prostate and seminal vesicles are not functional\nD) Egg is not fertilised in a human female\nE) Placenta does not attach to the uterus optimally\nOR\na) A doctor has advised Ram to reduce sugar intake and do regular exercise after checking his blood test results\ni. Which disease is Ram suffering from?\nii. Name the hormone responsible for this disease and the organ producing the hormone.\nb) Which hormone is responsible for changes noticed in males and females during puberty\nc) Which hormone is responsible for rapid cell division in plants?\nd) Which plant hormone inhibits growth?', 'student_answer_text': '(T) Ram is suffering from diabetes.\n(Ti) The hormone responsible for this is insulin. Lack of insulin causes diabetes. For insulin is produced by Pancreas.\n(Tii) Testosterone in males and Oestrogen in females are responsible for the changes noticed in during puberty.\n(iv) Cytokinin is responsible for rapid cell division.\n(v) Abscisic acid inhibits growth in plants.', 'actual_answer': 'a) i. Ram is suffering from **Diabetes**.\n   ii. The hormone responsible for this disease is **Insulin**, which is produced by the **Pancreas**.\nb) **Testosterone** (in males) and **Estrogen** (in females) are responsible for the changes noticed during puberty.\nc) **Cytokinin** is responsible for rapid cell division in plants.\nd) **Abscisic acid** is the plant hormone that inhibits growth.', 'feedback': 'All parts of your answer are correct and well-explained.', 'maximum_marks': 5, 'marks_awarded': 5}, {'section': 'E', 'question_number': '37', 'question_text': 'Pea plants can have smooth seeds or wrinkled seeds. One of the phenotypes is completely dominant over the other. A farmer decides to pollinate one flower of a plant with smooth seeds using pollen from a plant with wrinkled seeds. The resulting pea pod has all smooth seeds.\na. Which of the two traits is dominant?\nb. What would be the ratio if the F1 plants are selfed?\nc. Write the percentage of heterozygous smooth and homozygous smooth plants obtained in F2 generation.\nOR \nC. Write the genotype of the parental plants.', 'student_answer_text': 'a) Smooth & draft is dominant.\nb) 9:3:3:1\nc) 55 x 95\nd)\ne) 3:1', 'actual_answer': 'a) The **smooth seed trait** is dominant, as all F1 seeds were smooth.\nb) If the F1 plants (all heterozygous smooth, Ss) are selfed, the F2 generation will show a **phenotypic ratio of 3 (Smooth) : 1 (Wrinkled)** and a genotypic ratio of 1 (SS) : 2 (Ss) : 1 (ss).\nc) In the F2 generation (from selfing F1 plants):\n    Percentage of heterozygous smooth plants (Ss) = 50%\n    Percentage of homozygous smooth plants (SS) = 25%\nOR\nc) Genotype of the parental plants:\n    Smooth seeds plant: Homozygous dominant (SS)\n    Wrinkled seeds plant: Homozygous recessive (ss)', 'feedback': 'For part (a), your answer is correct. For part (b), the ratio for F1 selfing (monohybrid cross) is 3:1 (phenotypic), not 9:3:3:1. Part (c) is unclear and incorrect as it asks for percentages, not ratios or unrelated numbers.', 'maximum_marks': 4, 'marks_awarded': 1}, {'section': 'E', 'question_number': '38', 'question_text': 'When electric current flows through the circuit this electrical energy is used in two ways, some part is used for doing work and remaining may be expended in the form of heat. We can see, in mixers after using it for long time it become more hot, fans also become hot after continuous use. This type of effect of electric current is called as heating effect of electric current. The heating effect is also used for producing light. In case of electric bulb, the filament produces more heat energy which is emitted in the form of light. And hence filament are made from tungsten which is having high melting point. In case of electric circuit, this heating effect is used to protect the electric circuit from damage.\na) What is the commercial unit of energy?\nb) Why tungsten is used in electric bulbs?\nc) How heating effect works to protect electric circuit?\nOR\nC. If a bulb is working for 1 hour at a voltage of 200 V and the current is 1 A then what is the power of the bulb?', 'student_answer_text': 'a) The commercial unit of energy is 220 V.\nb) Tungsten has high melting point and produces more heat energy.\nc) Heating at effect prevents overloading and thus prevents electric circuit.', 'actual_answer': 'a) The commercial unit of energy is **kilowatt-hour (kWh)**.\nb) Tungsten is used in electric bulbs because it has a **very high melting point** (approx. 3422°C) and can glow at high temperatures without melting. It also has high resistivity, which helps it to heat up quickly and emit light.\nc) The heating effect of electric current is used in **fuses** to protect electric circuits. A fuse wire has a low melting point. When an excessive current (due to overloading or short-circuiting) flows through the circuit, the fuse wire heats up rapidly and melts, breaking the circuit and preventing damage to appliances and wiring.', 'feedback': 'For part (a), your answer for the commercial unit of energy is incorrect; it is kilowatt-hour (kWh), not voltage. For parts (b) and (c), your answers are correct.', 'maximum_marks': 4, 'marks_awarded': 3}, {'section': 'E', 'question_number': '39', 'question_text': 'An organic compound $A$ is used as a preservative in pickles and has molecular formulae $\\mathrm{C}_{7} \\mathrm{H}_{7} \\mathrm{O}_{2}$. This compound reacts with ethanol to form a sweet smelling compound B.\na) Determine the compounds $A$ and $B$. (2)\nb) i) Write the chemical equation for its reaction of $A$ with ethanol to form compound $B$ (1)\nii) Write any one use of compound $B$ (1)\nOR\nb) i) Which gas is produced when A reacts with baking soda? (1)\nii) How can vinegar be obtained from compound A? (1)', 'student_answer_text': 'a) $A \\rightarrow$ Ethanol acid\n$B \\rightarrow$ Ester\nb) $\\mathrm{CH C_2H_5O_2 + C_2H_5OH \\rightarrow 2C_2H_4 + 2H_2}$\nc) Ester is used in peryume as to give a pleasant smell', 'actual_answer': 'a) Compound A: Given the context (preservative in pickles, reacts with ethanol to form a sweet-smelling compound B), A is a carboxylic acid. Although the molecular formula $\\mathrm{C_7H_7O_2}$ is unusual for a simple carboxylic acid (benzoic acid is $\\mathrm{C_7H_6O_2}$), it strongly suggests an aromatic carboxylic acid like benzoic acid, which is a common preservative. Compound B: Ester (specifically, ethyl benzoate if A is benzoic acid).\nb) i) Chemical equation (assuming A is Benzoic acid, $\\mathrm{C_6H_5COOH}$):\n    $\\mathrm{C_6H_5COOH} + \\mathrm{CH_3CH_2OH} \\xrightarrow{\\text{Conc. } H_2SO_4} \\mathrm{C_6H_5COOCH_2CH_3} + \\mathrm{H_2O}$\n    (Benzoic acid + Ethanol $\\rightarrow$ Ethyl benzoate + Water)\nii) Use of compound B (Ester): Esters are used in **perfumes** and as **flavouring agents** because of their sweet, pleasant smell.', 'feedback': "For part (a), you correctly identified B as an ester. However, your identification of A as 'Ethanol acid' is incorrect in name and does not match the given molecular formula. For part (b)(i), your chemical equation is completely incorrect. For part (b)(ii), the use of esters is correctly stated.", 'maximum_marks': 4, 'marks_awarded': 1.5}]}
                    # result = response.json()
                    result = response
                    
                    
                    st.success("Answer sheet processed successfully!")
                    answer_sheet = result.get("response", [])
                    display_answer_data = []
                    for a in answer_sheet:
                        try:
                            # Ensure all numeric fields are properly converted
                            max_marks = float(a["maximum_marks"]) if isinstance(a["maximum_marks"], (int, float)) else int(float(str(a["maximum_marks"])))
                            awarded_marks = float(a["marks_awarded"]) if isinstance(a["marks_awarded"], (int, float)) else int(float(str(a["marks_awarded"])))
                            
                            display_answer_data.append({
                                "section": str(a.get("section", "")),
                                "question_number": str(a.get("question_number", "")),
                                "question_text": str(a.get("question_text", "")),
                                "student_answer_text": str(a.get("student_answer_text", "")),
                                "actual_answer": str(a.get("actual_answer", "")),
                                "feedback": str(a.get("feedback", "")),
                                "maximum_marks": max_marks,
                                "marks_awarded": awarded_marks
                            })
                        except (ValueError, TypeError) as e:
                            st.error(f"Error processing question data: {e}")
                            continue

                    if not display_answer_data:
                        st.error("No valid question data found")

                    a_df = pd.DataFrame(display_answer_data)

                    # Calculate totals
                    # max_marks_total = a_df['maximum_marks'].sum()
                    # marks_awarded_total = a_df['marks_awarded'].sum()

                    # # Create totals row
                    # totals_row = pd.DataFrame({
                    #     "section": ["📊"],
                    #     "question_number": [""],
                    #     "question_text": [""],
                    #     "student_answer_text": [""],
                    #     "actual_answer": ["**TOTAL SCORE**"],
                    #     "feedback": [""],
                    #     "maximum_marks": [f"**{max_marks_total}**"],
                    #     "marks_awarded": [f"**{marks_awarded_total}**"]
                    # })

                    # # Add totals row to the DataFrame
                    # a_df = pd.concat([a_df, totals_row], ignore_index=True)

                    # # Display the DataFrame with totals
                    # st.dataframe(a_df, use_container_width=True)

                    # # Optional: Display summary statistics
                    # col1, col2, col3 = st.columns(3)
                    # with col1:
                    #     st.metric("Total Questions", len(answer_sheet))
                    # with col2:
                    #     st.metric("Maximum Marks", max_marks_total)
                    # with col3:
                    #     st.metric("Marks Awarded", marks_awarded_total)
                        
                    # # Optional: Calculate percentage
                    # if max_marks_total > 0:
                    #     percentage = (marks_awarded_total / max_marks_total) * 100
                    #     st.metric("Score Percentage", f"{percentage:.2f}%")
                    # st.json(result)
                    # ✅ FIX: Keep as FLOAT values (not int)
                    a_df['maximum_marks'] = pd.to_numeric(a_df['maximum_marks'], errors='coerce').fillna(0.0)
                    a_df['marks_awarded'] = pd.to_numeric(a_df['marks_awarded'], errors='coerce').fillna(0.0)

                    # Calculate totals - keep as float
                    max_marks_total = float(a_df['maximum_marks'].sum())
                    marks_awarded_total = float(a_df['marks_awarded'].sum())
                    percentage = round((marks_awarded_total / max_marks_total) * 100, 2) if max_marks_total > 0 else 0
                    
                    # Calculate efficiency safely
                    a_df['efficiency'] = a_df.apply(lambda row: 
                        round((row['marks_awarded'] / row['maximum_marks']) * 100, 2) if row['maximum_marks'] > 0 else 0, 
                        axis=1
                    )

                    # === CREATIVE VISUALIZATIONS START ===
                    st.markdown("---")
                    st.header("🎯 Creative Performance Analytics")

                    # Import plotly here to avoid import errors if not installed
                    try:
                        import plotly.graph_objects as go
                    except ImportError:
                        st.error("Please install plotly: `pip install plotly`")

                    # Create tabs for different creative visualizations
                    tab1, tab2, tab3, tab4, tab5 = st.tabs([
                        "🌟 Performance Galaxy", 
                        "🎪 Score Carnival", 
                        "🏆 Achievement Radar", 
                        "🎭 Story Dashboard",
                        "📋 Detailed Results"
                    ])

                    with tab1:
                        st.subheader("🌟 Performance Galaxy")
                        
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            # 3D Bubble Chart - Questions as planets in performance galaxy
                            fig_galaxy = go.Figure()
                            
                            # Create bubbles for each question
                            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8']
                            
                            for i, row in a_df.iterrows():
                                fig_galaxy.add_trace(go.Scatter(
                                    x=[i+1],
                                    y=[row['efficiency']],
                                    mode='markers+text',
                                    marker=dict(
                                        size=max(row['maximum_marks'] * 15, 20),
                                        color=colors[i % len(colors)],
                                        opacity=0.7,
                                        line=dict(width=2, color='white')
                                    ),
                                    text=f"Q{i+1}<br>{row['marks_awarded']:.1f}/{row['maximum_marks']:.1f}",
                                    textposition="middle center",
                                    textfont=dict(size=10, color='white'),
                                    hovertemplate=f"<b>Question {i+1}</b><br>" +
                                                f"Section: {row['section']}<br>" +
                                                f"Score: {row['marks_awarded']:.1f}/{row['maximum_marks']:.1f}<br>" +
                                                f"Efficiency: {row['efficiency']:.1f}%<br>" +
                                                "<extra></extra>",
                                    showlegend=False
                                ))
                            
                            fig_galaxy.update_layout(
                                title="🚀 Each planet represents a question (size = max marks, height = efficiency)<br>",
                                xaxis_title="Question Number",
                                yaxis_title="Efficiency (%)",
                                showlegend=True,
                                height=400
                            )
                            
                            # Add performance zones
                            fig_galaxy.add_hline(y=90, line_dash="dash", line_color="gold", 
                                            annotation_text="Excellence Zone (90%+)")
                            fig_galaxy.add_hline(y=75, line_dash="dash", line_color="silver", 
                                            annotation_text="Good Zone (75%+)")
                            fig_galaxy.add_hline(y=50, line_dash="dash", line_color="orange", 
                                            annotation_text="Average Zone (50%+)")
                            
                            st.plotly_chart(fig_galaxy, use_container_width=True)
                        
                        with col2:
                            # Performance orbit status
                            st.markdown("### 🚀 Orbit Status")
                            
                            excellent_count = len(a_df[a_df['efficiency'] >= 90])
                            good_count = len(a_df[(a_df['efficiency'] >= 75) & (a_df['efficiency'] < 90)])
                            average_count = len(a_df[(a_df['efficiency'] >= 50) & (a_df['efficiency'] < 75)])
                            poor_count = len(a_df[a_df['efficiency'] < 50])
                            
                            st.metric("🌟 Excellence Orbit", f"{excellent_count} questions")
                            st.metric("⭐ Good Orbit", f"{good_count} questions") 
                            st.metric("🔸 Average Orbit", f"{average_count} questions")
                            st.metric("🔻 Needs Boost", f"{poor_count} questions")

                    with tab2:
                        st.subheader("🎪 Score Carnival - Interactive Performance Show")
                        
                        # Carnival-style performance meter
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            # Ferris wheel style circular progress
                            fig_ferris = go.Figure(go.Indicator(
                                mode = "gauge+number+delta",
                                value = percentage,
                                domain = {'x': [0, 1], 'y': [0, 1]},
                                title = {'text': "🎡 Performance Ferris Wheel"},
                                delta = {'reference': 80, 'valueformat': '.1f'},
                                gauge = {
                                    'axis': {'range': [None, 100]},
                                    'bar': {'color': "darkblue"},
                                    'steps': [
                                        {'range': [0, 50], 'color': "lightgray"},
                                        {'range': [50, 80], 'color': "yellow"},
                                        {'range': [80, 100], 'color': "green"}
                                    ],
                                    'threshold': {
                                        'line': {'color': "red", 'width': 4},
                                        'thickness': 0.75,
                                        'value': 90
                                    }
                                }
                            ))
                            fig_ferris.update_layout(height=300)
                            st.plotly_chart(fig_ferris, use_container_width=True)
                        
                        with col2:
                            # Carnival game scoring
                            st.markdown("### 🎯 Carnival Games Scores")
                            
                            # Ring toss representation
                            total_questions = len(a_df)
                            perfect_hits = len(a_df[a_df['efficiency'] == 100])
                            good_hits = len(a_df[a_df['efficiency'] >= 75])
                            
                            st.markdown(f"""
                            **🎯 Ring Toss Results:**
                            - 🎪 Total Throws: {total_questions}
                            - 🏆 Perfect Bulls-eye: {perfect_hits}
                            - 🎯 Good Hits: {good_hits}
                            - 🎪 Success Rate: {(good_hits/total_questions)*100:.1f}%
                            """)
                        
                        with col3:
                            # Cotton candy performance
                            st.markdown("### 🍭 Sweet Success Meter")
                            
                            sweetness_score = percentage / 100
                            cotton_candy_levels = ["😢", "😐", "🙂", "😊", "🤩"]
                            level_idx = min(int(sweetness_score * 5), 4)
                            
                            st.markdown(f"""
                            **Your Performance Sweetness:**
                            
                            {cotton_candy_levels[level_idx]} **Level {level_idx + 1}**
                            
                            *Sweetness Level: {percentage:.1f}%*
                            """)

                    with tab3:
                        st.subheader("🏆 Achievement Radar - Multi-dimensional Analysis")
                        
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            # Calculate different performance metrics
                            consistency = max(0, 100 - a_df['efficiency'].std()) if len(a_df) > 1 else 100
                            accuracy = percentage
                            completion_rate = (len(a_df[a_df['marks_awarded'] > 0]) / len(a_df)) * 100
                            excellence_rate = (len(a_df[a_df['efficiency'] >= 90]) / len(a_df)) * 100
                            
                            # Radar chart data
                            categories = ['Accuracy', 'Consistency', 'Completion', 'Excellence', 'Overall']
                            values = [accuracy, consistency, completion_rate, excellence_rate, percentage]
                            
                            fig_radar = go.Figure()
                            
                            fig_radar.add_trace(go.Scatterpolar(
                                r=values,
                                theta=categories,
                                fill='toself',
                                name='Your Performance',
                                line_color='rgb(255, 99, 132)',
                                fillcolor='rgba(255, 99, 132, 0.3)'
                            ))
                            
                            fig_radar.update_layout(
                                polar=dict(
                                    radialaxis=dict(
                                        visible=True,
                                        range=[0, 100]
                                    )),
                                title="🎯 Performance Radar Analysis",
                                showlegend=False,
                                height=400
                            )
                            
                            st.plotly_chart(fig_radar, use_container_width=True)
                        
                        with col2:
                            st.markdown("### 🏅 Achievement Badges")
                            
                            # Award badges based on performance
                            badges = []
                            
                            if percentage >= 95:
                                badges.append("🥇 Gold Medal - Excellence")
                            elif percentage >= 85:
                                badges.append("🥈 Silver Medal - Outstanding")
                            elif percentage >= 75:
                                badges.append("🥉 Bronze Medal - Good Work")
                            
                            if consistency >= 80:
                                badges.append("🎯 Consistency Champion")
                            
                            if perfect_hits > 0:
                                badges.append("💎 Perfect Score Badge")
                            
                            if completion_rate == 100:
                                badges.append("✅ 100% Completion Badge")
                            
                            for badge in badges:
                                st.success(badge)
                            
                            if not badges:
                                st.info("🌟 Keep practicing for more badges!")

                    with tab4:
                        st.subheader("🎭 Your Performance Story")
                        
                        # Story timeline chart
                        fig_story = go.Figure()
                        
                        # Create a journey line
                        x_vals = list(range(1, len(a_df) + 1))
                        y_vals = a_df['efficiency'].tolist()
                        
                        # Add the performance journey line
                        fig_story.add_trace(go.Scatter(
                            x=x_vals,
                            y=y_vals,
                            mode='lines+markers',
                            name='Your Journey',
                            line=dict(color='purple', width=3),
                            marker=dict(size=10, color=y_vals, colorscale='Viridis'),
                            hovertemplate="Question %{x}<br>Performance: %{y:.1f}%<extra></extra>"
                        ))
                        
                        # Add story annotations for interesting points
                        if len(a_df) > 1:
                            max_performance_idx = a_df['efficiency'].idxmax()
                            min_performance_idx = a_df['efficiency'].idxmin()
                            
                            fig_story.add_annotation(
                                x=max_performance_idx + 1,
                                y=a_df.loc[max_performance_idx, 'efficiency'],
                                text="🌟 Peak Performance!",
                                showarrow=True,
                                arrowhead=2
                            )
                            
                            if min_performance_idx != max_performance_idx:
                                fig_story.add_annotation(
                                    x=min_performance_idx + 1,
                                    y=a_df.loc[min_performance_idx, 'efficiency'],
                                    text="💪 Growth Opportunity",
                                    showarrow=True,
                                    arrowhead=2
                                )
                        
                        fig_story.update_layout(
                            title="📖 Your Performance Story - The Journey",
                            xaxis_title="Question Sequence",
                            yaxis_title="Performance (%)",
                            showlegend=False,
                            height=400
                        )
                        
                        st.plotly_chart(fig_story, use_container_width=True)

                    with tab5:
                        st.subheader("📋 Detailed Results & Analysis")

                        # Add efficiency string column for display
                        display_df = a_df.copy()
                        display_df['efficiency_str'] = display_df['efficiency'].apply(lambda x: f"{x:.1f}%")

                        # ✅ SAFE TOTALS ROW CREATION - with FLOAT formatting
                        totals_data = {
                            "section": "📊 TOTAL",
                            "question_number": "",
                            "question_text": "",
                            "student_answer_text": "",
                            "actual_answer": "**TOTAL SCORE**",
                            "feedback": "",
                            "maximum_marks": max_marks_total,  # Keep as float
                            "marks_awarded": marks_awarded_total,  # Keep as float
                            "efficiency": percentage,
                            "efficiency_str": f"**{percentage:.1f}%**"
                        }

                        # Create totals row as a single row DataFrame
                        totals_row = pd.DataFrame([totals_data])

                        # ✅ SAFE CONCATENATION - ensure same columns
                        final_df = pd.concat([display_df, totals_row], ignore_index=True)

                        # Display results table with proper float formatting
                        st.dataframe(
                            final_df[[
                                'section', 'question_number', 'question_text', 'student_answer_text', 
                                'actual_answer', 'maximum_marks', 'marks_awarded', 'efficiency_str', 'feedback'
                            ]],
                            use_container_width=True,
                            column_config={
                                "efficiency_str": "Efficiency",
                                "maximum_marks": st.column_config.NumberColumn(
                                    "Max Marks",
                                    format="%.1f"
                                ),
                                "marks_awarded": st.column_config.NumberColumn(
                                    "Awarded",
                                    format="%.1f"
                                ),
                                "section": "Section",
                                "question_number": "Q#",
                                "question_text": "Question",
                                "student_answer_text": "Student Answer",
                                "actual_answer": "Correct Answer"
                            }
                        )

                        # Summary metrics with float formatting
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Questions", len(answer_sheet))
                        with col2:
                            st.metric("Maximum Marks", f"{max_marks_total:.1f}")
                        with col3:
                            st.metric("Marks Awarded", f"{marks_awarded_total:.1f}")
                        with col4:
                            st.metric("Score Percentage", f"{percentage:.1f}%")


                    # Final celebration section
                    st.markdown("---")
                    st.markdown("### 🎊 Final Results")

                    col1, col2, col3 = st.columns(3)

                    with col1:
                        if percentage >= 90:
                            st.balloons()
                            st.success("🏆 CHAMPION!")
                        elif percentage >= 75:
                            st.success("🌟 STAR PERFORMER!")
                        else:
                            st.info("🚀 KEEP CLIMBING!")

                    with col2:
                        # Grade assignment
                        if percentage >= 95:
                            grade = "A+ 🌟"
                        elif percentage >= 90:
                            grade = "A 🥇"
                        elif percentage >= 85:
                            grade = "A- 🥈" 
                        elif percentage >= 80:
                            grade = "B+ 🥉"
                        elif percentage >= 75:
                            grade = "B 👍"
                        else:
                            grade = "Keep Trying! 💪"
                        
                        st.metric("Final Grade", grade)

                    with col3:
                        # Next steps
                        if percentage < 80:
                            st.warning("📚 Review weak areas")
                        else:
                            st.success("🎯 Ready for next level!")
                            
                except requests.exceptions.RequestException as e: 
                    st.error(f"Error processing answer sheet: {e}")
                except Exception as e:
                    st.error(f"Unexpected error: {e}")
                    import traceback
                    st.error(f"Debug traceback: {traceback.format_exc()}")
                    
        else:
            missing_items = []
            if answer_paper is None:
                missing_items.append("Answer paper")
            if selected_class == "Select a class":
                missing_items.append("Class")
            if selected_exam == "Select an exam":
                missing_items.append("Exam")
            if selected_subject == "Select a subject":
                missing_items.append("Subject")
            
            #st.error(f"Please provide: {', '.join(missing_items)}")








# if st.session_state.get("step") == 2:
#     st.subheader("Answer Paper", anchor=False)
#     st.caption("Upload a PDF of the answer paper and select existing question details.")
    
#     # Fetch question data for dropdowns
#     question_data = get_question_data()
    
#     if question_data:
#         # Extract unique class names and exam names
#         unique_classes = sorted(list(set([q["class_name"] for q in question_data])))
#         unique_exams = sorted(list(set([q["exam_name"] for q in question_data])))
        
#         # Create two columns for the dropdowns
#         col_class, col_exam = st.columns(2)
        
#         with col_class:
#             selected_class = st.selectbox(
#                 "Select Class",
#                 ["Select a class"] + unique_classes,
#                 key="class_dropdown"
#             )
        
#         with col_exam:
#             selected_exam = st.selectbox(
#                 "Select Exam",
#                 ["Select an exam"] + unique_exams,
#                 key="exam_dropdown"
#             )
        
#         # Filter questions based on selections
#         filtered_questions = question_data
#         if selected_class != "Select a class":
#             filtered_questions = [q for q in filtered_questions if q["class_name"] == selected_class]
#         if selected_exam != "Select an exam":
#             filtered_questions = [q for q in filtered_questions if q["exam_name"] == selected_exam]
        
#         # Show filtered results info
#         if selected_class != "Select a class" or selected_exam != "Select an exam":
#             st.info(f"Found {len(filtered_questions)} matching question papers")
            
#             # Optionally show a table of matching questions
#             if filtered_questions:
#                 st.write("**Matching Question Papers:**")
#                 import pandas as pd
#                 df = pd.DataFrame(filtered_questions)
#                 st.dataframe(df, use_container_width=True)
#     else:
#         st.warning("No question data available. Please ensure the database contains question papers.")
    
#     # File uploader for answer paper
#     answer_paper = st.file_uploader(
#         "Upload Answer Paper",
#         type=["pdf"],
#         accept_multiple_files=False,
#         key="answer_paper_uploader",
#     )

#     colA, colB = st.columns([1, 1])
#     back = colA.button("⬅ Back", use_container_width=True, key="back_btn")
#     finish = colB.button("Submit", use_container_width=True, key="finish_btn")

#     if back:
#         st.session_state["step"] = 1
#         st.rerun()
    
#     if finish:
#         # Handle the submission logic here
#         if answer_paper and selected_class != "Select a class" and selected_exam != "Select an exam":
#             st.success("Answer paper submitted successfully!")
#             # Add your submission logic here
#         else:
#             st.error("Please upload an answer paper and select both class and exam.")

