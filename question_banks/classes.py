from sqlalchemy import create_engine, Column, Integer, String, Text, JSON,BLOB,ARRAY,Float
from pydantic import BaseModel
from sqlalchemy.ext.declarative import declarative_base
from langchain_core.output_parsers import JsonOutputParser
from typing import List, Optional
# Define a base class for the models
Base = declarative_base()

class QuestionBankRequest(BaseModel):
    question: Optional[str] = None
    explanation: Optional[str] = None
    correct_opt: Optional[int] = None
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    difficulty: Optional[int] = None
    question_type: Optional[int] = None
    question_id: Optional[int] = None
    t_id: Optional[int] = None
    s_id: Optional[int] = None
    c_id: Optional[int] = None
    image_url: Optional[str] = None

class slug_data(BaseModel):
    question_id: Optional[int] = None
    question: Optional[str] = None
    topic: Optional[str] = None
    chapter: Optional[str] = None
    subject: Optional[str] = None

class Topics(Base):
    __tablename__ = 'topics'
    
    s_no = Column(Integer, primary_key=True, autoincrement=True)  # Topic ID
    t_name = Column(Text, nullable=False)
    s_id = Column(Integer, nullable=False)  # Subject ID
    c_id = Column(Integer, nullable=False)  # Chapter ID

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String
class explanation(Base):
    __tablename__ = 'ai_questions_qc'
    #__tablename__ = 'ai_questions'
    __table_args__ = {'extend_existing': True}
    s_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    option_a: Mapped[str] = mapped_column(String)
    option_b: Mapped[str] = mapped_column(String)
    option_c: Mapped[str] = mapped_column(String)
    option_d: Mapped[str] = mapped_column(String)
    correct_opt: Mapped[int] = mapped_column(Integer)
    answer_desc: Mapped[str] = mapped_column(String)


class slug(Base):
    __tablename__ = 'ai_questions'
    __table_args__ = {'extend_existing': True}
    s_no = Column(Integer, primary_key=True)
    slug = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)

class qc(Base):
    __tablename__ = 'ai_questions_qc'
    #__tablename__ = 'ai_questions'
    __table_args__ = {'extend_existing': True}
    s_no = Column(Integer, primary_key=True)
    result = Column(Integer, nullable=True)
    reason = Column(Text, nullable=True)

class MCQData(Base):
    __tablename__ = 'ai_questions' # ai_questions_variations
    #__tablename__ = 'ai_questions_qc'
    __table_args__ = {'extend_existing': True}
    s_no = Column(Integer, primary_key=True, autoincrement=True)
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
    total_score=Column(Float, nullable=False)
     # New columns for each score
    content_accuracy = Column(Float, nullable=True)
    question_construction = Column(Float, nullable=True)
    subject_specific_criteria = Column(Float, nullable=True)
    cognitive_level_assessment = Column(Float, nullable=True)
    difficulty_calibration = Column(Float, nullable=True)
    discrimination_power = Column(Float, nullable=True)
    time_requirement = Column(Float, nullable=True)
    step_complexity = Column(Float, nullable=True)
    concept_integration = Column(Float, nullable=True)
    reasoning_depth = Column(Float, nullable=True)
    # scaled scored 
    time_requirement_scaled = Column(Float, nullable=True)
    step_complexity_scaled = Column(Float, nullable=True)
    concept_integration_scaled = Column(Float, nullable=True)
    reasoning_depth_scaled = Column(Float, nullable=True)
    difficulty_scaled = Column(Float, nullable=True)
    estimated_time=Column(Float, nullable=True)
    
    QC = Column(Text, nullable=False)
    violations = Column(JSON, nullable=True)
    
    recommendations = Column(JSON, nullable=True)
    category_scores = Column(JSON, nullable=True)

    # Detailed Score Breakdown for Categories
    content_accuracy_details = Column(JSON, nullable=True)
    question_construction_details = Column(JSON, nullable=True)
    subject_specific_details = Column(JSON, nullable=True)
    difficulty_calibration_details = Column(JSON, nullable=True)
    discrimination_power_details = Column(JSON, nullable=True)
    # New Version control
    original_question_id=Column(Text, nullable=True)
    variation_type=Column(Text, nullable=True)
    change_log=Column(Text, nullable=True)
    question_origin=Column(Integer, nullable=False) 
    year=Column(Integer, nullable=False) 

class Topall_Data(Base):
    __tablename__ = 'vr_questions' 
    vr_ques_id = Column(Integer, primary_key=True, autoincrement=True)
    vr_ques_type = Column(Integer, nullable=False)
    cognitive_level = Column(Integer, nullable=False)
    estimated_time = Column(Float, nullable=False)
    #keywords = Column(Text, nullable=True)


# Options parser
class options(BaseModel):
    solution: Optional[str] = None
    correct_answer: Optional[str] = None
    options: Optional[List[str]] = None
options_parser = JsonOutputParser(pydantic_object=options)


# QC result parser
class options(BaseModel):
    result: Optional[str] = None
    reason: Optional[str] = None

result_parser = JsonOutputParser(pydantic_object=options)

class expl_parse(BaseModel):
    explanation: Optional[str] = None

explanation_parser = JsonOutputParser(pydantic_object=expl_parse)


class tagging_parse(BaseModel):
    concepts: Optional[str] = None
    cognitive_level: Optional[str] = None
    question_type: Optional[str] = None


question_type_parser = JsonOutputParser(pydantic_object=tagging_parse)