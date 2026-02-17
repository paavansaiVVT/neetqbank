from sqlalchemy import Column, Integer, String, update,JSON
from pydantic import BaseModel
from typing import Optional,Any
from sqlalchemy.orm import declarative_base

# Define the base model
Base = declarative_base()

class CareerFitResult(BaseModel):
    class_Id: Optional[int] = None
    topRiasecText: Optional[str] = None
    bigFiveText: Optional[str] = None
    profileTitle: Optional[str] = None
    profileDescription: Optional[str] = None
    scoreSummary: Optional[str] = None
    strengths: Optional[str] = None
    activities: Optional[str] = None
    careers: Optional[str] = None
    quizScores: Optional[str] = None
    report: Optional[str] = None
class RequestData(BaseModel):
    message: Optional[str] = None
    url: Optional[str] = None
    history: Optional[str] = None
    chapter: Optional[str] = None
    chapter_id: Optional[int] = None
    topic_ids : Optional[list]=None
    topic_list : Optional[list]=None
    study_plan : Optional[list]=None
    user_id:Optional[int]=None
    level:Optional[int]=None
    instruction_id:Optional[int]=None
    userId:Optional[int]=None
    studyPlanDate:Optional[str] = None
    subject:Optional[str] = None
    classId:Optional[int] = None
    careerFitResult: Optional[CareerFitResult] = None
    studentProfile: Optional[dict] = None
# Define the Milestone model (adjust the table name and columns if needed)
class Milestone(Base):
    __tablename__ = "milestone"  # Your table name

    sl_no = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    chapter_id = Column(Integer, nullable=False)
    chapter_name = Column(String(255), nullable=False)
    level = Column(Integer)  # This corresponds to "miston level"
    topic_ids = Column(String, nullable=True)
    date=Column(String, nullable=True)
    instruction_id=Column(Integer, nullable=False)


class AIQuestion(Base):
    __tablename__ = 'ai_questions'

    id = Column(Integer, primary_key=True, index=True)
    question = Column(String, nullable=False)
    correct_opt = Column(String, nullable=False)
    option_a = Column(String, nullable=False)
    option_b = Column(String, nullable=False)
    option_c = Column(String, nullable=False)
    option_d = Column(String, nullable=False)
    c_id = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)