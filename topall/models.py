from pydantic import BaseModel
class TopallQWeakRequest(BaseModel):
    studentId: int
    streamId: int
    subjectId: int

ACCURACY_THRESHOLD = 0.60

COGNITIVE_ORDER = {
    "Remembering": 1,
    "Understanding": 2,
    "Application": 3,
    "Analyzing": 4,
    "Evaluating": 5,
    "Creating": 6
}