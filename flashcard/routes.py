from fastapi import APIRouter
from flashcard.app import generate_flashcard,FlashcardRequest

router = APIRouter()


# Flashcard generator
@router.post("/flashcard")
async def flashcard(request: FlashcardRequest):
    try:
        response =await generate_flashcard(request)
        return {"response": response}
    except Exception as e:   
        print(f"Error occurred: {e}")
        return None