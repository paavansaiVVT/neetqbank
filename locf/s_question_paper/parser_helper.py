from langchain_core.output_parsers import JsonOutputParser
from typing import Dict, List
import json,re, constants
from typing import Any, List, Tuple, Optional

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
    def parse_json(self, generation_text: str):
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
    
json_helpers = parse_json()