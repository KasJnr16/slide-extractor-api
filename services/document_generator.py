"""
Document generation services for creating Word documents and ZIP packages
"""
import zipfile
from io import BytesIO
from docx import Document
from docx.shared import Pt


def create_exam_package_in_memory(document_name, questions, answers):
    """
    Creates questions and answers Word docs in memory and zips them.

    Args:
        document_name: Name for the document package
        questions: List of question strings
        answers: List of answer strings

    Returns:
        BytesIO: The zip file as a BytesIO object.
    """
    # In-memory Word docs
    questions_io = BytesIO()
    answers_io = BytesIO()

    # ------------------
    # Questions doc
    # ------------------
    doc_q = Document()
    doc_q.add_heading(f"{document_name} - Questions", level=1)
    for q in questions:
        if q.strip():  # Only add non-empty lines
            para = doc_q.add_paragraph(q)
            para.paragraph_format.space_after = Pt(6)
    doc_q.save(questions_io)
    questions_io.seek(0)  # reset pointer

    # ------------------
    # Answers doc
    # ------------------
    doc_a = Document()
    doc_a.add_heading(f"{document_name} - Answers", level=1)
    for a in answers:
        if a.strip():  # Only add non-empty lines
            para = doc_a.add_paragraph(a)
            para.paragraph_format.space_after = Pt(6)
    doc_a.save(answers_io)
    answers_io.seek(0)

    # ------------------
    # Create zip in memory
    # ------------------
    zip_io = BytesIO()
    with zipfile.ZipFile(zip_io, mode="w") as zipf:
        zipf.writestr(f"{document_name}_questions.docx", questions_io.getvalue())
        zipf.writestr(f"{document_name}_answers.docx", answers_io.getvalue())
    zip_io.seek(0)

    return zip_io
