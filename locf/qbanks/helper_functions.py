from langchain_core.output_parsers import JsonOutputParser
#from cs_qbanks import cs_classes,cs_db_connect
from locf.qbanks import classes, db
from typing import Dict, List
import json,re, constants, difflib
from typing import Any, List, Tuple, Optional

try:
    from classes import required_items as _REQUIRED_ITEMS
except Exception:
    _REQUIRED_ITEMS = None


class parse_json:
    """
    A class to parse JSON output from generation text, clean it,
    and return a list of valid JSON objects.
    """

    # ---- configuration ----
    _FIELDS_TO_ESCAPE = ['question', 'explanation', 'correct_answer']
    _PART_ANCHOR = re.compile(r'part:\s*\{', re.IGNORECASE)
    _CTRL_RE = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F]+')

    def __init__(self):
        self.parser = JsonOutputParser() if JsonOutputParser else None
        self.fields = ['question', 'explanation']

    # ---------------- core API ----------------
    def parse_json(self, generation_text: str, mode: str = "non-ocr"):
        """
        Parses the JSON output from the generation text, cleans it,
        and returns a list of valid JSON objects.
        """
        # 0) Basic sanitation: strip control chars that often break JSON loads
        cleaned_output = self._CTRL_RE.sub('', generation_text)

        # 1) Try the "pure JSON array" fast path
        arr = self._extract_outer_array(cleaned_output)
        if arr is not None:
            objs = arr
        else:
            # 2) Try your existing JsonOutputParser first (if available)
            objs = None
            if self.parser:
                try:
                    objs = self.parser.invoke(cleaned_output)
                except Exception:
                    pass

            # 3) Try escaping inner quotes minimally
            if objs is None:
                try:
                    result = self.escape_json_inner_quotes(cleaned_output)
                    objs = self.parser.invoke(result) if self.parser else None
                except Exception:
                    objs = None

            # 4) Final robust pass: stream objects / repair (handles noisy "part:{...}, error ..." logs)
            if objs is None:
                objs = self.parse_cleaner_def(cleaned_output)

        # 5) Optional: filter by required items if present and mode requires it
        if mode == "non-ocr" and _REQUIRED_ITEMS:
            objs = [q for q in objs if all(k in q for k in _REQUIRED_ITEMS)]

        return objs

    # ---------------- robust cleaner ----------------
    def parse_cleaner_def(self, raw_string: str) -> List[Any]:
        """
        Prefer parsing a full JSON array; if that fails, stream-extract balanced
        objects while respecting strings/escapes, apply minimal repairs, and load.
        Also supports noisy logs like:  part:{ ... }, error ...
        """
        s = self.clean_markdown(raw_string)

        # 1) Outer array attempt
        arr = self._extract_outer_array(s)
        if arr is not None:
            return arr

        # 2) No array: try log-style "part:{...}" extraction first.
        objs = self._extract_from_part_logs(s)
        if objs:
            return objs

        # 3) Generic streaming of balanced objects anywhere in s.
        objs, i, n = [], 0, len(s)
        while i < n:
            start = s.find("{", i)
            if start == -1:
                break

            try:
                candidate, end_pos = self._extract_braced_json(s, start)
                i = end_pos
            except ValueError:
                # unbalanced; stop scanning
                break

            candidate = candidate.strip()
            if not candidate:
                continue

            # Repairs: trailing commas, backslashes, inner quotes
            candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
            candidate = self._fix_trailing_backslashes_in_strings(candidate)

            try:
                objs.append(json.loads(candidate))
                continue
            except json.JSONDecodeError:
                repaired = self.escape_json_inner_quotes(candidate, fields=self.fields + ['correct_answer'])
                repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
                repaired = self._fix_trailing_backslashes_in_strings(repaired)
                try:
                    objs.append(json.loads(repaired))
                except json.JSONDecodeError as e:
                    # keep going; noisy logs are expected
                    print(f"part:{candidate}, error {e}")
                    continue

        return objs

    # ---------------- helpers ----------------
    def _extract_outer_array(self, s: str) -> Optional[List[Any]]:
        """
        Try to detect and parse the largest outer JSON array in `s`.
        Returns list on success, None otherwise.
        """
        # First, prefer fenced code JSON (```json ... ```)
        s = self.clean_markdown(s)

        if "[" not in s or "]" not in s:
            return None

        start, end = s.find("["), s.rfind("]") + 1
        arr = s[start:end]
        # Minimal normalizations
        arr = arr.replace("“", '"').replace("”", '"').replace("’", "'")
        arr = self._CTRL_RE.sub('', arr)
        arr = re.sub(r",\s*([}\]])", r"\1", arr)

        try:
            return json.loads(arr)
        except json.JSONDecodeError:
            return None

    def _extract_from_part_logs(self, log_text: str) -> List[Any]:
        """
        Extract objects that are logged as:  part:{...}, error ...
        """
        objs: List[Any] = []
        pos = 0
        while True:
            m = self._PART_ANCHOR.search(log_text, pos)
            if not m:
                break

            brace_idx = log_text.find('{', m.end() - 1)
            if brace_idx == -1:
                break

            try:
                json_text, end_pos = self._extract_braced_json(log_text, brace_idx)
            except ValueError:
                # couldn't find a balanced object; stop scanning
                break

            pos = end_pos  # advance

            # Repairs for each extracted object
            candidate = re.sub(r",\s*([}\]])", r"\1", json_text)
            candidate = self._fix_trailing_backslashes_in_strings(candidate)

            try:
                objs.append(json.loads(candidate))
            except json.JSONDecodeError:
                repaired = self.escape_json_inner_quotes(candidate, fields=self._FIELDS_TO_ESCAPE)
                repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
                repaired = self._fix_trailing_backslashes_in_strings(repaired)
                try:
                    objs.append(json.loads(repaired))
                except json.JSONDecodeError as e:
                    print(f"part:{candidate}, error {e}")
                    continue

        return objs

    def _extract_braced_json(self, s: str, start_idx: int) -> Tuple[str, int]:
        """
        Given string s and index of a '{', return (json_text, end_index_after_json)
        using brace matching with string/escape awareness.
        """
        i = start_idx
        depth = 0
        in_str = False
        esc = False

        while i < len(s):
            ch = s[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        return s[start_idx:i+1], i + 1
            i += 1

        raise ValueError("Unbalanced braces: couldn't find the end of a JSON object.")

    # ---- your existing repair utilities (kept + refined) ----
    def _fix_trailing_backslashes_in_strings(self, s: str) -> str:
        """
        Ensure string literals don't end with an odd number of backslashes,
        which would escape the closing quote → unterminated string.
        """
        def fix(m):
            prefix, content = m.group(1), m.group(2)
            tail = re.search(r"(\\+)$", content)
            bs = len(tail.group(1)) if tail else 0
            if bs % 2 == 1:
                content += "\\"
            return f'{prefix}{content}"'

        # target the fields most prone to inner quotes; apply generic string guard as well
        s = re.sub(
            r'("(?:question|explanation|correct_answer)"\s*:\s*")((?:[^"\\]|\\.)*?)"',
            fix, s, flags=re.S
        )
        return s

    def clean_markdown(self, json_string: str) -> str:
        """
        Return inner code-fence content if present, else the original string.
        """
        _json_markdown_re = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
        m = _json_markdown_re.search(json_string.strip())
        return (m.group(1) if m else json_string).strip()

    def escape_json_inner_quotes(self, json_str: str, fields=None) -> str:
        """
        Escape only unescaped inner double-quotes within specific fields,
        without double-escaping already-escaped quotes.
        """
        if fields is None:
            fields = self._FIELDS_TO_ESCAPE

        s = json_str
        for field in fields:
            pattern = re.compile(rf'("{field}"\s*:\s*")((?:[^"\\]|\\.)*?)(")', re.S)
            def _esc(m):
                head, val, tail = m.groups()
                # replace only raw " that are not already escaped
                val = re.sub(r'(?<!\\)"', r'\"', val)
                return f"{head}{val}{tail}"
            s = pattern.sub(_esc, s)
        return s
    
class HelperFunctions():
    """A class containing helper functions for processing data."""
    def __init__(self):
        self.percentage_weightage=90
        self._CO_RE = re.compile(r"co[\s\-\:_]*([0-9]+)$", re.IGNORECASE)

    def check_options(self, all_data):
        """Checks if the 'correct_answer' is present in 'options' and assigns the correct option number."""
        cleaned_data = []
        for item in all_data:
            try:
                correct_answer = item['correct_answer']
                if correct_answer in item['options']:
                    correct_opt = item['options'].index(correct_answer) + 1
                    item['correct_option'] = correct_opt
                    cleaned_data.append(item)
                else:
                    print(f"⚠️ Skipping: question ID: {item.get('q_id')} Correct answer '{correct_answer}' not found in options {item.get('options')}")
                    continue
            except Exception as e:
                print(f"❌ Error processing item: {e}")
        return cleaned_data
    
    def calculate_total_tokens(self, generation_tokens:dict, QC_tokens:dict):
        try:
            total_tokens = {
                'total_input_tokens': generation_tokens['input_tokens'] + QC_tokens['input_tokens'],
                'total_output_tokens': generation_tokens['output_tokens'] + QC_tokens['output_tokens'],
                'total_tokens': generation_tokens['total_tokens'] + QC_tokens['total_tokens']
            }
            return total_tokens
        except Exception as e:
            print(f"Error occurred at calculate_total_tokens: {e}")
            total_tokens = {'total_input_tokens': 0,'total_output_tokens': 0,'total_tokens': 0}
            return total_tokens
        
    def _extract_tokens(self, message) -> Dict[str, int]:
        """
        Return a unified token dict for an LLM message across providers.
        Tries usage_metadata, response_metadata, and additional_kwargs.
        """
        out = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
        }

        try:
            # 1) Preferred: LangChain's normalized usage
            um = getattr(message, "usage_metadata", None)
            if isinstance(um, dict):
                out["total_input_tokens"] += int(um.get("input_tokens") or um.get("prompt_tokens") or um.get("promptTokenCount") or 0)
                out["total_output_tokens"] += int(um.get("output_tokens") or um.get("completion_tokens") or um.get("candidatesTokenCount") or 0)
                out["total_tokens"]     += int(um.get("total_tokens") or um.get("totalTokenCount") or 0)

            # 2) Provider-specific data under response_metadata
            rm = getattr(message, "response_metadata", None) or {}
            if isinstance(rm, dict):
                tok = rm.get("token_usage") or rm.get("usage_metadata") or rm.get("usage") or {}
                out["total_input_tokens"] += int(tok.get("prompt_tokens") or tok.get("input_tokens") or tok.get("promptTokenCount") or 0)
                out["total_output_tokens"] += int(tok.get("completion_tokens") or tok.get("output_tokens") or tok.get("candidatesTokenCount") or 0)
                ttl = int(tok.get("total_tokens") or tok.get("totalTokenCount") or 0)
                if ttl:
                    out["total_tokens"] += ttl

            # 3) Sometimes tucked in additional_kwargs
            ak = getattr(message, "additional_kwargs", None) or {}
            if isinstance(ak, dict):
                um2 = ak.get("usage") or ak.get("usage_metadata") or ak.get("usageMetadata") or {}
                out["total_input_tokens"] += int(um2.get("prompt_tokens") or um2.get("input_tokens") or um2.get("promptTokenCount") or 0)
                out["total_output_tokens"] += int(um2.get("completion_tokens") or um2.get("output_tokens") or um2.get("candidatesTokenCount") or 0)
                out["total_tokens"]        += int(um2.get("total_tokens") or um2.get("totalTokenCount") or 0)
        except Exception:
            pass

        if out["total_tokens"] == 0:
            out["total_tokens"] = out["total_input_tokens"] + out["total_output_tokens"]
        return out

        
    def merge_data(self,gen_output, qc_output):
        # Normalize keys in qc_output as strings for flexible matching
        qc_dict = {str(item['q_id']): item for item in qc_output}

        merged_data = []
        for item in gen_output:
            q_id_str = str(item['q_id'])  # Ensure string key for comparison
            if q_id_str in qc_dict:
                item.update(qc_dict[q_id_str])  # Merge QC info
            merged_data.append(item)

        return merged_data
    
    def closest_topic(self, query: str, choices: List[str], threshold: float = 0.7) -> Tuple[Optional[str], float]:
        """
        Return (best_match, score) where best_match is the closest string in `choices` to `query`.
        """
        def _tokens(s: str) -> List[str]:
            return re.findall(r"\w+", s.lower())

        def _token_set_ratio(a: str, b: str) -> float:
            A, B = set(_tokens(a)), set(_tokens(b))
            if not A or not B:
                return 0.0
            common = A & B
            if not common:
                return 0.0
            common_str = " ".join(sorted(common))
            a_str = " ".join(sorted(A))
            b_str = " ".join(sorted(B))
            r1 = difflib.SequenceMatcher(None, common_str, a_str).ratio()
            r2 = difflib.SequenceMatcher(None, common_str, b_str).ratio()
            return max(r1, r2)  # mirrors fuzzywuzzy's token_set_ratio behavior

        def _seq_ratio(a: str, b: str) -> float:
            return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

        best = None
        best_score = 0.0
        eps = 1e-9

        for cand in choices:
            score = max(_token_set_ratio(query, cand), _seq_ratio(query, cand))
            # Tie-break: prefer longer candidate if scores are effectively equal
            if (score > best_score + eps) or (abs(score - best_score) <= eps and best is not None and len(cand) > len(best)):
                best, best_score = cand, score

        if best_score < threshold:
            return None, best_score
        return best, best_score       

    def find_topic(self, query: str, choices: List[str], *, threshold: float = 0.8, case_insensitive_exact: bool = True) -> Tuple[Optional[str], float, bool]:
        """
        Returns (match, score, is_exact).
        1) Try exact match first (case-insensitive by default).
        2) If not found, use closest_topic().
        """
        q_norm = query.strip()
        if case_insensitive_exact:
            lookup = {c.strip().casefold(): c for c in choices}
            hit = lookup.get(q_norm.casefold())
            if hit is not None:
                return hit, 1.0, True
        else:
            if q_norm in choices:
                return q_norm, 1.0, True

        best, score = self.closest_topic(q_norm, choices, threshold=threshold)
        return best, score, False

    async def cal_percentage(self, uuid, passed:int, total:int):
        try:
            if total == 0:
                return 0
            percentage = (passed / total) * self.percentage_weightage
            #print(f"Percentage calculated: {percentage}%")
            #await db.update_progress(uuid, percentage)
            return round(percentage, 2)
        except Exception as e:
            print(f"Error calculating percentage: {e}")
            return 0     

    def _normalize_co(self, code: str) -> str:
        code = (code or "").strip()
        m = self._CO_RE.search(code)
        return f"CO{int(m.group(1))}" if m else code.upper()

    async def key_function(self, request: classes.QuestionRequest, passed_qc):
        # Caches
        chapter_cache: dict[str, tuple[int, int]] = {}             # chapter_name -> (subject_id, chapter_id)
        topic_cache: dict[str, tuple[int, int, int, int]] = {}     # topic_name -> (p_id, s_id, c_id, t_id)
        course_cache: dict[tuple[int, int], tuple[int, int]] = {}  # (program_id, subject_id) -> (course_id, semester_id)
        co_cache: dict[tuple[int, int, str], int] = {}             # (course_id, chapter_id, co_code) -> co_id

        try:
            passed_items: list[dict] = []

            for entry in passed_qc:
                try:
                    # --- Resolve Chapter (cached) ---
                    chapter_name = entry["chapter_name"]
                    if chapter_name in chapter_cache:
                        subject_id, chapter_id = chapter_cache[chapter_name]
                    else:
                        subject_id, chapter_id = await db.get_chapters(
                            chapter_name,
                            retry_id=0,
                            question=entry["question"],
                            chapter_list=request.chapter_name,
                            subject_id=request.subject_id,
                            program_id=request.program_id,
                        )
                        if subject_id is None or chapter_id is None:
                            db.logger.warning(f"Skipping question due to unresolved chapter '{chapter_name}'")
                            continue
                        chapter_cache[chapter_name] = (subject_id, chapter_id)

                    # --- Resolve Topic (cached, fuzzy) ---
                    topic_name = entry["topic_name"]
                    if topic_name in topic_cache:
                        p_id, s_id, c_id, t_id = topic_cache[topic_name]
                    else:
                        valid_topic, score, is_exact = self.find_topic(
                            topic_name,
                            request.topic_name,
                            threshold=0.8,
                            case_insensitive_exact=True,
                        )
                        p_id, s_id, c_id, t_id = await db.get_topic(
                            program_id=request.program_id,
                            subject_id=subject_id,
                            chapter_id=chapter_id,
                            topic_name=valid_topic,
                        )
                        if t_id is None:
                            db.logger.warning(f"Skipping question due to unresolved topic '{topic_name}'")
                            continue
                        topic_cache[topic_name] = (p_id, s_id, c_id, t_id)

                    # --- Resolve Course (cached) ---
                    course_key = (request.program_id, subject_id)
                    if course_key in course_cache:
                        course_id, semester_id = course_cache[course_key]
                    else:
                        course_id, semester_id = await db.get_courses(
                            subject_id=subject_id,
                            program_id=request.program_id,
                        )
                        # Optional: if either is None, you may want to skip/log
                        if course_id is None:
                            db.logger.warning(
                                f"Skipping question due to unresolved course (program_id={request.program_id}, subject_id={subject_id})"
                            )
                            continue
                        course_cache[course_key] = (course_id, semester_id)

                    # --- Resolve Course Outcome (cached, with fallback) ---
                    co_code = self._normalize_co(entry.get("course_outcome", ""))
                    co_key = (course_id, c_id, co_code)  # c_id is the chapter_id resolved via topic

                    if co_key in co_cache:
                        course_outcomes_id = co_cache[co_key]
                    else:
                        course_outcomes_id = await db.get_course_outcomes(
                            course_outcome=co_code,
                            course_id=course_id,
                            chapter_id=c_id,
                        )

                        if course_outcomes_id is None:
                            db.logger.warning(
                                f"trying attempt two to resolved course outcome '{entry.get('course_outcome')}'"
                            )
                            # Fallback resolver (e.g., pick any/default CO for chapter/course)
                            course_outcomes_id = await db.get_course_outcomes2(
                                chapter_id=chapter_id,
                                course_id=course_id,
                            )

                        if course_outcomes_id is None:
                            db.logger.warning(
                                f"Skipping question due to unresolved course outcome '{entry.get('course_outcome')}'"
                            )
                            continue

                        # Cache the successful CO resolution
                        co_cache[co_key] = course_outcomes_id
                    
                    # --- Extract question-specific fields (MUST be outside cache block!) ---
                    try:
                        options = entry["options"]
                    except:
                        options = ["", "", "", ""]
                        
                    try:
                        concepts = entry["concepts"]
                    except:
                        concepts = entry['keywords']
                        
                    try:
                        correct_option = entry["correct_option"]
                    except:
                        correct_option = ""
                            
                    

                    # --- Prepare question payload ---
                    question = {
                        "q_id": entry["q_id"],
                        "question": entry["question"],
                        "explanation": entry["explanation"],
                        "correct_answer": entry["correct_answer"],
                        "options": options,
                        "chapter_name": entry["chapter_name"],
                        "topic_name": entry["topic_name"],
                        "question_type": classes.question_type_dict[request.question_type.lower()],
                        "estimated_time": entry["estimated_time"],
                        "concepts": concepts,
                        "QC": entry["QC"],
                        "correct_option": correct_option,
                        "t_id": t_id,
                        "s_id": s_id,
                        "c_id": c_id,
                        "p_id": request.program_id,
                        "co_id": course_outcomes_id,
                        "course_id": course_id,
                        "difficulty": classes.difficulty_level[entry["difficulty"].lower()],
                        "cognitive_level": classes.cognitive_levels[entry["cognitive_level"].lower()],
                        "stream": 1,
                        "model": constants.model_dict[request.model],
                    }
                    passed_items.append(question)

                except Exception as e:
                    print(f"Error in (key_function) preparing question: {entry}. Error: {e}")
                    continue

            return passed_items

        except Exception as e:
            print(f"An error occurred in Key Function: {e}")
            raise

# Initialize the helper functions and JSON parser
helpers=HelperFunctions()
json_helpers=parse_json()