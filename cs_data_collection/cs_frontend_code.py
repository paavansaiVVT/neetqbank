import streamlit as st
import asyncio
from cs_data_collection.cs_basic_details import CollegeRequest
from cs_data_collection.cs_assigner_function import college_suggest_dc

# --- Setup Streamlit UI ---
st.set_page_config(page_title="CollegeSuggest Data Collection", layout="centered")
st.title("🏫 CollegeSuggest Data Collection Tool")

progress_bar = st.empty()
status_text = st.empty()

# --- Main Async function ---
async def main(college_name, state_name, year):
    try:
        request = CollegeRequest(
            college_name=college_name,
            state_name=state_name,
            year=year
        )

        # Reset progress and status
        progress_bar.progress(0)
        status_text.text("🔵 Starting basic validation...")

        # Prepare callbacks
        async def progress_callback(progress_value):
            progress_bar.progress(progress_value)

        async def status_callback(message):
            status_text.text(message)

        # Call your main function
        await college_suggest_dc(
            request,
            progress_callback=lambda p: progress_bar.progress(p),
            status_callback=lambda msg: status_text.text(msg)
        )

    except ValueError as e:
        st.error(f"❌ {e}")  # Proper Streamlit popup if error
    except Exception as e:
        st.error(f"❌ Critical Error: {e}")  # Any other errors

# --- Input Form ---
with st.form(key="input_form"):
    college_name = st.text_input("College Name", "")
    state_name = st.text_input("State Name", "")
    year = st.number_input("Year", min_value=2000, max_value=2100, value=2025)
    submit_button = st.form_submit_button(label="Start Data Collection")

# --- When Form Submitted ---
if submit_button:
    if college_name and state_name:
        asyncio.run(main(college_name, state_name, year))
    else:
        st.warning("⚠️ Please fill all fields before submitting.")
