import google.generativeai as genai
import os
import time
import PyPDF2
from dotenv import load_dotenv

load_dotenv()
import os
import PyPDF2
import os
import re
import textwrap
from pathlib import Path
import google.generativeai as genai
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from pathlib import Path
import re
import textwrap



def wait_for_download(download_dir, timeout=30):
    """Wait for a file to be downloaded into the specified directory and validate it."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        files = os.listdir(download_dir)
        downloaded = [f for f in files if not f.endswith(".crdownload")]
        if downloaded:
            # Check each file to ensure it’s valid
            for file_name in downloaded:
                file_path = os.path.join(download_dir, file_name)
                # Check file size (should not be empty)
                if os.path.getsize(file_path) == 0:
                    print(f"Warning: {file_name} is empty")
                    continue
                # If it’s a PDF, try to open it to ensure it’s valid
                if file_name.endswith(".pdf"):
                    try:
                        with open(file_path, "rb") as f:
                            reader = PyPDF2.PdfReader(f)
                            if len(reader.pages) == 0:
                                print(f"Warning: {file_name} has no pages")
                                continue
                    except Exception as e:
                        print(f"Warning: {file_name} is not a valid PDF: {e}")
                        continue
                return downloaded
        time.sleep(1)
    raise Exception("Download did not complete within timeout")


def process_assignment(folder_path: str, completed_assignments_path:str, instruction: str, model_name: str = "gemini-2.0-flash"):
    """
    Uploads all PDF files from the specified folder to the Gemini API,
    analyzes the assignment, and generates required submission files.

    Args:
        folder_path (str): Path to the folder containing PDF files.
        instruction (str): Instruction prompt to guide content generation.
        model_name (str): Name of the Gemini model to use. Defaults to "gemini-2.0-flash".

    Returns:
        dict: Information about the assignment and generated files
    """
    wait_for_download(folder_path)

    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    model = genai.GenerativeModel(model_name=model_name)

    uploaded_files = []

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path) and filename.lower().endswith(".pdf"):
            try:
                uploaded_file = genai.upload_file(path=file_path)
                uploaded_files.append(uploaded_file)
                print(f"Uploaded: {filename}")
            except Exception as e:
                print(f"Failed to upload {filename}: {e}")

    if not uploaded_files:
        print("No PDF files were uploaded. Please check the folder path and contents.")
        return {"error": "No PDF files were uploaded"}

    analysis_instruction = """
    Please analyze this assignment carefully and provide a structured response with these sections:

    1. REQUIREMENTS: List all the core requirements for this assignment
    2. SUBMISSION_FORMAT: What file formats need to be submitted (.py, .pdf, .csv, etc.) default is pdf
    3. NUMBER_OF_FILES: How many distinct files need to be submitted always at least 1 
    4. ADDITIONAL_NOTES: Any other important information

    Always complete the homework.
    """

    analysis_prompt = [analysis_instruction] + uploaded_files

    try:
        analysis_response = model.generate_content(analysis_prompt)
        analysis_text = analysis_response.text
        print("Assignment Analysis:\n")
        print(analysis_text)

        requirements = extract_section(analysis_text, "REQUIREMENTS")
        submission_formats = extract_section(analysis_text, "SUBMISSION_FORMAT")
        num_files = extract_section(analysis_text, "NUMBER_OF_FILES")
        additional_notes = extract_section(analysis_text, "ADDITIONAL_NOTES")

        solution_prompt = [instruction] + uploaded_files
        solution_response = model.generate_content(solution_prompt)
        solution_text = solution_response.text
        print("\nGenerated Solution:\n")
        print(solution_text)

        generated_files = generate_submission_files(solution_text, completed_assignments_path, submission_formats)

        return {
            "requirements": requirements,
            "submission_formats": submission_formats,
            "number_of_files": num_files,
            "additional_notes": additional_notes,
            "generated_files": generated_files,
            "full_solution": solution_text
        }

    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}


def extract_section(text, section_name):
    """
    Extract content from a named section in the text.

    Args:
        text (str): The text to search in
        section_name (str): Section name to look for

    Returns:
        str: The extracted section content or empty string if not found
    """
    pattern = rf"{section_name}:?\s*(.*?)(?:\n\n|\n[A-Z_]+:|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""


def extract_code_blocks(text):
    """
    Extract all code blocks from the text.

    Args:
        text (str): Text containing code blocks

    Returns:
        list: List of tuples (language, code)
    """
    # Pattern to match code blocks with language specification
    # This pattern handles both ```python and ```python\n cases
    pattern = r"```([\w]*)\s*(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)

    # Debug information
    print(f"Found {len(matches)} code blocks")

    # If no matches found with the first pattern, try an alternative pattern
    if not matches:
        print("No matches found with first pattern, trying alternative...")
        pattern = r"```([^`\n]*)\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)

    # If still no matches, try without language specification
    if not matches:
        print("No matches found with second pattern, trying without language...")
        pattern = r"```\s*(.*?)```"
        code_blocks = re.findall(pattern, text, re.DOTALL)
        return [("", block) for block in code_blocks]

    # Clean up results
    clean_matches = []
    for lang, code in matches:
        # Remove any leading newlines from the code
        code = code.lstrip('\n')
        clean_matches.append((lang.strip(), code))

    return clean_matches


def guess_file_extension(language, code_content):
    """
    Guess the appropriate file extension based on language or code content.

    Args:
        language (str): The language specified in the code block
        code_content (str): The actual code content

    Returns:
        str: Appropriate file extension
    """
    language = language.lower().strip()

    extension_map = {
        "python": ".py",
        "py": ".py",
        "javascript": ".js",
        "js": ".js",
        "typescript": ".ts",
        "java": ".java",
        "c": ".c",
        "cpp": ".cpp",
        "c++": ".cpp",
        "csharp": ".cs",
        "c#": ".cs",
        "sql": ".sql",
        "html": ".html",
        "css": ".css",
        "r": ".R",
        "ruby": ".rb",
        "php": ".php",
        "go": ".go",
        "rust": ".rs",
        "swift": ".swift",
        "julia": ".jl",
        "matlab": ".m",
        "scala": ".scala",
        "kotlin": ".kt",
        "shell": ".sh",
        "bash": ".sh",
        "powershell": ".ps1",
        "markdown": ".md",
        "md": ".md",
        "xml": ".xml",
        "json": ".json",
        "yaml": ".yaml",
        "yml": ".yml",
        "tex": ".tex",
        "latex": ".tex"
    }

    if language in extension_map:
        return extension_map[language]

    if "import pandas" in code_content or "def " in code_content and ":" in code_content:
        return ".py"
    elif "function" in code_content and "{" in code_content:
        return ".js"
    elif "public class" in code_content or "import java" in code_content:
        return ".java"
    elif "#include" in code_content and ("int main" in code_content):
        return ".c" if "struct" in code_content else ".cpp"
    elif "<html" in code_content:
        return ".html"

    return ".txt"


def generate_submission_files(solution_text, output_dir, submission_formats=""):
    """
    Generate submission files based on the solution text and format requirements.
    Always convert the full_solution.md to a PDF with basic markdown formatting.

    Args:
        solution_text (str): The generated solution text
        output_dir (str): Directory to save files
        submission_formats (str): String describing required submission formats

    Returns:
        list: Paths of files that were generated
    """
    generated_files = []

    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)

    output_path = output_dir / "generated_files"
    output_path.mkdir(exist_ok=True, parents=True)

    print(f"\nSolution text length: {len(solution_text)} characters")
    print(f"First 100 characters: {solution_text[:100]}")

    code_blocks = extract_code_blocks(solution_text)
    file_suggestions = re.findall(r'`([^`]+\.(py|java|cpp|js|html|css|txt|md|json|xml))`', solution_text)
    suggested_filenames = [suggestion[0] for suggestion in file_suggestions]
    print(f"Suggested filenames: {suggested_filenames}")

    full_solution_path = output_path / "full_solution.md"
    with open(full_solution_path, 'w', encoding='utf-8') as f:
        f.write(solution_text)
    generated_files.append(str(full_solution_path))
    print(f"Saved full solution to: {full_solution_path}")

    full_solution_pdf_path = output_path / "full_solution.pdf"
    c = canvas.Canvas(str(full_solution_pdf_path), pagesize=letter)
    y = 750
    left_margin = 50
    in_code_block = False
    code_block_lines = []

    for line in solution_text.split('\n'):
        font = "Helvetica"
        font_size = 12
        line_indent = 0
        bold = False

        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            if not in_code_block and code_block_lines:
                # Render accumulated code block
                c.setFont("Courier", 10)
                for code_line in code_block_lines:
                    wrapped_lines = textwrap.wrap(code_line, width=90)
                    for wrapped_line in wrapped_lines:
                        if y < 50:
                            c.showPage()
                            c.setFont("Courier", 10)
                            y = 750
                        c.drawString(left_margin + 10, y, wrapped_line)
                        y -= 12
                code_block_lines = []
                y -= 5  # Small gap after code block
            continue
        elif in_code_block:
            code_block_lines.append(line)
            continue
        elif line.strip().startswith('# '):
            font = "Helvetica-Bold"
            font_size = 16
            line = line.strip()[2:].strip()
        elif line.strip().startswith('## '):
            font = "Helvetica-Bold"
            font_size = 14
            line = line.strip()[3:].strip()
        elif line.strip().startswith('- ') or line.strip().startswith('* '):
            line_indent = 10
            line = '• ' + line.strip()[2:].strip()
        elif '**' in line:

            bold = True
            line = re.sub(r'\*\*(.*?)\*\*', r'\1', line)

        c.setFont(font, font_size)

        wrapped_lines = textwrap.wrap(line, width=80 if font_size == 12 else 70)
        for wrapped_line in wrapped_lines:
            if y < 50:
                c.showPage()
                c.setFont(font, font_size)
                y = 750
            c.drawString(left_margin + line_indent, y, wrapped_line)
            y -= font_size + 3

        if line.strip().startswith(('# ', '## ', '- ', '* ')):
            y -= 5

    if code_block_lines:
        c.setFont("Courier", 10)
        for code_line in code_block_lines:
            wrapped_lines = textwrap.wrap(code_line, width=90)
            for wrapped_line in wrapped_lines:
                if y < 50:
                    c.showPage()
                    c.setFont("Courier", 10)
                    y = 750
                c.drawString(left_margin + 10, y, wrapped_line)
                y -= 12

    c.save()
    generated_files.append(str(full_solution_pdf_path))
    print(f"Converted full solution to PDF: {full_solution_pdf_path}")

    for i, (lang, code) in enumerate(code_blocks):
        print(f"\nCode block {i + 1}:")
        print(f"Language: '{lang}'")
        print(f"Code preview: {code[:100]}...")

        if submission_formats and '.py' in submission_formats.lower():
            filename = 'XGBoots_Titanic.py' if 'XGBoots_Titanic.py' in solution_text else f"submission_{i + 1}.py"
        elif i < len(suggested_filenames):
            filename = suggested_filenames[i]
        else:
            extension = guess_file_extension(lang, code)
            filename = f"{lang or 'code'}_submission_{i + 1}{extension}"

        code = textwrap.dedent(code).strip()

        file_path = output_path / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)

        generated_files.append(str(file_path))
        print(f"Generated file: {file_path}")

    if submission_formats:
        required_formats = re.findall(r'\.(py|java|cpp|js|html|css|csv|txt|pdf|md|json|xml)', submission_formats.lower())
        existing_formats = [Path(f).suffix[1:] for f in generated_files]

        for fmt in required_formats:
            if fmt not in existing_formats:
                filename = f"submission_{fmt}.{fmt}"
                file_path = output_path / filename
                with open(file_path, 'w', encoding='utf-8') as f:
                    if fmt == 'pdf':
                        f.write("% This is a placeholder PDF file\n% Please replace with actual content\n")
                    else:
                        f.write(f"# TODO: Complete this {fmt} file as required by the assignment\n")
                generated_files.append(str(file_path))
                print(f"Created template file for required format: {file_path}")

    return generated_files


