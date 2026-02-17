from locf.data_extraction.classes import file_request
from locf.data_extraction.predata import PreCourse,logger
from locf.data_extraction.postdata import PostCourse


PreCourseData = PreCourse()
PostCourseData = PostCourse()
async def all_data_dump(request:file_request,output,co_po_maps):
    """Extracts and stores all data from the request and output."""
    try: 
        file_upload_id=await PreCourseData.update_file_data(request,output)
        print(f"File Upload ID: {file_upload_id}")
        year_id=await PreCourseData.get_year_id(output)
        academic_id=await PreCourseData.get_academic_year(request,year_id)
        print(f"Academic Year ID: {academic_id}")
        semester_id=await PreCourseData.get_semester_id(output,academic_id)
        print(f"Semester ID: {semester_id}")
        sub_id=await PreCourseData.get_sub_id(output,request)
        print(f"Subject ID: {sub_id}")
        course_id=await PreCourseData.add_course_data(request, output,file_upload_id,semester_id, sub_id, year_id)
        if course_id=="Duplicate":
            logger.info("Duplicate course found, skipping further processing.")
            await PreCourseData.update_processing_status(file_upload_id,"fail")
            return course_id
        print(f"Course ID: {course_id}")
        chapter_ids = []
        if output.get("mapping_with_programme_outcomes"):
            co_po=await PostCourseData.add_co_po(co_po_maps,course_id)
        if output.get("units"):
            chapter_ids=await PostCourseData.add_units(output["units"],course_id,sub_id, request.program_id)
            print(f"Chapter IDs: {chapter_ids}")
        if output.get("course_outcomes"):
            co=await PostCourseData.add_course_outcomes(output["course_outcomes"],course_id,chapter_ids)
            co2=await PostCourseData.add_course_outcomes_po(output["course_outcomes"],course_id,chapter_ids, request.program_id)
        if output.get("textbooks"):
            textbboks=await PostCourseData.add_textbooks(output["textbooks"],course_id)
        if output.get("list_of_programs"):
            list_of_programs=await PostCourseData.add_list_of_programs(request.program_id, course_id, output["list_of_programs"])
        if output.get("reference_books"):
            reference_books=await PostCourseData.add_reference_books(output["reference_books"],course_id)
        if output.get("web_resources"):
            web_resources=await PostCourseData.add_web_resources(output["web_resources"],course_id)
        if output.get("learning_objectives"):
            lo=await PostCourseData.add_learning_objectives(output["learning_objectives"],course_id)
        course_id=await PreCourseData.add_course_data(request, output,file_upload_id,semester_id, sub_id, year_id)
        await PreCourseData.update_processing_status(file_upload_id,"success")
        print("Data successfully extracted and stored.")
        return True
    except Exception as e:
        logger.error(f"An error occurred during data extraction and storage: {e}")
        if file_upload_id:
            await PreCourseData.update_processing_status(file_upload_id,"fail")
        return False











