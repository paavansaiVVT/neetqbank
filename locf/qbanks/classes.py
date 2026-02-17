from sqlalchemy import create_engine, Column, Integer, String, Text, JSON,BLOB,ARRAY,Float, ForeignKey
from pydantic import BaseModel
from sqlalchemy.ext.declarative import declarative_base
from langchain_core.output_parsers import JsonOutputParser
from sqlalchemy.dialects.postgresql import JSONB
from typing import List, Optional, Dict

Base = declarative_base()

required_items = ["q_id", "question", "explanation", "correct_answer", "options", "chapter_name", "topic_name", "cognitive_level", "difficulty", "estimated_time", "concepts"]
question_types = ["direct_concept_based","assertion_reason","numerical_problem","diagram_Based_Question","multiple_correct_answer","matching_type","comprehension_type","case_study_based","statement_based","single_correct_answer"]
cognitive_levels = ["remembering","understanding","application","analyzing","evaluating", "creating"]
difficulty_levels=["easy","medium","hard"]

class pro_file_request(BaseModel):
    program_id: int
    file_url: str
class QuestionRequest(BaseModel):
    user_id: int
    uuid: str
    course_id: int
    program_id: int
    program_name: str
    subject_id: int
    subject_name: List[str]
    chapter_name: List[str]
    topic_name: List[str]
    question_type: str
    cognitive_level: Dict
    difficulty: Dict
    number_of_questions: int
    already_gen_mcqs: Optional[List[str]] = None
    model:Optional[int] = 1
    stream: Optional[int] = 1

class TopicQuestionrequest(BaseModel):
    course_id: int
    program_id: int
    program_name: str
    subject_name: str
    subject_id: int
    number_of_questions: int

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

class ImprovedQuestionReq(BaseModel):
    question_id: int
    user_query: str


class MCQData(Base):
    __tablename__ = 'ai_questions'
    __table_args__ = {'extend_existing': True}
    s_no = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    uuid = Column(Integer, nullable=False)
    stream = Column(Integer, nullable=True)  # Stream name
    question = Column(Text, nullable=False)
    correct_opt = Column(Text, nullable=True)
    option_a = Column(Text, nullable=True)  # Option A
    option_b = Column(Text, nullable=True)  # Option B
    option_c = Column(Text, nullable=True)  # Option C
    option_d = Column(Text, nullable=True)  # Option D
    answer_desc = Column(Text, nullable=False)
    difficulty = Column(Integer, nullable=False)
    question_type = Column(Integer, nullable=False)
    t_id = Column(Integer, nullable=False)  # Topic ID
    s_id = Column(Integer, nullable=False)  # Subject ID
    c_id = Column(Integer, nullable=False)  # Chapter ID
    p_id = Column(Integer, nullable=False)  # Program ID
    course_id = Column(Integer, nullable=False)
    co_id = Column(Integer, nullable=True)  # Course Outcome ID
    cognitive_level=Column(Integer, nullable=False)
    keywords = Column(Text, nullable=True)
    estimated_time=Column(Float, nullable=True)
    QC = Column(Text, nullable=False)
    model= Column(Text, nullable=True)
    model_id = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)


class PreGenMCQData(Base):
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
    p_id = Column(Integer, nullable=False)  # Program ID
    course_id = Column(Integer, nullable=False)
    co_id = Column(Integer, nullable=True)  # Course Outcome ID
    cognitive_level=Column(Integer, nullable=False)
    keywords = Column(Text, nullable=True)
    estimated_time=Column(Float, nullable=True)
    QC = Column(Text, nullable=False)
    model= Column(Text, nullable=True)
    model_id = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    
    
class oldMCQ(Base):
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
    
class Chapters(Base):
    __tablename__ = 'chapters'
    id = Column(Integer, primary_key=True, autoincrement=True)
    p_id = Column(Integer, nullable=False)
    s_id = Column(Integer, nullable=False)
    c_name = Column(Text, nullable=False)
    status = Column(Integer, nullable=False)
    is_deleted = Column(Integer, nullable=False)

class Topics(Base):
    __tablename__ = 'topics'
    id = Column(Integer, primary_key=True, autoincrement=True)
    s_id = Column(Integer, nullable=False)
    c_id = Column(Integer, nullable=False)
    p_id = Column(Integer, nullable=False)
    t_name = Column(Text, nullable=False)
    status = Column(Integer, nullable=False)
    is_deleted = Column(Integer, nullable=False)
    
class course_units(Base):
  __tablename__ = 'course_units'
  id = Column(Integer, primary_key=True, autoincrement=True)
  content = Column(Text, nullable=False)
  course_id = Column(Integer, nullable=False)
  title = Column(Integer, nullable=False)
  unit_number = Column(Integer, nullable=False)
  hours_allocated = Column(Integer, nullable=False)
    
class course_outcomes(Base):
  __tablename__ = 'course_outcomes'
  id = Column(Integer, primary_key=True, autoincrement=True)
  co_number = Column(Text, nullable=False)
  content = Column(Text, nullable=False)
  course_id = Column(Integer, nullable=False)
  chapter_id = Column(Integer, nullable=False) 
  
class courses(Base):
    __tablename__ = 'courses'
    id=Column(Integer, primary_key=True,autoincrement=True)
    code=Column(Text, nullable=False,unique=True)
    year_id= Column(Integer, nullable=False)  # Foreign key to years table
    course_name_id= Column(Integer, nullable=False)  # Foreign key to course_names table
    course_type= Column(Text, nullable=True)  # e.g., Core, Elective
    credits=  Column(Integer, nullable=True)  # Number of credits
    co_mapping=  Column(Text, nullable=True)  
    extracted_data= Column(Text, nullable=True)  
    learning_outcomes= Column(Text, nullable=True)  
    program_id= Column(Integer, nullable=False)  # Foreign key to programs table
    prerequisites= Column(Text,nullable=True)
    file_upload_id=Column(Integer, nullable=False)
    semester_id= Column(Integer, nullable=False)
    is_active= Column(Integer, nullable=True)  
    syllabus_file_url= Column(Text, nullable=True)   
    instruction_hours= Column(Integer, nullable=True)
    theory_ratio=   Column(Integer, nullable=True)  
    problems_ratio= Column(Integer, nullable=True) 
    total_hours= Column(Integer, nullable=True)  
    
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

class QbankRequest(Base):
    __tablename__ = 'ai_qbank_request'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True)
    uuid = Column(String, nullable=True)
    program_name = Column(String, nullable=True)
    subject_name = Column(JSON, nullable=True)
    chapter_name = Column(JSON, nullable=True)
    topic_name = Column(JSON, nullable=True)
    question_type = Column(String, nullable=True)
    cognitive_level = Column(JSON, nullable=True)
    difficulty = Column(JSON, nullable=True)
    number_of_questions = Column(Integer, nullable=True)
    model_id = Column(Integer, nullable=True)
    
    
question_type_dict = {
    "multiple_choice": 1,
    "short_answer": 2,
    "long_answer": 3,
    "problem_solving": 4
}

difficulty_level={"easy":1,
                  "medium":2,
                  "hard":3,
                  "veryhard":4}

cognitive_levels = {
    "remembering": 1,    
    "understanding": 2,
    "applying": 3,
    "application":3,
    "analyzing": 4,
    "analyze": 4,
    "evaluating": 5,
    "creating": 6       
}   

class program_content(Base):
    __tablename__ = 'program_content'
    id = Column(Integer, primary_key=True, autoincrement=True)
    program_id = Column(Integer, nullable=False)
    content = Column(Text, nullable=True)
    clean_content= Column(Text, nullable=True)
    raw_json = Column(JSON, nullable=True)
