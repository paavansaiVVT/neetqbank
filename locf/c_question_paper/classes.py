from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from sqlalchemy import create_engine, Column, Integer, String, Text, JSON,BLOB,ARRAY,Float, ForeignKey
from pydantic import BaseModel
from sqlalchemy.ext.declarative import declarative_base
from langchain_core.output_parsers import JsonOutputParser
from sqlalchemy.dialects.postgresql import JSONB

Base = declarative_base()

# Required fields from OCR_Question_Paper_Extraction_Agent
required_items_extraction = [
    "question_number",
    "has_sub_questions",
    "alternative_ques",
    "parts"
]

# Required fields in each part from extraction
required_part_fields_extraction = [
    "part_label",
    "text",
    "marks"
]

# Required fields from OCR_Question_Paper_Enrichment_Agent (added to parts)
required_part_fields_enrichment = [
    "explanation",
    "expected_answer",
    "key_points",
    "marking_scheme",
    "cognitive_level",  # Bloom's Taxonomy level
    "difficulty",       # Easy, Medium, Hard
    "estimated_time"    # Float minutes
]

# Optional fields (can be null)
optional_fields = [
    "s3_url",
    "part_of",
    "image_name",
    "image_description",
    "question_type"
]

# Legacy required_items (for backward compatibility)
required_items = ["question_number", "question_type", "max_marks", "question_text","options", "explanation", "expected_answer", "key_points","marking_scheme", "image_description", "image_name", "question_no", "part_of", "s3_url"]

question_type_dict = {
    "MCQ": 1,
    "SA": 2,
    "LA": 3,
    "problem_solving": 4,
    "A/R": 5,
    "VSA": 6,
    "CBQ": 7,
    "MAP": 8
}

# Bloom's Taxonomy Cognitive Level Mapping
cognitive_level_dict = {
    "Remembering": 1,
    "Understanding": 2,
    "Applying": 3,
    "Analyzing": 4,
    "Evaluating": 5,
    "Creating": 6
}

# Difficulty Level Mapping
difficulty_dict = {
    "Easy": 1,
    "Medium": 2,
    "Hard": 3
}
class QuestionPaperRequest(BaseModel):
    uuid: str
    user_id: int
    exam_title: str
    subject: Optional[str] = None
    class_name: Optional[str] = None
    grade_level: Optional[str] = None
    exam_date: Optional[str] = None
    duration_minutes: Optional[int] = 120
    description: Optional[str] = None
    question_paper_name: Optional[str] = None
    pdf_url: Optional[str] = None
    qcount: Optional[int] = None
    
class DbQuestionData(Base):
    __tablename__ = 'ocr_question_paper'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    uuid = Column(String, nullable=False)
    grader_id = Column(Integer, nullable=True)
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

class QuestionData(Base):
    __tablename__ = 'ocr_ai_questions'
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    qp_id = Column(Integer, nullable=False)
    uuid = Column(String(255), nullable=False)
    question_number = Column(Integer, nullable=False)
    alternative_ques = Column(String, nullable=True)
    has_sub_questions = Column(String, nullable=True)
    is_or_question = Column(String, nullable=True)
    or_option = Column(String, nullable=True)
    part_label = Column(String, nullable=True)
    is_image= Column(Integer, nullable=True)
    image_description = Column(Text, nullable=True)
    question_type = Column(Integer, nullable=True)
    max_marks = Column(Integer, nullable=True)
    question = Column(Text, nullable=False)
    correct_opt = Column(String(255), nullable=True)
    option_a = Column(Text, nullable=True)
    option_b = Column(Text, nullable=True)
    option_c = Column(Text, nullable=True)
    option_d = Column(Text, nullable=True)
    explanation = Column(Text, nullable=True)
    expected_answer = Column(Text, nullable=True)
    marking_scheme = Column(Text, nullable=True)
    key_points = Column(JSONB, nullable=True)
    image_part_of = Column(JSONB, nullable=True)
    image_url = Column(JSONB, nullable=True)
    difficulty = Column(Integer, nullable=True)
    cognitive_level=Column(Integer, nullable=True)
    estimated_time=Column(Float, nullable=True)
    QC = Column(Text, nullable=True)
    model= Column(Text, nullable=True)
    model_id = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
        
class ImageTag(BaseModel):
    """A model to link an image ID to a specific question number and part."""
    image_name: str = Field(..., description="The unique ID of the image, e.g., 'page-0-img-0'")
    question_no: str = Field(..., description="The question number this image belongs to, e.g., '1' or '39' or '12'")
    part_of: Literal["question", "option_1", "option_2", "option_3", "option_4", "sub_question_a", "sub_question_b"] = Field(..., description="Specifies if the image is part of the main question stem, an option, or a specific sub-question.")

# This will be our final output model, including the S3 URL.
class FinalImageTag(ImageTag):
    s3_url: str = Field(..., description="The final public URL of the image in the S3 bucket.")
    
class OcrProcessResult(BaseModel):
    image_tags: List[dict]
    image_urls: List[str]
    llm_full_response: str
    llm_markdown_results: str
    
    
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