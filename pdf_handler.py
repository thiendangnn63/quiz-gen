import os
import json
import re
from pypdf import PdfReader, PdfWriter
from json_repair import repair_json
from llm_api import call_api

def clean_json_response(raw_text):
    match = re.search(r'```(?:json)?(.*?)```', raw_text, re.DOTALL | re.IGNORECASE)
    extracted = match.group(1).strip() if match else raw_text.strip()

    try:
        return repair_json(extracted)
    except Exception as e:
        print(f"[Module: pdf_handler, Function: clean_json_response] json_repair failed, returning unrepaired text: {e}")
        return extracted

def get_text_with_pages(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        full_text = ""
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                full_text += f"[Page {i}]\n{text}\n"

        if not full_text.strip():
            raise SystemExit("Error: No text extracted. The PDF might be image-based.")

        return full_text
    except Exception as e:
        print(f"[Module: pdf_handler, Function: get_text_with_pages] Error: {e}")
        raise

def get_chapter_ranges(text):
    try:
        prompt = f"""
        Analyze this textbook text which contains [Page X] markers.
        Find the Table of Contents. Map the chapter page numbers to the physical [Page X] markers.
        Determine the physical start_page and end_page for each chapter.
        Return a JSON array of objects, each containing: "chapter_number", "title", "start_page" (integer), and "end_page" (integer).
        Ignore chapters such as "Preface".
        Text:
        {text}
        """
        raw_response = call_api(prompt, response_json=True)
        parsed = json.loads(clean_json_response(raw_response))

        if isinstance(parsed, dict):
            for key, value in parsed.items():
                if isinstance(value, list):
                    return value
            return [parsed]

        if not parsed:
            raise SystemExit("Error: AI returned an empty chapter list.")

        return parsed
    except Exception as e:
        print(f"[Module: pdf_handler, Function: get_chapter_ranges] Error: {e}")
        raise

def split_pdf_to_chapters(pdf_path, ranges, output_dir):
    try:
        reader = PdfReader(pdf_path)
        chapter_files = []

        for ch in ranges:
            writer = PdfWriter()
            start = ch.get("start_page", 0)
            end = ch.get("end_page", 0)

            start = max(0, min(start, len(reader.pages) - 1))
            end = max(0, min(end, len(reader.pages) - 1))

            if start > end:
                start, end = end, start

            for i in range(start, end + 1):
                writer.add_page(reader.pages[i])

            out_name = f"Chapter_{ch.get('chapter_number', 'X')}.pdf"
            out_path = os.path.join(output_dir, out_name)
            with open(out_path, "wb") as f:
                writer.write(f)

            ch["pdf_path"] = out_path
            chapter_files.append(ch)

        return chapter_files
    except Exception as e:
        print(f"[Module: pdf_handler, Function: split_pdf_to_chapters] Error: {e}")
        raise

def ingest_chapter(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        full_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
        return full_text
    except Exception as e:
        print(f"[Module: pdf_handler, Function: ingest_chapter] Error: {e}")
        raise