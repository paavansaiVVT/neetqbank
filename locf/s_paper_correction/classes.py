from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Union
from sqlalchemy import create_engine, Column, Integer, String, Text, JSON,BLOB,ARRAY,Float, ForeignKey
from pydantic import BaseModel
from sqlalchemy.ext.declarative import declarative_base
from langchain_core.output_parsers import JsonOutputParser
from sqlalchemy.dialects.postgresql import JSONB

Base= declarative_base()
required_items =["section", "question_number", "student_answer_text", "feedback", "maximum_marks", "marks_awarded", "confident_level"]

cdl_level={"easy":1,
            "medium":2,
            "hard":3}

question_type_dict = {
    1: "MCQ",
    2: "SA",
    3: "LA",
    4: "problem_solving",
    5: "A/R",
    6: "VSA",
    7: "CBQ"
}

crt_opt = {
    1: "a",
    2: "b",
    3: "c",
    4: "d",
}

class AnswerSheetRequest(BaseModel):
    user_id: int
    uuid: str
    pdf_url: str
    question_id: int
    cdl_level: Optional[str] = "EASY"
    student_rollno: Optional[str] = None
    model: Optional[int] = 1 
    qcount: Optional[int] = None 
      
class DbQuestionData(Base):
    __tablename__ = 'ocr_question_paper'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    uuid = Column(String, nullable=False)
    question_paper_name = Column(String, nullable=False)
    pdf_url = Column(String, nullable=False)
    class_name = Column(String, nullable=False)
    subject_name = Column(String, nullable=False)
    grade_level = Column(String, nullable=False)
    exam_name = Column(String, nullable=False)
    exam_date = Column(String, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    question_paper_json = Column(JSONB, nullable=True)
    contain_image_list = Column(ARRAY(String), nullable=True)
    instruction_set = Column(JSONB, nullable=True)
    md_list = Column(ARRAY(JSONB), nullable=True)
    missed_questions = Column(ARRAY(JSONB), nullable=True)
    
class DbAnswerSheetCorrection(Base):
    __tablename__ = 'ocr_answer_paper'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    uuid = Column(String(255), nullable=False)
    qp_id = Column(Integer, nullable=False)
    q_id = Column(Integer, nullable=False)
    student_id = Column(Integer, nullable=False)
    exam_id = Column(Integer, nullable=False)
    section = Column(String, nullable=True)
    question_number = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    student_answer_text = Column(Text, nullable=False)
    actual_answer = Column(Text, nullable=True)
    feedback = Column(Text, nullable=True)
    maximum_marks = Column(Float, nullable=True)
    marks_awarded = Column(Float, nullable=True)
    model_used = Column(String, nullable=False)
    cdl_level = Column(Integer, nullable=False)
    confidence_level = Column(Float, nullable=True)
    
class DbStudentDetails(Base):
    __tablename__ = 'ocr_student_details'
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_name = Column(String, nullable=True)
    role_number = Column(Integer, nullable=False)
    section = Column(String, nullable=True)
    class_name = Column(String, nullable=True)
    
class DbExamDetails(Base):
    __tablename__ = 'ocr_ans_paper_details'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    uuid = Column(String(255), nullable=False)
    grader_id = Column(Integer, nullable=True)
    student_id = Column(Integer, nullable=False)
    qp_id = Column(Integer, nullable=False)
    cdl_id = Column(Integer, nullable=False)
    exam_date = Column(String, nullable=True)
    pdf_url = Column(String(255), nullable=True)
    subject = Column(String, nullable=True)
    phase = Column(String, nullable=True)
    missed_answers = Column(JSONB, nullable=True)
    request_json = Column(JSONB, nullable=True)
    gen_response = Column(JSONB, nullable=True)
    max_marks = Column(Float, nullable=True)
    awarded_marks = Column(Float, nullable=True)
    confidence_level = Column(Float, nullable=True)
    result_analysis = Column(JSONB, nullable=True)
    
class QuestionData(Base):
    __tablename__ = 'ocr_ai_questions'
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    qp_id = Column(Integer, nullable=False)
    uuid = Column(String(255), nullable=False)
    question_number = Column(Integer, nullable=False)
    is_image= Column(Integer, nullable=True)
    image_description = Column(Text, nullable=True)
    question_type = Column(Integer, nullable=True)
    max_marks = Column(Integer, nullable=True)
    question = Column(Text, nullable=False)
    correct_opt = Column(String(255), nullable=True)
    option_a = Column(Text, nullable=True)  # Option A
    option_b = Column(Text, nullable=True)  # Option B
    option_c = Column(Text, nullable=True)  # Option C
    option_d = Column(Text, nullable=True)  # Option D
    explanation = Column(Text, nullable=True)
    expected_answer = Column(Text, nullable=True)
    marking_scheme = Column(Text, nullable=True)
    key_points = Column(JSONB, nullable=True)
    image_part_of = Column(String(255), nullable=True)
    image_url = Column(String(255), nullable=True)
    difficulty = Column(Integer, nullable=True)
    cognitive_level=Column(Integer, nullable=True)
    estimated_time=Column(Float, nullable=True)
    QC = Column(Text, nullable=True)
    model= Column(Text, nullable=True)
    model_id = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    
class UserTokenUsage(Base):
    __tablename__ = 'ai_gen_que_tokens_usage'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True)
    session_uuid = Column(String, nullable=True)
    bot_name = Column(String, nullable=True)
    model_name = Column(String, nullable=True)
    input = Column(Integer, nullable=True)
    output = Column(Integer, nullable=True)
    total = Column(Integer, nullable=True)
    
class ProgressData(Base):
    __tablename__ = 'progress_table'
    __table_args__ = {'extend_existing': True}
    s_no = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String, nullable=False)
    progress_percent = Column(Float, nullable=False)