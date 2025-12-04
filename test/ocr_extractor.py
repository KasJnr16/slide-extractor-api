import pytesseract
from pdf2image import convert_from_bytes
from PyPDF2 import PdfReader
from PIL import Image
import io
import re
import tkinter as tk
from tkinter import filedialog, messagebox
from docx import Document   # <-- NEW

def clean_text(text):
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = text.replace("\t", " ")
    return text.strip()


def extract_pdf_text(pdf_bytes):
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception:
        return ""


def ocr_image(image: Image.Image):
    gray = image.convert("L")
    return pytesseract.image_to_string(gray, lang="eng")


def extract_docx_text(file_bytes):
    """Extract text from DOCX files."""
    try:
        file_stream = io.BytesIO(file_bytes)
        doc = Document(file_stream)
        full_text = [p.text for p in doc.paragraphs]
        return clean_text("\n".join(full_text))
    except Exception as e:
        raise ValueError(f"Error reading DOCX: {e}")


def extract_text_file(file_bytes):
    """Extract plain text from .txt files."""
    try:
        return clean_text(file_bytes.decode("utf-8"))
    except:
        return clean_text(file_bytes.decode("latin-1"))


def extract_text_from_any(file_bytes: bytes, filename: str):
    filename = filename.lower()

    # -------- PDF --------
    if filename.endswith(".pdf"):
        extracted = extract_pdf_text(file_bytes)
        if extracted and len(extracted) > 20:
            return clean_text(extracted)

        images = convert_from_bytes(file_bytes)
        ocr_text = ""
        for img in images:
            ocr_text += ocr_image(img) + "\n"
        return clean_text(ocr_text)

    # -------- Images --------
    elif filename.endswith((".jpg", ".jpeg", ".png", ".tiff")):
        img = Image.open(io.BytesIO(file_bytes))
        text = ocr_image(img)
        return clean_text(text)

    # -------- DOCX --------
    elif filename.endswith(".docx"):
        return extract_docx_text(file_bytes)

    # -------- TXT --------
    elif filename.endswith(".txt"):
        return extract_text_file(file_bytes)

    else:
        raise ValueError("Unsupported file type for extraction.")


# GUI --------------------------------------------------------

def run_file_picker():
    root = tk.Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename(
        title="Select a File",
        filetypes=[
            ("Supported files", "*.pdf *.docx *.txt *.jpg *.jpeg *.png *.tiff"),
            ("PDF files", "*.pdf"),
            ("Word files", "*.docx"),
            ("Text files", "*.txt"),
            ("Images", "*.jpg *.jpeg *.png *.tiff"),
            ("All files", "*.*")
        ]
    )

    if not file_path:
        messagebox.showinfo("No File", "No file selected.")
        return

    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        extracted = extract_text_from_any(file_bytes, file_path)

        output_window = tk.Toplevel()
        output_window.title("Extracted Text")

        text_box = tk.Text(output_window, wrap="word")
        text_box.pack(expand=True, fill="both")
        text_box.insert("1.0", extracted)

    except Exception as e:
        messagebox.showerror("Error", str(e))

    root.mainloop()


if __name__ == "__main__":
    run_file_picker()
