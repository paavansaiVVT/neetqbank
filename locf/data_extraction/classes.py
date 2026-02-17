from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Text, JSON,ForeignKey,String, Float
from pydantic import BaseModel
from typing import List, Optional

Base = declarative_base()

class file_request(BaseModel):
    file_path: str
    file_name: str
    markdown: Optional[str] = None
    uuid: str
    organization_id: int
    program_id: int
class file_upload(Base):
    __tablename__ = 'file_uploads'
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(Text, nullable=False)
    file_size = Column(Text, nullable=False)
    original_filename = Column(Text, nullable=False)  # Stream name
    program_id = Column(Integer, nullable=False)  # Program ID
    stored_filename = Column(Text, nullable=False)
    processing_status=Column(Text, nullable=True)
    processing_results= Column(JSON)  # Store results of processing
    organization_id=Column(Integer, nullable=False)

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
    

class years_table(Base):
    __tablename__ = 'years'
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, autoincrement=True)
    years = Column(Text, nullable=False)

class academic_years(Base):
    __tablename__ = 'academic_years'
    id = Column(Integer, primary_key=True, autoincrement=True)
    year_id = Column(Integer, nullable=False)
    #program_id = Column(Integer, nullable=False)


class semesters(Base):
    __tablename__ = 'semesters'
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    year_number = Column(Integer, nullable=True)
    semester_number = Column(Integer, nullable=False)
    semester_type = Column(Text, nullable=False)
    academic_year_id = Column(Integer, nullable=False)
    is_active=Column(Integer, nullable=False)


class co_po_mappings(Base):
    __tablename__ = 'co_po_mappings'
    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, nullable=False)
    co_label = Column(String(10), nullable=False)   # e.g., 'CO1', 'TOTAL'
    po_label = Column(String(10), nullable=False)   # e.g., 'PO1', 'PSO1'
    value = Column(Float, nullable=False)
    justification = Column(Text, nullable=True)  # Justification for the mapping

class course_units(Base):
    __tablename__ = 'course_units'
    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, nullable=False)
    unit_number = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    hours_allocated = Column(Integer, nullable=False)
    title = Column(Text, nullable=False)

class list_of_programs(Base):
    __tablename__ = 'list_of programs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, nullable=False)
    program_id = Column(Integer, nullable=True)
    description = Column(Text, nullable=False)
    
class Textbook(Base):
    __tablename__ = 'textbooks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    author = Column(String(255))
    edition = Column(String(100))
    year = Column(Integer)
    publisher = Column(String(255))
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    

class CourseOutcome(Base):
    __tablename__ = 'course_outcomes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    co_number = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    chapter_id = Column(Integer, ForeignKey('chapters.id'), nullable=False)
    
class CourseOutcomePo(Base):
    __tablename__ = 'course_outcomes_po'

    id = Column(Integer, primary_key=True, autoincrement=True)
    co_number = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    chapter_id = Column(Integer, ForeignKey('chapters.id'), nullable=False)
    po_id = Column(Integer, nullable=True)
    

class ReferenceBook(Base):
    __tablename__ = 'reference_books'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    author = Column(String(255))
    edition = Column(String(100))
    year = Column(Integer, nullable=True)
    publisher = Column(String(255))
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)


class WebResource(Base):
    __tablename__ = 'web_resources'

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(Text, nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)

class LearningObjective(Base):
    __tablename__ = 'learning_objectives'

    id = Column(Integer, primary_key=True, autoincrement=True)
    lo_number = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    #confidence_score = Column(Float, nullable=True)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)


class Subjects(Base):
    __tablename__ = 'subjects'
    id = Column(Integer, primary_key=True, autoincrement=True)
    s_name = Column(Text, nullable=False)

class Chapters(Base):
    __tablename__ = 'chapters'
    id = Column(Integer, primary_key=True, autoincrement=True)
    p_id = Column(Integer, nullable=False)
    s_id = Column(Integer, ForeignKey('subjects.id'), nullable=False)
    c_name = Column(Text, nullable=False)
    status = Column(Integer, nullable=False)
    is_deleted = Column(Integer, nullable=False)


class ProgramOutcomes(Base):
    __tablename__ = 'program_outcomes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    program_id = Column(Integer, ForeignKey('programs.id'), nullable=False)
    code = Column(String(10), nullable=False)  # e.g., 'PO1', 'PSO1'
    description = Column(Text, nullable=False)

class Topics(Base):
    __tablename__ = 'topics'
    id = Column(Integer, primary_key=True, autoincrement=True)
    s_id = Column(Integer, nullable=False)
    c_id = Column(Integer, nullable=False)
    p_id = Column(Integer, nullable=False)
    t_name = Column(Text, nullable=False)
    status = Column(Integer, nullable=False)
    is_deleted = Column(Integer, nullable=False)    