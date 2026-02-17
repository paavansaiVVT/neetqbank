import os
import asyncio
import logging
from dotenv import load_dotenv

from cs_data_collection.cs_basic_details import CollegeRequest, cs_basic_data_bot
from cs_data_collection.cs_authority import cs_authority_data
from cs_data_collection.cs_course_details import cs_course_data_bot
from cs_data_collection.cs_infrastructure import cs_infrastructure_data
from cs_data_collection.cs_college_rankings import cs_ranking_data
from cs_data_collection.cs_college_cutoff import cs_cutoff_bot
from cs_data_collection.cs_bonds import cs_bond_data
from cs_data_collection.cs_college_quota import cs_college_quota_bot
from cs_data_collection.cs_counselling_activities import cs_schedule_data
from cs_data_collection.cs_hostel_fees import cs_hostel_fees_data_bot
from cs_data_collection.cs_college_fees import cs_clg_fees_data_bot
from cs_data_collection.cs_seatmatrix import cs_seat_intake_bot

load_dotenv()
DATABASE_URL_6 = os.getenv("DATABASE_URL_6")
logger = logging.getLogger(__name__)

# --- Retry Helper ---
async def retry_task(task_func, *args, retries=2, delay=2, rate_limit_delay=10, **kwargs):
    attempt = 0
    while attempt <= retries:
        try:
            await asyncio.sleep(0.5)  # small delay between calls
            return await task_func(*args, **kwargs)
        except Exception as e:
            attempt += 1
            if "429" in str(e) or "rate limit" in str(e).lower():
                logger.warning(f"⚡ Rate limit hit for {task_func.__name__}. Waiting {rate_limit_delay}s before retrying...")
                await asyncio.sleep(rate_limit_delay)
            else:
                await asyncio.sleep(delay)

            if attempt > retries:
                logger.error(f"❌ Task {task_func.__name__} failed after {retries} retries: {e}")
                return e
            else:
                logger.warning(f"⚡ Retry {attempt} for task {task_func.__name__} after error: {e}")

async def college_suggest_dc(request: CollegeRequest, progress_callback=None, status_callback=None):
    try:
        result = await cs_basic_data_bot.model_call(request)
        logger.info(f"🎯 Received basic details for request: {result}")

        college_id = result.get("college_id")
        state_id = result.get("state_id")

        # ✅ Important Check: College ID must exist
        if not college_id:
            if status_callback:
                status_callback("❌ College ID not found. Stopping data collection.")
            logger.error("❌ College ID not found. Data collection aborted.")
            raise ValueError("College ID not found. Please check the college name and state.")

        if status_callback:
            status_callback("🔵 Starting First Batch...")
        if progress_callback:
            progress_callback(5)

        # First batch
        first_batch = await asyncio.gather(
            retry_task(cs_infrastructure_data.get_data, request, college_id=college_id),
            retry_task(cs_authority_data.get_data, request, college_id=college_id, state_id=state_id),
            retry_task(cs_college_quota_bot.fetch_all_program_levels, request, college_id=college_id),
            retry_task(cs_course_data_bot.fetch_all_course_levels, request, college_id=college_id),
            retry_task(cs_hostel_fees_data_bot.model_call, request),
            return_exceptions=True
        )
        if status_callback:
            status_callback("✅ First Batch Completed. Moving to Second Batch ➡️")
        if progress_callback:
            progress_callback(25)

        await asyncio.sleep(2)

        # Second batch
        second_batch = await asyncio.gather(
            retry_task(cs_ranking_data.get_data, request, college_id=college_id),
            retry_task(cs_schedule_data.get_data, request, college_id=college_id, state_id=state_id),
            return_exceptions=True
        )
        if status_callback:
            status_callback("✅ Second Batch Completed. Moving to Third Batch ➡️")
        if progress_callback:
            progress_callback(45)

        await asyncio.sleep(2)

        # Third batch
        third_result = await retry_task(cs_cutoff_bot.get_all_program_fee_data, request, college_id=college_id)
        if status_callback:
            status_callback("✅ Third Batch Completed. Moving to Fourth Batch ➡️")
        if progress_callback:
            progress_callback(60)

        await asyncio.sleep(2)

        # Fourth batch
        fourth_result = await retry_task(cs_clg_fees_data_bot.get_all_program_fee_data, request, college_id=college_id)
        if status_callback:
            status_callback("✅ Fourth Batch Completed. Moving to Fifth Batch ➡️")
        if progress_callback:
            progress_callback(75)

        await asyncio.sleep(2)

        # Fifth batch
        fifth_result = await retry_task(cs_seat_intake_bot.get_all_program_fee_data, request, college_id=college_id)
        if status_callback:
            status_callback("✅ Fifth Batch Completed. Collecting Bond Data ➡️")
        if progress_callback:
            progress_callback(85)

        await asyncio.sleep(2)

        # Bond data collection
        course_list = await cs_cutoff_bot.get_course_and_quota_details(DATABASE_URL_6, college_id=college_id)
        bond_tasks = []
        for course in course_list:
            program_id = course.get("program_id")
            bond_tasks.append(retry_task(cs_bond_data.get_data, request, course, program_id, quota="All India Quota", quota_id=2))
            bond_tasks.append(retry_task(cs_bond_data.get_data, request, course, program_id, quota="State Quota", quota_id=53))
            await asyncio.sleep(0.5)

        await asyncio.gather(*bond_tasks, return_exceptions=True)

        if status_callback:
            status_callback("🎯 All Batches Completed Successfully!")
        if progress_callback:
            progress_callback(100)

        logger.info(f"🎯 Data collection completed successfully for College ID {college_id}")

    except Exception as e:
        logger.exception(f"❌ Critical error during college data collection: {e}")

