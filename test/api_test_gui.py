"""Updated API test GUI for the Document Processing API with all endpoints and data input."""

import json
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext

try:
    import requests
except ModuleNotFoundError:
    try:
        import tkinter.messagebox as messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Missing dependency: requests",
            "The test GUI requires the 'requests' package.\n\n"
            "Install it in your active venv with one of:\n"
            "  - pip install requests\n"
            "  - pip install -r requirements.txt\n\n"
            "Then re-run this script."
        )
    except Exception:
        pass
    raise


@dataclass
class ApiResponse:
    ok: bool
    status_code: int
    headers: Dict[str, str]
    json_data: Optional[Any] = None
    bytes_data: Optional[bytes] = None
    text_data: Optional[str] = None
    error: Optional[str] = None


class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def set_base_url(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, timeout: int = 30) -> ApiResponse:
        try:
            r = self.session.get(self._url(path), params=params, timeout=timeout)
            return self._parse(r)
        except Exception as e:
            return ApiResponse(False, 0, {}, error=str(e))

    def post_json(self, path: str, json_body: Any, params: Optional[Dict[str, Any]] = None, timeout: int = 60) -> ApiResponse:
        try:
            r = self.session.post(self._url(path), params=params, json=json_body, timeout=timeout)
            return self._parse(r)
        except Exception as e:
            return ApiResponse(False, 0, {}, error=str(e))

    def post_form_with_files(
        self,
        path: str,
        files: Dict[str, Tuple[str, bytes, str]],
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 120,
    ) -> ApiResponse:
        try:
            r = self.session.post(self._url(path), params=params, files=files, data=data or {}, timeout=timeout)
            return self._parse(r)
        except Exception as e:
            return ApiResponse(False, 0, {}, error=str(e))

    def post_multi_files(
        self,
        path: str,
        files_field_name: str,
        file_items: list[Tuple[str, bytes, str]],
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 300,
    ) -> ApiResponse:
        try:
            multi = []
            for filename, content, mime in file_items:
                multi.append((files_field_name, (filename, content, mime)))
            r = self.session.post(self._url(path), params=params, files=multi, data=data or {}, timeout=timeout)
            return self._parse(r)
        except Exception as e:
            return ApiResponse(False, 0, {}, error=str(e))

    @staticmethod
    def _parse(r: requests.Response) -> ApiResponse:
        headers = {k: v for k, v in r.headers.items()}
        ct = headers.get("content-type", "")
        if ct.startswith("application/json"):
            try:
                return ApiResponse(r.ok, r.status_code, headers, json_data=r.json())
            except Exception:
                return ApiResponse(r.ok, r.status_code, headers, text_data=r.text)
        return ApiResponse(r.ok, r.status_code, headers, bytes_data=r.content)


class ApiTestGui:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Document Processing API - Complete Test Suite")
        self.root.geometry("1400x900")

        # Use project temp directory instead of system temp
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = self.repo_root / "temp"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Setup cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.base_url_var = tk.StringVar(value="http://localhost:8080")
        self.client = ApiClient(self.base_url_var.get())

        self._build_ui()
        self._write(f"Using project temp directory: {self.temp_dir}")
        self._write("All files will be saved here and cleaned up on exit")

    def _on_closing(self):
        """Clean up project temp directory when GUI closes"""
        try:
            # Clean up files in temp directory
            for file_path in self.temp_dir.glob("*"):
                if file_path.is_file():
                    file_path.unlink()
                    self._write(f"Deleted: {file_path.name}")
            self._write(f"Cleaned up project temp directory: {self.temp_dir}")
        except Exception as e:
            print(f"Error cleaning up temp directory: {e}")
        finally:
            self.root.destroy()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Base URL:").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.base_url_var, width=40).pack(side=tk.LEFT, padx=(6, 8))
        ttk.Button(top, text="Apply", command=self._apply_base_url).pack(side=tk.LEFT)
        ttk.Button(top, text="Smoke Test", command=self._smoke).pack(side=tk.LEFT, padx=(8, 0))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(top, textvariable=self.status_var).pack(side=tk.RIGHT)

        mid = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        mid.pack(fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(mid)
        self.notebook.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_tabs()

        right = ttk.Frame(mid)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        ttk.Label(right, text="Output").pack(anchor=tk.W)
        self.output = scrolledtext.ScrolledText(right, width=50, height=45, wrap=tk.WORD)
        self.output.pack(fill=tk.BOTH, expand=True)

        btns = ttk.Frame(right)
        btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btns, text="Clear", command=lambda: self.output.delete("1.0", tk.END)).pack(side=tk.LEFT)
        ttk.Button(btns, text="Save Output", command=self._save_output_text).pack(side=tk.LEFT, padx=(6, 0))

    def _build_tabs(self) -> None:
        self._tab_health()
        self._tab_extract()
        self._tab_excel()
        self._tab_generate()
        self._tab_jobs()
        self._tab_batch()

    def _tab_health(self) -> None:
        f = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(f, text="Health")

        ttk.Button(f, text="GET /health", command=lambda: self._thread(self._call_get, "/health")).grid(row=0, column=0, sticky=tk.W)
        ttk.Button(f, text="GET /health/detailed", command=lambda: self._thread(self._call_get, "/health/detailed")).grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        ttk.Button(f, text="GET /metrics", command=lambda: self._thread(self._call_get, "/metrics")).grid(row=2, column=0, sticky=tk.W, pady=(6, 0))

        ttk.Label(f, text="History hours:").grid(row=3, column=0, sticky=tk.W, pady=(12, 0))
        self.history_hours = tk.StringVar(value="24")
        ttk.Entry(f, textvariable=self.history_hours, width=8).grid(row=3, column=0, sticky=tk.E, pady=(12, 0))
        ttk.Button(
            f,
            text="GET /health/history",
            command=lambda: self._thread(self._call_get, "/health/history", {"hours": self.history_hours.get()}),
        ).grid(row=4, column=0, sticky=tk.W, pady=(6, 0))

    def _tab_extract(self) -> None:
        f = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(f, text="Extract")

        ttk.Button(f, text="Select File + POST /extract_file", command=self._extract_any).grid(row=0, column=0, sticky=tk.W)

        ttk.Label(f, text="Advanced Excel Extraction:").grid(row=1, column=0, sticky=tk.W, pady=(12, 0))
        
        self.excel_images = tk.BooleanVar(value=True)
        self.excel_charts = tk.BooleanVar(value=True)
        self.excel_formatting = tk.BooleanVar(value=True)

        ttk.Checkbutton(f, text="Images", variable=self.excel_images).grid(row=2, column=0, sticky=tk.W)
        ttk.Checkbutton(f, text="Charts", variable=self.excel_charts).grid(row=2, column=1, sticky=tk.W)
        ttk.Checkbutton(f, text="Formatting", variable=self.excel_formatting).grid(row=2, column=2, sticky=tk.W)

        ttk.Button(f, text="Select .xlsx + POST /extract_excel/", command=self._excel_advanced).grid(row=3, column=0, sticky=tk.W, pady=(10, 0))

    def _tab_excel(self) -> None:
        f = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(f, text="Excel Generation")

        # Create a frame with two columns
        main_frame = ttk.Frame(f)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left column - buttons
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        ttk.Label(left_frame, text="Excel Generation:").pack(anchor=tk.W)
        ttk.Button(left_frame, text="POST /generate_excel (sample)", command=self._gen_excel_sample).pack(anchor=tk.W, pady=(6, 0))
        ttk.Button(left_frame, text="POST /create_excel (sample)", command=self._gen_excel_from_json).pack(anchor=tk.W, pady=(6, 0))

        ttk.Separator(left_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=12)
        ttk.Label(left_frame, text="Custom Data:").pack(anchor=tk.W)
        ttk.Button(left_frame, text="POST /generate_excel (custom)", command=self._gen_excel_custom).pack(anchor=tk.W, pady=(6, 0))
        ttk.Button(left_frame, text="POST /create_excel (custom)", command=self._gen_excel_custom_json).pack(anchor=tk.W, pady=(6, 0))

        # Right column - data input
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        ttk.Label(right_frame, text="Excel Data (JSON):").pack(anchor=tk.W)
        self.excel_data_text = scrolledtext.ScrolledText(right_frame, width=40, height=15, wrap=tk.WORD)
        self.excel_data_text.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        # Sample data
        sample_excel = {
            "sheets": [
                {
                    "name": "Sheet1",
                    "data": {
                        "A1": ["Product", "string"],
                        "B1": ["Price", "number"],
                        "C1": ["Quantity", "number"],
                        "A2": ["Apple", "string"],
                        "B2": ["1.50", "number"],
                        "C2": ["100", "number"],
                        "A3": ["Banana", "string"],
                        "B3": ["0.80", "number"],
                        "C3": ["200", "number"]
                    }
                }
            ]
        }
        self.excel_data_text.insert("1.0", json.dumps(sample_excel, indent=2))

    def _tab_generate(self) -> None:
        f = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(f, text="Document Generation")

        # Create a frame with two columns
        main_frame = ttk.Frame(f)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left column - buttons and controls
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        ttk.Label(left_frame, text="Document Generation:").pack(anchor=tk.W)
        ttk.Button(left_frame, text="POST /generate_exam_zip (sample)", command=self._gen_exam_zip).pack(anchor=tk.W, pady=(6, 0))
        ttk.Button(left_frame, text="POST /generate_document_package (sample)", command=self._gen_doc_package).pack(anchor=tk.W, pady=(6, 0))

        ttk.Separator(left_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=12)
        ttk.Label(left_frame, text="Custom Data:").pack(anchor=tk.W)
        ttk.Button(left_frame, text="POST /generate_exam_zip (custom)", command=self._gen_exam_zip_custom).pack(anchor=tk.W, pady=(6, 0))
        ttk.Button(left_frame, text="POST /generate_document_package (custom)", command=self._gen_doc_package_custom).pack(anchor=tk.W, pady=(6, 0))

        # Format controls
        ttk.Separator(left_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=12)
        ttk.Label(left_frame, text="Format Options:").pack(anchor=tk.W)
        
        ttk.Label(left_frame, text="Format:").pack(anchor=tk.W, pady=(6, 0))
        self.doc_format = ttk.Combobox(left_frame, values=["docx", "pdf", "txt", "md"], width=10)
        self.doc_format.set("docx")
        self.doc_format.pack(anchor=tk.W)

        ttk.Label(left_frame, text="Font Family:").pack(anchor=tk.W, pady=(6, 0))
        self.font_family = ttk.Combobox(left_frame, values=["Arial", "Times New Roman", "Calibri", "Verdana"], width=12)
        self.font_family.set("Arial")
        self.font_family.pack(anchor=tk.W)

        ttk.Label(left_frame, text="Font Size:").pack(anchor=tk.W, pady=(6, 0))
        self.font_size = ttk.Spinbox(left_frame, from_=8, to=24, width=8)
        self.font_size.set(12)
        self.font_size.pack(anchor=tk.W)

        # Right column - data input
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        ttk.Label(right_frame, text="Document Data (JSON):").pack(anchor=tk.W)
        self.doc_data_text = scrolledtext.ScrolledText(right_frame, width=40, height=20, wrap=tk.WORD)
        self.doc_data_text.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        # Sample data
        sample_doc = {
            "documents": {
                "report": {
                    "title": "Monthly Report",
                    "content": [
                        {"type": "heading", "text": "Sales Report", "level": 1},
                        {"type": "paragraph", "text": "This is the monthly sales report generated by the API."},
                        {"type": "heading", "text": "Summary", "level": 2},
                        {"type": "paragraph", "text": "Total sales increased by 15% compared to last month.", "bold": True}
                    ]
                }
            }
        }
        self.doc_data_text.insert("1.0", json.dumps(sample_doc, indent=2))

    def _tab_jobs(self) -> None:
        f = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(f, text="Jobs")

        ttk.Label(f, text="Job ID:").grid(row=0, column=0, sticky=tk.W)
        self.job_id_var = tk.StringVar(value="")
        ttk.Entry(f, textvariable=self.job_id_var, width=48).grid(row=1, column=0, sticky=tk.W, pady=(4, 8))
        ttk.Button(f, text="GET /job_status/{job_id}", command=self._job_status).grid(row=2, column=0, sticky=tk.W)

    def _tab_batch(self) -> None:
        f = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(f, text="Batch")

        ttk.Button(f, text="Select Files + POST /extract_batch", command=self._batch_extract).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(f, text="Select multiple files for bulk extraction", font=("TkDefaultFont", 9, "italic")).grid(row=1, column=0, sticky=tk.W, pady=(6, 0))

    def _apply_base_url(self) -> None:
        self.client.set_base_url(self.base_url_var.get())
        self._write("Base URL updated")

    def _set_status(self, s: str) -> None:
        self.status_var.set(s)
        self.root.update_idletasks()

    def _write(self, s: str) -> None:
        self.output.insert(tk.END, s + "\n")
        self.output.see(tk.END)

    def _write_json(self, obj: Any) -> None:
        self._write(json.dumps(obj, indent=2, ensure_ascii=False))

    def _save_output_text(self) -> None:
        out = self.output.get("1.0", tk.END).strip()
        if not out:
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path(self.temp_dir) / f"api_test_output_{ts}.txt"
        path.write_text(out, encoding="utf-8")
        self._write(f"Saved output to temp: {path.name}")

    def _thread(self, fn, *args, **kwargs):
        t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
        t.start()

    def _call_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> None:
        self._set_status(f"GET {path}...")
        resp = self.client.get(path, params=params)
        self._render_response(resp)
        self._set_status("Ready")

    def _render_response(self, resp: ApiResponse) -> None:
        self._write(f"Status: {resp.status_code}")
        if resp.error:
            self._write(f"Error: {resp.error}")
            return
        if resp.json_data is not None:
            self._write_json(resp.json_data)
            return
        if resp.bytes_data is not None:
            ct = resp.headers.get("content-type", "")
            self._write(f"Binary response ({len(resp.bytes_data)} bytes) content-type={ct}")
            saved = self._save_bytes_auto(resp.bytes_data, ct)
            self._write(f"Saved to {saved}")
            return
        if resp.text_data is not None:
            self._write(resp.text_data)

    def _save_bytes_auto(self, data: bytes, content_type: str) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if "zip" in content_type:
            ext = "zip"
        elif "spreadsheetml" in content_type or "ms-excel" in content_type:
            ext = "xlsx"
        else:
            ext = "bin"
        path = Path(self.temp_dir) / f"download_{ts}.{ext}"
        path.write_bytes(data)
        self._write(f"Saved to temp: {path.name}")
        return path

    def _extract_any(self) -> None:
        p = filedialog.askopenfilename(title="Select file")
        if not p:
            return
        content = Path(p).read_bytes()
        files = {"file": (Path(p).name, content, "application/octet-stream")}
        self._thread(self._call_upload, "/extract_file/", files, None)

    def _excel_advanced(self) -> None:
        p = filedialog.askopenfilename(title="Select Excel", filetypes=[("Excel", "*.xlsx *.xls *.xlsm")])
        if not p:
            return
        content = Path(p).read_bytes()
        files = {"file": (Path(p).name, content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        data = {
            "extract_images": str(self.excel_images.get()).lower(),
            "extract_charts": str(self.excel_charts.get()).lower(),
            "extract_formatting": str(self.excel_formatting.get()).lower(),
        }
        self._thread(self._call_upload, "/extract_excel/", files, data)

    def _call_upload(self, endpoint: str, files: Dict[str, Tuple[str, bytes, str]], data: Optional[Dict[str, Any]]) -> None:
        self._set_status(f"POST {endpoint}...")
        resp = self.client.post_form_with_files(endpoint, files=files, data=data)
        self._render_response(resp)
        self._set_status("Ready")

    def _gen_excel_sample(self) -> None:
        sample = {
            "sheets": [
                {
                    "name": "Sheet1",
                    "data": {
                        "A1": ["Product", "string"],
                        "B1": ["Qty", "number"],
                        "A2": ["Apples", "string"],
                        "B2": ["3", "number"],
                    },
                }
            ],
        }
        self._thread(self._call_post_json_download, "/generate_excel/", sample)

    def _gen_excel_from_json(self) -> None:
        sample = {
            "sheets": [
                {
                    "name": "Sheet1",
                    "data": {
                        "A1": ["Name", "string"],
                        "B1": ["Score", "number"],
                        "A2": ["Moji", "string"],
                        "B2": ["100", "number"],
                    },
                }
            ],
        }
        json_str = json.dumps(sample)
        self._thread(self._call_post_query_download, "/create_excel/", {"json_data": json_str})

    def _gen_excel_custom(self) -> None:
        try:
            data = json.loads(self.excel_data_text.get("1.0", tk.END))
            self._thread(self._call_post_json_download, "/generate_excel/", data)
        except json.JSONDecodeError as e:
            self._write(f"Invalid JSON: {e}")

    def _gen_excel_custom_json(self) -> None:
        try:
            json_str = self.excel_data_text.get("1.0", tk.END)
            self._thread(self._call_post_query_download, "/create_excel/", {"json_data": json_str})
        except Exception as e:
            self._write(f"Error: {e}")

    def _gen_exam_zip(self) -> None:
        questions = "Q1: What is 2+2?\nQ2: Capital of France?\n"
        answers = "A1: 4\nA2: Paris\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as qf:
            qf.write(questions)
            q_path = qf.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as af:
            af.write(answers)
            a_path = af.name
        try:
            q_bytes = Path(q_path).read_bytes()
            a_bytes = Path(a_path).read_bytes()
            files = {
                "questions_file": ("questions.txt", q_bytes, "text/plain"),
                "answers_file": ("answers.txt", a_bytes, "text/plain"),
            }
            data = {
                "document_name": "TestExam",
                "format": self.doc_format.get(),
                "font_family": self.font_family.get(),
                "font_size": int(self.font_size.get()),
            }
            self._thread(self._call_upload, "/generate_exam_zip/", files, data)
        finally:
            try:
                os.unlink(q_path)
            except Exception:
                pass
            try:
                os.unlink(a_path)
            except Exception:
                pass

    def _gen_exam_zip_custom(self) -> None:
        try:
            data = json.loads(self.doc_data_text.get("1.0", tk.END))
            # For exam zip, we need questions and answers files
            questions = "Custom Question 1?\nCustom Question 2?\n"
            answers = "Custom Answer 1\nCustom Answer 2\n"
            
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as qf:
                qf.write(questions)
                q_path = qf.name
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as af:
                af.write(answers)
                a_path = af.name
                
            try:
                q_bytes = Path(q_path).read_bytes()
                a_bytes = Path(a_path).read_bytes()
                files = {
                    "questions_file": ("questions.txt", q_bytes, "text/plain"),
                    "answers_file": ("answers.txt", a_bytes, "text/plain"),
                }
                data = {
                    "document_name": "CustomExam",
                    "format": self.doc_format.get(),
                    "font_family": self.font_family.get(),
                    "font_size": int(self.font_size.get()),
                }
                self._thread(self._call_upload, "/generate_exam_zip/", files, data)
            finally:
                try:
                    os.unlink(q_path)
                except Exception:
                    pass
                try:
                    os.unlink(a_path)
                except Exception:
                    pass
        except json.JSONDecodeError as e:
            self._write(f"Invalid JSON: {e}")

    def _gen_doc_package(self) -> None:
        content = {
            "documents": {
                "report": {
                    "title": "Report",
                    "content": [
                        {"type": "heading", "text": "Hello", "level": 1},
                        {"type": "paragraph", "text": "Generated by API."},
                    ],
                }
            }
        }
        params = {
            "document_name": "DocPackage", 
            "format": self.doc_format.get(),
            "font_family": self.font_family.get(), 
            "font_size": int(self.font_size.get()), 
            "line_spacing": 1.15
        }
        self._thread(self._call_post_json_download, "/generate_document_package/", content, params)

    def _gen_doc_package_custom(self) -> None:
        try:
            content = json.loads(self.doc_data_text.get("1.0", tk.END))
            params = {
                "document_name": "CustomDocPackage", 
                "format": self.doc_format.get(),
                "font_family": self.font_family.get(), 
                "font_size": int(self.font_size.get()), 
                "line_spacing": 1.15
            }
            self._thread(self._call_post_json_download, "/generate_document_package/", content, params)
        except json.JSONDecodeError as e:
            self._write(f"Invalid JSON: {e}")

    def _call_post_json_download(self, endpoint: str, body: Any, params: Optional[Dict[str, Any]] = None) -> None:
        self._set_status(f"POST {endpoint}...")
        resp = self.client.post_json(endpoint, json_body=body, params=params)
        self._render_response(resp)
        self._set_status("Ready")

    def _call_post_query_download(self, endpoint: str, params: Dict[str, Any]) -> None:
        self._set_status(f"POST {endpoint}...")
        resp = self.client.post_json(endpoint, json_body=None, params=params)
        self._render_response(resp)
        self._set_status("Ready")

    def _job_status(self) -> None:
        job_id = self.job_id_var.get().strip()
        if not job_id:
            return
        self._thread(self._call_get, f"/job_status/{job_id}")

    def _batch_extract(self) -> None:
        paths = filedialog.askopenfilenames(title="Select multiple files")
        if not paths:
            return
        file_items: list[Tuple[str, bytes, str]] = []
        for p in paths:
            file_items.append((Path(p).name, Path(p).read_bytes(), "application/octet-stream"))
        self._thread(self._call_batch_upload, file_items)

    def _call_batch_upload(self, file_items: list[Tuple[str, bytes, str]]) -> None:
        self._set_status("POST /extract_batch/...")
        resp = self.client.post_multi_files("/extract_batch/", "files", file_items)
        self._render_response(resp)
        self._set_status("Ready")

    def _smoke(self) -> None:
        def run():
            self._set_status("Smoke test...")
            self._render_response(self.client.get("/health"))
            self._render_response(self.client.get("/metrics"))
            self._set_status("Ready")

        self._thread(run)


def main() -> None:
    root = tk.Tk()
    style = ttk.Style()
    if "vista" in style.theme_names():
        style.theme_use("vista")
    app = ApiTestGui(root)
    root.mainloop()


if __name__ == "__main__":
    from datetime import datetime

    main()
