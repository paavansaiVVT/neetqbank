from sqlalchemy import create_engine, Column, Integer, String, Text, JSON,BLOB,ARRAY,Float
from pydantic import BaseModel
from sqlalchemy.ext.declarative import declarative_base
from langchain_core.output_parsers import JsonOutputParser
from typing import List, Optional

required_items = ["q_id", "question", "explanation", "correct_answer", "options", "topic_name", "cognitive_level", "question_type", "estimated_time", "concepts"]
question_types = ["direct_concept_based","assertion_reason","numerical_problem","diagram_Based_Question","multiple_correct_answer","matching_type","comprehension_type","case_study_based","statement_based","single_correct_answer"]
cognitive_levels = ["remembering","understanding","application","analyzing","evaluating"]#,"creating"]
difficulty_levels=["easy","medium","hard"]

cognitive_level_to_question_types = {
    "remembering": [
        "direct_concept_based",
        "matching_type"
    ],
    "understanding": [
        "direct_concept_based",
        "matching_type",
        "comprehension_type",
        "statement_based"
    ],
    "applying": [
        "numerical_problem"
    ],
    "application": [
        "numerical_problem"
    ],
    "analyzing": [
        "assertion_reason",
        "numerical_problem",
        "comprehension_type",
        "case_study_based"
    ],
    "evaluating": [
        "assertion_reason",
        "case_study_based",
        "statement_based",
    ],
    "creating": [
        # No direct question type from your list maps to this yet
    ]
}

class MCQ(BaseModel):
    q_id: str
    question: str
    explanation: str
    correct_answer: str
    options: List[str]
    topic_name: str
    cognitive_level: str
    question_type: str
    estimated_time: str
    concepts: str

class QuestionRequest(BaseModel):
    user_id: int
    uuid: str
    subject_name: List[str]
    chapter_name: List[str]
    topic_name: List[str]
    difficulty: str
    number_of_questions: int
    cognitive_level: str
    already_gen_mcqs: Optional[List[str]] = None
    model:int
    stream: str

class ComplaintRequest(BaseModel):
    user_id: int
    complaint_id: str
    user_name: str
    user_email: Optional[str] = None
    user_phone: Optional[str] = None
    ss_url: Optional[str] = None
    description: Optional[str] = None

class TopicRequest(BaseModel):
    chapter_name: List[str]
    difficulty: Optional[str] = None
    number_of_questions: int
    model:Optional[int] = None

class ImprovedQuestionReq(BaseModel):
    question_id: int
    user_query: str
# Define a base class for the models
Base = declarative_base()
class cs_MCQData(Base):
    __tablename__ = 'ai_questions'
    __table_args__ = {'extend_existing': True}
    s_no = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    uuid = Column(Integer, nullable=False)
    stream = Column(Integer, nullable=True)  # Stream name
    question = Column(Text, nullable=False)
    correct_opt = Column(String(255), nullable=False)
    option_a = Column(Text, nullable=False)  # Option A
    option_b = Column(Text, nullable=False)  # Option B
    option_c = Column(Text, nullable=False)  # Option C
    option_d = Column(Text, nullable=False)  # Option D
    answer_desc = Column(Text, nullable=False)
    difficulty = Column(Integer, nullable=False)
    question_type = Column(Integer, nullable=False)
    t_id = Column(Integer, nullable=False)  # Topic ID
    s_id = Column(Integer, nullable=False)  # Subject ID
    c_id = Column(Integer, nullable=False)  # Chapter ID
    cognitive_level=Column(Integer, nullable=False)
    keywords = Column(Text, nullable=True)
    estimated_time=Column(Float, nullable=True)
    QC = Column(Text, nullable=False)
    model= Column(Text, nullable=True)
    model_id = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)  # Reason for the question

class repo_MCQData(Base):
    __tablename__ = 'ai_questions_repo'
    __table_args__ = {'extend_existing': True}
    s_no = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    uuid = Column(Integer, nullable=False)
    stream = Column(Integer, nullable=True)  # Stream name
    question = Column(Text, nullable=False)
    correct_opt = Column(String(255), nullable=False)
    option_a = Column(Text, nullable=False)  # Option A
    option_b = Column(Text, nullable=False)  # Option B
    option_c = Column(Text, nullable=False)  # Option C
    option_d = Column(Text, nullable=False)  # Option D
    answer_desc = Column(Text, nullable=False)
    difficulty = Column(Integer, nullable=False)
    question_type = Column(Integer, nullable=False)
    t_id = Column(Integer, nullable=False)  # Topic ID
    s_id = Column(Integer, nullable=False)  # Subject ID
    c_id = Column(Integer, nullable=False)  # Chapter ID
    cognitive_level=Column(Integer, nullable=False)
    keywords = Column(Text, nullable=True)
    estimated_time=Column(Float, nullable=True)
    QC = Column(Text, nullable=False)
    model= Column(Text, nullable=True)
    model_id = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)

class Topics(Base):
    __tablename__ = 'topics'
    
    s_no = Column(Integer, primary_key=True, autoincrement=True)  # Topic ID
    t_name = Column(Text, nullable=False)
    s_id = Column(Integer, nullable=False)  # Subject ID
    c_id = Column(Integer, nullable=False)  # Chapter ID


class cs_oldMCQ(Base):
    __tablename__ = 'old_questions'
    __table_args__ = {'extend_existing': True}
    s_no = Column(Integer, primary_key=True, autoincrement=True)
    q_id = Column(Integer, nullable=False)
    question = Column(Text, nullable=False)
    correct_opt = Column(String(255), nullable=False)
    option_a = Column(Text, nullable=False)  # Option A
    option_b = Column(Text, nullable=False)  # Option B
    option_c = Column(Text, nullable=False)  # Option C
    option_d = Column(Text, nullable=False)  # Option D
    answer_desc = Column(Text, nullable=False)
    difficulty = Column(Integer, nullable=False)
    question_type = Column(Integer, nullable=False)
    t_id = Column(Integer, nullable=False)  # Topic ID
    s_id = Column(Integer, nullable=False)  # Subject ID
    c_id = Column(Integer, nullable=False)  # Chapter ID
    cognitive_level=Column(Integer, nullable=False)
    keywords = Column(Text, nullable=True)
    estimated_time=Column(Float, nullable=True)
    QC = Column(Text, nullable=False)
    user_query = Column(Text, nullable=True)
    model= Column(Text, nullable=True)

class ProgressData(Base):
    __tablename__ = 'progress_table'
    __table_args__ = {'extend_existing': True}
    s_no = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String, nullable=False)
    progress_percent = Column(Float, nullable=False)