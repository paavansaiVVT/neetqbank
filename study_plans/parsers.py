from pydantic import BaseModel
from typing import Optional
from langchain_core.output_parsers import JsonOutputParser
from typing import List, Optional


class adaptive_plan(BaseModel):
    explanation: Optional[str] = None


adaptive_plan_parser = JsonOutputParser(pydantic_object=adaptive_plan)
