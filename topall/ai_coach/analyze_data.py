import asyncio,os,httpx,constants,re,json, time, aiohttp
import pandas as pd
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text  # Explicitly mark SQL query as text
from dotenv import load_dotenv
from langchain_community.storage import RedisStore
from langchain_community.utilities.redis import get_client
from question_banks.db2 import retry_on_failure
load_dotenv()


# Database forgien key constants
question_types = {
    "direct_concept_based": 1,
    "assertion_reason": 2,
    "numerical_problem": 3,
    "Mixed": 4,
    "multiple_correct_answer": 5,
    "matching_type": 6,
    "comprehension_type": 7,
    "case_study_based": 8,
    "statement_based": 9,
    "True_false type": 10,
    "single_correct_answer":11
}


class StudentData:  
    def __init__(self):
        self.TOPALL_WEEKAREAS_API = os.getenv("TOPALL_WEEKAREAS_API")
        self.TOPALL_TOPIC_NAMES_API = os.getenv("TOPALL_TOPIC_NAMES_API")
        self.client = get_client(redis_url=os.getenv("REDIS_URL"))
        self.redis_store = RedisStore(client=self.client, ttl=constants.TTL)
        # Engine and session for DB 3 (topics)
        self.engine = create_async_engine(os.getenv("DATABASE_URL_3"), echo=False,pool_size=100,max_overflow=50,pool_timeout=60,pool_recycle=1800)
        self.SessionLocal = sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

        # Engine and session for DB 4 (questions info)
        self.engine2 = create_async_engine(os.getenv("DATABASE_URL_4"), echo=False,pool_size=100,max_overflow=50,pool_timeout=60,pool_recycle=1800)
        self.SessionLocal2 = sessionmaker(self.engine2, expire_on_commit=False, class_=AsyncSession)


    async def get_student_data(self,student_id):
        """Fetch student data """
        try:
            # Try fetching from cache
            cached_data =await self.redis_store.amget([student_id])
            if cached_data[0]:
                print("✅ Data fetched from cache")
                return cached_data[0].decode()
            # Call both async functions concurrently
            topics, decoded_data = await asyncio.gather(self.weak_areas_with_topic_names(student_id),self.get_weaker_pattern(student_id))
            if isinstance(topics, dict or list) and topics:
                weakness_data =topics 
                weakness_data = [topics] + decoded_data
            elif isinstance(topics,set):
                weakness_data = decoded_data+list(topics)
            else:
                weakness_data = decoded_data
            # Store in cache
            await self.redis_store.amset([(student_id, str(weakness_data))])
            print("✅ Data computed and cached")
            return weakness_data
        except Exception as e:
            print(f"Error fetching student data: {e}")
            return None
    
    async def get_weaker_pattern(self,student_id):
        try:    
            qids=await self.get_student_analysis(student_id)    # Fetch student attempted questions
            correct_qids, wrong_qids = qids["correct_qids"], qids["wrong_qids"]
            total_qids=correct_qids + wrong_qids
            wrong_data, total_data = await asyncio.gather(self.get_question_details(wrong_qids),self.get_question_details(total_qids))
            wrong_data_df=pd.DataFrame(wrong_data)
            total_data_df=pd.DataFrame(total_data)
            all_data=[]
            for x in total_data_df.columns[3:]:
                result=self.calulate_ratio(x,total_data_df,wrong_data_df) # Calculate error ratios for each category
                data={x:result}
                all_data.append(data)
            decoded_data=await self.decode_data(all_data)
            return decoded_data
        except Exception as e:
            print(f"Error fetching student analysis: {e}")
            return None

    
    @retry_on_failure    
    async def get_question_details(self,question_ids):
        """Fetch details of wrong question IDs from MySQL database."""
        try:
            if not question_ids:
                print("No questions found.")
                return {}
            async with self.SessionLocal() as session:
                # Use SQLAlchemy text() for raw query
                query = text(f"""
                    SELECT vr_ques_id, vr_chapter_id, vr_difficulty, vr_ques_type, cognitive_level,vr_topic_id
                    FROM vr_questions WHERE vr_ques_id IN ({','.join(map(str, question_ids))})""")
                result = await session.execute(query)
                question_details = [{"question_id":row[0],"chapter_id": row[1],"vr_topic_id":row[5],"difficulty": row[2],"question_type": row[3],"cognitive_level": row[4]} for row in result.fetchall()]
            return question_details
        except Exception as e:
            print(f"Error fetching question details: {e}")
 
    def calulate_ratio(self,category,total_data_df,wrong_data_df):
        try:
            # Group total attempts by the specified category
            total_by_cat = total_data_df.groupby(category).size().reset_index(name="total_questions")
            # Group wrong attempts by the specified category
            wrong_by_cat = wrong_data_df.groupby(category).size().reset_index(name="wrong_questions")
            # Merge ensuring all categories are included
            performance = pd.merge(total_by_cat, wrong_by_cat, on=category, how="left")
            performance["wrong_questions"] = performance["wrong_questions"].fillna(0)
            performance["wrong_ratio"] = performance["wrong_questions"] / performance["total_questions"]
            # Sort by wrong_ratio in descending order
            performance_sorted = performance.sort_values(by="wrong_ratio", ascending=False)
            performance_filtered = performance_sorted[performance_sorted[category] != 0]
            # Extract only the top two values from the specified category
            #top_one_values = performance_filtered[category].head(1).tolist()
            top3_items = performance_filtered[category].head(3).tolist()
            valid_top_items = [item for item in top3_items if str(item).strip() != ""]

            if len(valid_top_items) >= 1:
                top_one_value = valid_top_items[0]
            else:
                top_one_value = None
            return [top_one_value] if top_one_value is not None else []

            #return top_one_values
        except Exception as e:
            print(f"Error calculating ratio: {e}")

    @retry_on_failure
    async def get_chapter_mapping(self,chapter_ids):
        """
        Query the database table `vr_chapter_det` to get a mapping from 
        chapter_id (vr_chapter_id) to chapter name (vr_chapter).
        """
        try:
            mapping = {}
            # Create a session and execute a raw SQL query
            async with self.SessionLocal()  as session:
                # The query returns rows with vr_chapter_id and vr_chapter
                query = text("SELECT vr_chapter_id, vr_chapter FROM vr_chapter_det WHERE vr_chapter_id IN :ids")
                # Bind the chapter_ids as a tuple (important for the IN clause)
                query = query.bindparams(ids=tuple(chapter_ids))
                result = await session.execute(query)
                rows = result.fetchall()
                # Build the mapping; converting id to string for consistency with topic mapping keys
                mapping = {str(row.vr_chapter_id): row.vr_chapter for row in rows}
            await self.engine.dispose()
            return mapping
        except Exception as e:
            print(f"Error fetching chapter mapping: {e}")
            return {}


    async def decode_data(self, total_data):
        """
        Decode all fields in total_data:
        - 'cognitive_level' and 'question_type' are decoded via dictionaries.
        - 'vr_topic_id' is decoded by posting to an external API.
        - 'chapter_id' is decoded by querying the database.
        """
        try:
            cognitive_levels_reverse = {v: k for k, v in constants.cognitive_levels.items()}
            question_types_reverse = {v: k for k, v in question_types.items()}
            difficulty_level_reverse = {v: k for k, v in constants.difficulty_level.items()}

            # Extract topic IDs and chapter IDs
            topic_ids = []
            chapter_ids = []
            for entry in total_data:
                if "vr_topic_id" in entry:
                    topic_ids.extend(entry["vr_topic_id"])
                if "chapter_id" in entry:
                    chapter_ids.extend(entry["chapter_id"])

            # Decode topic IDs via API
            topic_mapping = {}
            if topic_ids:
                headers = {"Content-Type": "application/json"}
                payload = {"topicIds": topic_ids}
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(self.TOPALL_TOPIC_NAMES_API, json=payload, headers=headers)
                    if response.status_code == 200:
                        api_response = response.json()
                        topic_mapping = {str(item["topicId"]): item["topicName"] for item in api_response}
                    else:
                        print(f"Failed to fetch topic names: {response.status_code}, {response.text}")
                except Exception as e:
                    print(f"Error while fetching topic names: {e}")

            # Decode chapter IDs via DB query
            chapter_mapping = {}
            if chapter_ids:
                chapter_mapping = await self.get_chapter_mapping(chapter_ids)

            # Decode all fields
            decoded_data = []
            for entry in total_data:
                key = list(entry.keys())[0]
                values = entry[key]
                if key == "cognitive_level":
                    decoded_values = [cognitive_levels_reverse.get(val, val) for val in values]
                elif key == "question_type":
                    decoded_values = [question_types_reverse.get(val, val) for val in values]
                elif key == "difficulty":
                    decoded_values = [difficulty_level_reverse.get(int(val), val) for val in values]
                elif key == "vr_topic_id":
                    decoded_values = [topic_mapping.get(str(val), f"Unknown_Topic_{val}") for val in values]
                elif key == "chapter_id":
                    decoded_values = [chapter_mapping.get(str(val), f"Unknown_Chapter_{val}") for val in values]
                else:
                    decoded_values = values
                decoded_data.append({key: decoded_values})
            return decoded_data
        except Exception as e:
            print(f"Error decoding data: {e}")


    @retry_on_failure
    async def get_student_analysis(self,student_id):
        try:
            async with self.SessionLocal() as session:
                query = text("""
                    SELECT nta.correct_qids, nta.wrong_qids
                    FROM new_testwise_analysis nta
                    LEFT JOIN new_self_exam_results nser ON nta.student_id = nser.student_id
                    WHERE nta.student_id = :student_id
                """)
                result = await session.execute(query, {"student_id": student_id})
                rows = result.fetchall()
                correct_set = set()
                wrong_set = set()

                for row in rows:
                    # Clean correct question IDs
                    if row.correct_qids:
                        ids = row.correct_qids.split(',')
                        for qid in ids:
                            clean_qid = re.sub(r'\(\d+\)', '', qid).strip()
                            if clean_qid:
                                correct_set.add(clean_qid)
                    # Clean wrong question IDs
                    if row.wrong_qids:
                        ids = row.wrong_qids.split(',')
                        for qid in ids:
                            clean_qid = re.sub(r'\(\d+\)', '', qid).strip()
                            if clean_qid:
                                wrong_set.add(clean_qid)

                return {"correct_qids": list(correct_set),"wrong_qids": list(wrong_set)}
        except Exception as e:
            print(f"Error fetching student analysis: {e}")
            return None
  
    async def weak_areas(self,user_id):
        sub_ids = [2, 3, 4, 5, 6]
        async def fetch_weak_area(session, user_id, sub_id):
            url = f"{self.TOPALL_WEEKAREAS_API}/{user_id}/{sub_id}"
            try:
                async with session.get(url) as response:
                    response.raise_for_status()
                    return sub_id, await response.json()
            except Exception as e:
                print(f"Error fetching data for subject {sub_id}: {e}")
                return sub_id, None
        weak_areas_data = {}
        async with aiohttp.ClientSession() as session:
            tasks = [fetch_weak_area(session, user_id, sub_id) for sub_id in sub_ids]
            results = await asyncio.gather(*tasks)
            weak_areas_data = {sub_id: data for sub_id, data in results}
        return weak_areas_data

    @retry_on_failure    
    async def get_chapter_and_topics(self,topic_ids: list):
        try:
            async with self.SessionLocal2() as session:
                topic_query = text("""
                    SELECT DISTINCT
                        t.vr_topic_id AS topic_id,
                        t.vr_topic AS topic_name,
                        c.vr_chapter_id AS chapter_id,
                        c.vr_chapter AS chapter_name
                    FROM vr_topic t
                    LEFT JOIN vr_questions q ON q.vr_topic_id = t.vr_topic_id
                    LEFT JOIN vr_chapter_det c ON c.vr_chapter_id = q.vr_chapter_id
                    WHERE t.vr_topic_id IN :topic_ids
                """)
                topic_result = await session.execute(topic_query, {"topic_ids": tuple(topic_ids)})
                topic_rows = topic_result.mappings().all()

                chapter_ids = list({row["chapter_id"] for row in topic_rows if row["chapter_id"]})
                count_query = text("""
                    SELECT
                        c.vr_chapter_id AS chapter_id,
                        COUNT(DISTINCT q.vr_ques_id) AS question_count
                    FROM vr_chapter_det c
                    LEFT JOIN vr_questions q ON q.vr_chapter_id = c.vr_chapter_id
                    LEFT JOIN vr_previous_year_ques pyq ON pyq.vr_ques_id = q.vr_ques_id
                    LEFT JOIN vr_previous_year py ON py.vr_sno = pyq.vr_paper_id
                    WHERE
                        c.vr_chapter_id IN :chapter_ids
                        AND py.vr_stream_id = 1
                        AND py.vr_course_id = 1
                    GROUP BY c.vr_chapter_id
                """)
                count_result = await session.execute(count_query, {"chapter_ids": tuple(chapter_ids)})
                count_rows = count_result.mappings().all()
                count_map = {row["chapter_id"]: row["question_count"] for row in count_rows}

            grouped = {}
            for row in topic_rows:
                chap_id = row["chapter_id"]
                if not chap_id:
                    continue
                if chap_id not in grouped:
                    grouped[chap_id] = {
                        #"chapter_id": chap_id,
                        #"chapter": row["chapter_name"],
                        "questions_appeared_in_exams": count_map.get(chap_id, 0),"topics": set()}
                grouped[chap_id]["topics"].add(row["topic_name"])

            final_result = []
            for data in grouped.values():
                data["topics"] = sorted(list(data["topics"]))
                final_result.append(data)
            return final_result

        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    async def weak_areas_with_topic_names(self,user_id):
            try:
                weak_areas_data = await self.weak_areas(user_id)  # Fetch weak areas
                topic_ids = set()  # Use a set to avoid duplicates
                for sub_id, topics in weak_areas_data.items():
                    for topic in topics:
                        topic_ids.add(topic["topicId"])  # Collect all topic IDs
                if not topic_ids:
                    print(f"No weak topics found for the user id :{user_id}.")
                    return {"User Dont have any specific weaker topic or chapter or subject."}
                topic_info_list = await self.get_chapter_and_topics(list(topic_ids))
                return {"weaker_topic_details": topic_info_list}
            except Exception as e:
                print(f"Error fetching weak areas with topic names: {e}")


# Instantiate the StudentData class
student_data=StudentData()
