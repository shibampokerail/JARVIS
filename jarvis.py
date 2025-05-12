import os
import json
import re
from datetime import datetime
import PyPDF2
from google import genai
from google.genai import types
from BrowserController import (
    setup_browser_with_profile, search, extract_contact_info,
    collect_search_links, summarize_page, fill_form, click_element_by_text, scroll_up, scroll_down, human_type, click_search_result_link, login_truman, click_youtube_video, go_back, go_forward, navigate_to_url, close_tab
)
import keyboard
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import Chrome
from selenium.webdriver.support.ui import Select
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from GeminiAssignments import process_assignment
import time
import urllib
import requests
from jarvis_config import speak, function_declarations, remember_info, recall_info
from SpotifyAI import process_spotify_command
from Email import send_email
import speech_recognition as sr
from BlandCall import call
load_dotenv()
import logging

def load_knowledge_base(knowledgebase_file="knowledgebase.txt", contacts_file="contacts.json"):
    """
    Load content from knowledgebase.txt and contacts.json into a structured dictionary.

    Args:
        knowledgebase_file (str): Path to the knowledgebase text file (default: "knowledgebase.txt").
        contacts_file (str): Path to the contacts JSON file (default: "contacts.json").

    Returns:
        dict: A dictionary with:
            - status: "success" or "error"
            - message: Description of the result
            - data: Dictionary containing:
                - knowledgebase: List of non-comment lines from knowledgebase.txt
                - contacts: List of contact dictionaries from contacts.json
    """
    result = {
        "status": "success",
        "message": "Successfully loaded knowledge base and contacts",
        "data": {
            "knowledgebase": [],
            "contacts": []
        }
    }

    try:
        if os.path.exists(knowledgebase_file):
            with open(knowledgebase_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            knowledgebase_content = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
            result["data"]["knowledgebase"] = knowledgebase_content
            logging.info(f"Loaded {len(knowledgebase_content)} entries from {knowledgebase_file}")
        else:
            logging.warning(f"Knowledgebase file {knowledgebase_file} does not exist")
            result["message"] = f"Warning: {knowledgebase_file} not found, returning empty knowledgebase"

        if os.path.exists(contacts_file):
            with open(contacts_file, "r", encoding="utf-8") as f:
                contacts = json.load(f)
            if isinstance(contacts, list):
                result["data"]["contacts"] = contacts
                logging.info(f"Loaded {len(contacts)} contacts from {contacts_file}")
            else:
                logging.error(f"Invalid format in {contacts_file}: expected a JSON array")
                result["status"] = "error"
                result["message"] = f"Invalid format in {contacts_file}: expected a JSON array"
                return result
        else:
            logging.warning(f"Contacts file {contacts_file} does not exist")
            if "not found" in result["message"]:
                result["message"] = "Warning: Both knowledgebase.txt and contacts.json not found"
            else:
                result["message"] = f"Warning: {contacts_file} not found, returning empty contacts"

        return result

    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse {contacts_file}: {str(e)}")
        result["status"] = "error"
        result["message"] = f"Failed to parse {contacts_file}: {str(e)}"
        return result
    except Exception as e:
        logging.error(f"Failed to load knowledge base: {str(e)}")
        result["status"] = "error"
        result["message"] = f"Failed to load knowledge base: {str(e)}"
        return result
def speech_input(prompt=""):
    if prompt:
        speak(prompt)
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        audio = recognizer.listen(source)
    try:
        return recognizer.recognize_google(audio).lower().strip()
    except sr.UnknownValueError:
        speak("Sorry, I didn't catch that.")
        return speech_input(prompt)  # Retry on failure
    except sr.RequestError:
        speak("Sorry, speech service is unavailable.")
        return ""

def search_contact_info(organization: str) -> dict:
    """
    Search for an organization's contact info by collecting web pages and using Gemini to extract phone numbers and emails.
    """
    driver = setup_browser_with_profile(headless=False)
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    error_occurred = False
    try:
        search_query = f"{organization} contact information"
        search(driver, search_query)

        links = collect_search_links(driver, max_links=1)
        if not links or not links[0]["url"]:
            raise Exception("No valid search result links found")

        page_contents = []
        for link in links:
            if link["url"]:
                content = summarize_page(driver, link["url"])
                page_contents.append({
                    "title": link["title"],
                    "url": link["url"],
                    "content": content
                })

        prompt = (
            f"Extract contact information (phone numbers, email addresses) for {organization} from the following web page contents. "
            "Return only the contact information in a clear, concise format (e.g., 'Phone: (123) 456-7890, Email: contact@org.com'). "
            "If no contact info is found, say 'No contact information found.'\n\n"
        )
        for idx, page in enumerate(page_contents, 1):
            prompt += f"Page {idx}: {page['title']} ({page['url']})\nContent: {page['content']}\n\n"

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])]
        )
        contact_info = response.text.strip()

        return {"contact_info": contact_info}
    except Exception as e:
        print(f"Error in search_contact_info: {e}")
        error_occurred = True
        return {"contact_info": f"Error: {str(e)}"}
    finally:
        if not error_occurred:
            driver.quit()
        else:
            print("Browser left open for debugging. Close manually or press Enter to quit.")
            input()
            driver.quit()

def research_topic(topic: str, max_links: int = 6) -> dict:
    """
    Research a topic by collecting and summarizing links from Bing search.
    """
    driver = setup_browser_with_profile(headless=False)
    error_occurred = False
    try:
        search(driver, topic)
        links = collect_search_links(driver, max_links)
        summaries = []
        for link in links:
            if link["url"]:
                summary = summarize_page(driver, link["url"])
                summaries.append({
                    "title": link["title"],
                    "url": link["url"],
                    "summary": summary
                })
        return {"summaries": summaries}
    except Exception as e:
        print(f"Error in research_topic: {e}")
        error_occurred = True
        return {"summaries": [{"title": "Error", "url": "", "summary": str(e)}]}
    finally:
        if not error_occurred:
            driver.quit()
        else:
            print("Browser left open for debugging. Close manually or press Enter to quit.")
            input()
            driver.quit()

def parse_due_date(due_date_str):
    """Parse due date string into a datetime object for comparison."""
    try:
        return datetime.strptime(due_date_str, "%B %d, %Y")
    except ValueError:
        return None

def wait_for_download(download_dir, timeout=30):
    """Wait for a file to be downloaded into the specified directory."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        files = os.listdir(download_dir)
        if any(not f.endswith(".crdownload") for f in files):  # Check for completed downloads
            return [f for f in files if not f.endswith(".crdownload")]
        time.sleep(1)
    raise Exception("Download did not complete within timeout")

def read_file(file_path):
    """Read the contents of a file (PDF or text)."""
    if file_path.endswith(".pdf"):
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

def do_homework(subject: str) -> dict:
    """
    Access Truman University's Brightspace portal, log in, navigate to the assignments page,
    extract "Not Submitted" assignments, identify the desired assignment through conversation,
    extract homework instructions, download files, and get a response from a simulated Gemini.
    """
    driver = setup_browser_with_profile(headless=False)
    error_occurred = False
    try:
        # Enable network tracking via Chrome DevTools Protocol
        driver.execute_cdp_cmd('Network.enable', {})

        # List to store network responses
        course_data = []

        # Callback to process network responses for course data
        def process_network_log(log_entry):
            message = json.loads(log_entry['message'])['message']
            if message['method'] == 'Network.responseReceived' and 'response' in message['params']:
                url = message['params']['response']['url']
                # Match URLs like "12345?localeId=1"
                match = re.match(r'.*/(\d{5})\?localeId=1$', url)
                if match:
                    course_id = match.group(1)
                    # Get the response body
                    request_id = message['params']['requestId']
                    try:
                        response = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                        if response['base64Encoded']:
                            import base64
                            body = base64.b64decode(response['body']).decode('utf-8')
                        else:
                            body = response['body']
                        # Parse JSON response
                        data = json.loads(body)
                        course_name = data.get('properties', {}).get('name', '').strip()
                        if course_name:
                            course_data.append({'course_id': course_id, 'name': course_name})
                            print(f"Found course: {course_name} (ID: {course_id})")
                    except Exception as e:
                        print(f"Error processing response for {url}: {e}")

        driver.get("https://learn.truman.edu")
        print("Navigated to learn.truman.edu")

        if driver.current_url=="https://learn.truman.edu/d2l/login":

            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "/html/body/div/div[2]/div/div[2]/div/div[1]/div[1]/div[1]/button"))
            ).click()
            print("Clicked Truman Login button")
            login_truman(driver, 30)

        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.TAG_NAME, "d2l-my-courses"))
        )
        print("Found d2l-my-courses element")

        page_source = driver.page_source
        print("Page source after finding d2l-my-courses:")
        print(page_source[:1000] + "..." if len(page_source) > 1000 else page_source)

        print("Waiting for network responses...")
        start_time = time.time()
        while time.time() - start_time < 30:
            logs = driver.get_log('performance')
            for log in logs:
                process_network_log(log)
            if len(course_data) >= 2:
                break
            time.sleep(1)

        print("Captured courses:")
        for course in course_data:
            print(f"- {course['name']} (ID: {course['course_id']})")

        course_id = None
        course_name = None
        for course in course_data:
            if subject.lower() in course['name'].lower():
                course_id = course['course_id']
                course_name = course['name']
                break

        if not course_id:
            raise Exception(f"No course found matching '{subject}'")

        print(f"Found course: {course_name} (ID: {course_id})")

        assignments_url = f"https://learn.truman.edu/d2l/lms/dropbox/user/folders_list.d2l?ou={course_id}&isprv=0"
        driver.get(assignments_url)
        print(f"Navigated to assignments page: {assignments_url}")

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, '//select[@title="Results Per Page"]'))
        )
        print("Dropdown loaded")

        dropdown = Select(driver.find_element(By.XPATH, '//select[@title="Results Per Page"]'))
        dropdown.select_by_value("200")
        print("Selected 200 per page")

        time.sleep(2)

        assignments_html = None
        print("Waiting for folders_list.d2l network response...")
        start_time = time.time()
        while time.time() - start_time < 30:
            logs = driver.get_log('performance')
            for log in logs:
                message = json.loads(log['message'])['message']
                if message['method'] == 'Network.responseReceived' and 'response' in message['params']:
                    url = message['params']['response']['url']
                    if f"folders_list.d2l?ou={course_id}&isprv=0" in url:
                        request_id = message['params']['requestId']
                        try:
                            response = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                            if response['base64Encoded']:
                                import base64
                                assignments_html = base64.b64decode(response['body']).decode('utf-8')
                            else:
                                assignments_html = response['body']
                            print("Captured folders_list.d2l response")
                            break
                        except Exception as e:
                            print(f"Error capturing folders_list.d2l response: {e}")
            if assignments_html:
                break
            time.sleep(1)

        if not assignments_html:
            raise Exception("Failed to capture folders_list.d2l network response")

        soup = BeautifulSoup(assignments_html, 'html.parser')
        table = soup.find('table', id='z_b')
        if not table:
            raise Exception("Assignments table not found in folders_list.d2l response")

        assignments = []
        rows = table.find_all('tr')
        for row in rows:
            if row.find('th', class_='d_hch') or row.find('td', colspan='4'):
                continue

            try:
                title_elem = row.find('a', class_='d2l-link')
                title = title_elem.find('strong').text.strip() if title_elem and title_elem.find('strong') else "Unknown"

                link = title_elem['href'] if title_elem and 'href' in title_elem.attrs else ""

                due_date_elem = row.find('div', class_='d2l-dates-text')
                due_date = due_date_elem.find('strong').text.strip() if due_date_elem and due_date_elem.find('strong') else "Not specified"

                status_elem = row.find('td', class_='d_gt').find('a', class_='d2l-link')
                submission_status = status_elem.text.strip() if status_elem else "Unknown"

                if submission_status.lower() != "not submitted":
                    continue

                assignments.append({
                    "title": title,
                    "due_date": due_date,
                    "submission_status": submission_status,
                    "link": f"https://learn.truman.edu{link}" if link else ""
                })
            except Exception as e:
                print(f"Error parsing row: {e}")
                continue

        if not assignments:
            raise Exception("No 'Not Submitted' assignments found for this course")

        print("Not Submitted Assignments:")
        print(json.dumps(assignments, indent=2))

        assignments_sorted = sorted(
            assignments,
            key=lambda x: parse_due_date(x['due_date']) or datetime.max
        )

        speak("\nAlright sir, Let's find the assignment that you want me to work on.")
        selected_assignment = None
        remaining_assignments = assignments_sorted.copy()

        while remaining_assignments and not selected_assignment:
            if len(remaining_assignments) == 1:
                selected_assignment = remaining_assignments[0]
                speak(f"I've found the most recent assignment, {selected_assignment['title']}")
                break

            current_assignment = remaining_assignments[0]
            speak(f"\nI am currently looking at {current_assignment['title']}")
            speak(f"This assignment is {current_assignment['due_date']}.")

            user_input = speech_input("Is this the assignment that you want me to work on, sir?")

            if user_input == "yes":
                selected_assignment = current_assignment
                break
            elif user_input == "cancel":
                speak("Cancelling homework selection.")
                return {"result": "Homework selection cancelled by user"}
            else:
                keyword = speech_input("Please tell me a specific keyword in your assignment's title:")

                if keyword == "cancel":
                    speak("Cancelling homework selection.")
                    return {"result": "Homework selection cancelled by user"}

                matching_assignments = [
                    assignment for assignment in assignments_sorted
                    if keyword in assignment['title'].lower()
                ]
                speak(f"Found {len(matching_assignments)} assignment(s) with keyword '{keyword}'")

                if matching_assignments:
                    if len(matching_assignments) == 1:
                        selected_assignment = matching_assignments[0]
                        speak(f"I've identified the assignment: {selected_assignment['title']}")
                        break
                    remaining_assignments = matching_assignments
                else:
                    print("No assignments found with that keyword. Continuing with next assignment.")
                    remaining_assignments.pop(0)
                    if not remaining_assignments:
                        print("No more assignments to check. Starting over.")
                        remaining_assignments = assignments_sorted.copy()

        if not selected_assignment:
            speak("sorry sir, I couldn't find the assignment that you wanted me to work on.")
            raise Exception("Failed to identify an assignment to work on")

        assignment_link = selected_assignment['link']
        print(f"Navigating to assignment: {selected_assignment['title']} at {assignment_link}")
        driver.get(assignment_link)

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "d2l-html-block"))
        )
        print("Assignment page loaded")

        html_block = driver.find_element(By.TAG_NAME, "d2l-html-block")
        instructions = html_block.get_attribute("html")
        print("Homework Instructions:")
        print(instructions)

        soup = BeautifulSoup(instructions, 'html.parser')
        links = soup.find_all('a', href=True)
        download_dir = os.path.join(os.getcwd(), "downloads")
        os.makedirs(download_dir, exist_ok=True)
        downloaded_files = []

        original_window = driver.current_window_handle

        for link in links:
            href = link['href']
            href = urllib.parse.unquote(href)
            if not href.startswith('http'):
                href = f"https://learn.truman.edu{href}"
            file_name = link.text.strip() or href.split('/')[-1]
            file_ext = os.path.splitext(file_name)[1].lower()

            if file_ext not in ['.pdf', '.xlsx', '.xls']:
                print(f"Skipping non-PDF/Excel link: {href}")
                continue

            print(f"Attempting to download file from instructions: {file_name}")

            try:
                driver.execute_cdp_cmd('Page.setDownloadBehavior', {
                    'behavior': 'allow',
                    'downloadPath': download_dir
                })

                if file_ext == '.pdf':
                    driver.execute_script(f"window.open('{href}', '_blank');")
                    WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
                    driver.switch_to.window(driver.window_handles[-1])

                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )

                    js_script = """
                        var link = document.createElement('a');
                        link.href = window.location.href;
                        link.download = arguments[0];
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                    """
                    driver.execute_script(js_script, file_name)

                    downloaded = wait_for_download(download_dir, timeout=30)
                    if not downloaded:
                        print(f"No file downloaded for {file_name}")
                        driver.close()
                        driver.switch_to.window(original_window)
                        continue

                    downloaded_file = os.path.join(download_dir, downloaded[0])
                    downloaded_files.append((downloaded_file, file_name))

                    driver.close()
                    driver.switch_to.window(original_window)

                else:
                    driver.get(href)

                    downloaded = wait_for_download(download_dir, timeout=30)
                    if not downloaded:
                        print(f"No file downloaded for {file_name}")
                        continue

                    downloaded_file = os.path.join(download_dir, downloaded[0])
                    downloaded_files.append((downloaded_file, file_name))

                time.sleep(1)

            except Exception as e:
                print(f"Error downloading {file_name}: {e}")
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(original_window)
                continue

        final_downloaded_files = []
        for downloaded_file, intended_name in downloaded_files:
            try:
                new_file_path = os.path.join(download_dir, intended_name)
                os.rename(downloaded_file, new_file_path)
                print(f"Renamed: {downloaded_file} to {new_file_path}")
                final_downloaded_files.append(new_file_path)
            except Exception as e:
                print(f"Error renaming {downloaded_file} to {intended_name}: {e}")
                continue

        downloaded_files = final_downloaded_files

        # Clear any remaining .crdownload files
        for f in os.listdir(download_dir):
            if f.endswith('.crdownload'):
                try:
                    os.remove(os.path.join(download_dir, f))
                    print(f"Cleaned up: {f}")
                except Exception as e:
                    print(f"Error cleaning up {f}: {e}")

        # Reset download behavior to default
        driver.execute_cdp_cmd('Page.setDownloadBehavior', {
            'behavior': 'deny'
        })

        # Check for downloadable files in the table
        table_files = []
        try:
            tbody = driver.find_element(By.XPATH, '//*[@id="z_k"]/tbody')
            rows = tbody.find_elements(By.TAG_NAME, "tr")
            print(f"Found {len(rows)} downloadable links in table")

            original_window = driver.current_window_handle

            for idx, row in enumerate(rows):
                try:
                    link = row.find_element(By.XPATH, ".//td[1]/span/a")
                    file_name = link.text.strip() or f"file_{idx}"
                    href = link.get_attribute("href")
                    print(f"Downloading file from table: {file_name} (URL: {href})")

                    file_ext = '.pdf' if 'pdf' in href.lower() else '.xlsx' if 'xlsx' in href.lower() or 'xls' in href.lower() else '.dat'

                    # Set download behavior
                    driver.execute_cdp_cmd('Page.setDownloadBehavior', {
                        'behavior': 'allow',
                        'downloadPath': download_dir
                    })

                    if file_ext == '.pdf':
                        driver.execute_script(f"window.open('{href}', '_blank');")
                        WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
                        driver.switch_to.window(driver.window_handles[-1])

                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.TAG_NAME, "body"))
                        )

                        js_script = """
                            var link = document.createElement('a');
                            link.href = window.location.href;
                            link.download = arguments[0];
                            document.body.appendChild(link);
                            link.click();
                            document.body.removeChild(link);
                        """
                        driver.execute_script(js_script, file_name + file_ext)

                        downloaded = wait_for_download(download_dir, timeout=30)
                        if not downloaded:
                            print(f"No file downloaded for {file_name}")
                            driver.close()
                            driver.switch_to.window(original_window)
                            continue

                        downloaded_file = os.path.join(download_dir, downloaded[0])
                        new_file_path = os.path.join(download_dir, file_name + file_ext)
                        os.rename(downloaded_file, new_file_path)
                        print(f"Downloaded and renamed: {new_file_path}")
                        table_files.append(new_file_path)

                        driver.close()
                        driver.switch_to.window(original_window)

                    else:
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", link)
                        WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, f'//*[@id="z_k"]/tbody/tr[{idx + 1}]/td[1]/span/a'))
                        )
                        try:
                            link.click()
                        except Exception as e:
                            print(f"Normal click failed: {e}. Attempting JavaScript click.")
                            driver.execute_script("arguments[0].click();", link)

                        downloaded = wait_for_download(download_dir, timeout=30)
                        if not downloaded:
                            print(f"No file downloaded for {file_name}")
                            continue

                        downloaded_file = os.path.join(download_dir, downloaded[0])
                        new_file_path = os.path.join(download_dir, file_name + file_ext)
                        os.rename(downloaded_file, new_file_path)
                        print(f"Downloaded and renamed: {new_file_path}")
                        table_files.append(new_file_path)

                    time.sleep(1)

                except Exception as e:
                    print(f"Error downloading file at row {idx}: {e}")
                    if len(driver.window_handles) > 1:
                        driver.close()
                        driver.switch_to.window(original_window)
                    continue

        except Exception as e:
            print(f"No downloadable files found in table: {e}")

        downloaded_files.extend(table_files)

        gemini_prompt = "Homework Instructions:\n" + instructions + "\n\n"
        if downloaded_files:
            gemini_prompt += "Downloaded Files:\n" + "\n".join(downloaded_files) + "\n\n"

        speak("\nAlright Sir, I am working on your assignment as we speak....")
        gemini_response = process_assignment("downloads", "completed_assignments", gemini_prompt)
        print("Gemini Response:")
        is_completed_voice = False
        speak("\nI have completed the assignment sir. You can view it in the completed assignments folder.")

        print(gemini_response)

        if not downloaded_files:
            print("No downloadable files found. Generating PDF from instructions.")
            output_dir = os.path.join(os.getcwd(), "completed_assignments", "generated_files")
            os.makedirs(output_dir, exist_ok=True)
            pdf_path = os.path.join(output_dir, f"{selected_assignment['title']}_submission.pdf")

            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas

            c = canvas.Canvas(pdf_path, pagesize=letter)
            c.drawString(100, 750, selected_assignment['title'])
            y = 730
            for line in gemini_response.get('full_solution', instructions).split('\n'):
                if y < 50:
                    c.showPage()
                    y = 750
                c.drawString(100, y, line[:80])
                y -= 20
            c.save()
            print(f"Generated PDF: {pdf_path}")
            speak("\nI have completed the assignment sir. You can view it in the completed assignments folder.")
            gemini_response['generated_files'] = gemini_response.get('generated_files', []) + [pdf_path]

        return {
            "result": f"Successfully processed the {selected_assignment['title']} assignment",
            "gemini_response": gemini_response
        }
    except Exception as e:
        print(f"Error in do_homework: {e}")
        error_occurred = True
        return {"result": f"Error: {str(e)}"}
    finally:
        if not error_occurred:
            pass
        else:
            print("Browser left open for debugging. Close manually or press Enter to quit.")
            input()
            pass

def main():
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    tools = types.Tool(function_declarations=function_declarations)
    config = types.GenerateContentConfig(tools=[tools])

    driver = setup_browser_with_profile(headless=False)
    conversation_history = []
    last_function_call = None

    recognizer = sr.Recognizer()
    microphone = sr.Microphone()

    print("Adjusting for ambient noise... Please wait.")
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=5)
    print("Ready to listen. Hold spacebar and say your command (or 'quit' to exit).")

    success_phrases = [
        "Alright, sir",
        "Okay, sir",
        "Of Course, Sir"
    ]

    try:
        while True:
            if not keyboard.is_pressed('space'):
                print("Hold spacebar to give a command...")
                time.sleep(0.1)
                continue

            print("Listening...")
            try:
                with microphone as source:
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                try:
                    user_input = recognizer.recognize_google(audio).strip()
                    print(f"You said: {user_input}")
                except sr.UnknownValueError:
                    print("Sorry, sir, my ears are failing me! Could you repeat that?")
                    continue
                except sr.RequestError as e:
                    print(f"Oops, sir, the speech service gave me a headache: {e}")
                    continue
            except sr.WaitTimeoutError:
                print("No speech detected, sir. Speak up while holding spacebar!")
                continue

            if user_input.lower() == 'quit':
                speak("Farewell, sir! Shutting down JARVIS.")
                print("Exiting JARVIS.")
                break

            if not user_input:
                print("No command recognized, sir. Try again with some flair!")
                continue

            print(f"Debug: Conversation history length: {len(conversation_history)}")

            if last_function_call and last_function_call.name in ("click_youtube_video", "click_search_result_link"):
                last_response_content = None
                for content in reversed(conversation_history):
                    if content.parts and content.parts[0].function_response:
                        last_response_content = content
                        break
                if last_response_content:
                    try:
                        last_result = last_response_content.parts[0].function_response.response.get("result")
                        if isinstance(last_result, dict) and ("videos" in last_result or "links" in last_result):
                            try:
                                index = int(user_input) - 1
                                if last_function_call.name == "click_youtube_video" and 0 <= index < len(
                                        last_result["videos"]):
                                    result = navigate_to_url(driver, last_result["videos"][index]["url"])
                                    print(f"Selected video {index + 1}: {last_result['videos'][index]['title']}")
                                    speak(random.choice(success_phrases))
                                    last_function_call = None
                                    conversation_history = [types.Content(
                                        role="model",
                                        parts=[
                                            types.Part(text=f"Clicked video: {last_result['videos'][index]['title']}")]
                                    )]
                                    continue
                                elif last_function_call.name == "click_search_result_link" and 0 <= index < len(
                                        last_result["links"]):
                                    result = navigate_to_url(driver, last_result["links"][index]["url"])
                                    print(f"Selected link {index + 1}: {last_result['links'][index]['title']}")
                                    speak(random.choice(success_phrases))
                                    last_function_call = None
                                    conversation_history = [types.Content(
                                        role="model",
                                        parts=[types.Part(text=f"Clicked link: {last_result['links'][index]['title']}")]
                                    )]
                                    continue
                                else:
                                    print("Invalid number, sir. Pick a valid one, pretty please!")
                                    continue
                            except ValueError:
                                print("Say a number, sir, not poetry!")
                                continue
                    except AttributeError as e:
                        print(f"Debug: My circuits got tangled accessing that response: {e}")
                        last_function_call = None
                        continue
                else:
                    print("Debug: No valid function response in history, sir. Let’s start fresh!")
                    last_function_call = None

            knowledge_base_content = load_knowledge_base()
            context_prompt = f"Context from knowledge base: {knowledge_base_content}\n\nUse the above context to inform your response."
            context_content = types.Content(role="user", parts=[types.Part(text=context_prompt)])

            conversation_history.append(types.Content(role="user", parts=[types.Part(text=user_input)]))
            conversation_history = [context_content] + conversation_history[-5:]  # Include context in every prompt

            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=conversation_history,
                    config=config
                )
                print("Debug: Gemini response parts:", [part.__dict__ for part in response.candidates[0].content.parts])
            except Exception as e:
                print(f"Ouch, sir, Gemini gave me a digital bruise: {e}")
                conversation_history = [types.Content(role="model", parts=[types.Part(text=f"Error: {e}")])]
                continue

            function_call = None
            if response.candidates and response.candidates[0].content.parts:
                part = response.candidates[0].content.parts[0]
                if part.function_call:
                    function_call = part.function_call
                elif part.text and part.text.startswith("```tool_outputs"):
                    try:
                        tool_output = json.loads(part.text.split("```tool_outputs\n")[1].split("\n```")[0])
                        for key, value in tool_output.items():
                            function_name = key.replace("_response", "")
                            args = value if isinstance(value, dict) else {}
                            function_call = types.FunctionCall(name=function_name, args=args)
                            print(f"Debug: Parsed tool_outputs - Function: {function_name}, Args: {args}")
                            break
                    except Exception as e:
                        print(f"Debug: Sir, I fumbled parsing those tool outputs: {e}")
                        conversation_history = [
                            types.Content(role="model", parts=[types.Part(text=f"Error parsing response: {e}")])]
                        continue

            if function_call:
                last_function_call = function_call
                function_name = function_call.name
                args = function_call.args
                print(f"Debug: Function call - Name: {function_name}, Args: {args}")
            else:
                print("No function call suggested, sir. Here’s the direct response:")
                print(response.text or "No response text available.")
                conversation_history = [types.Content(role="model", parts=[
                    types.Part(text=response.text or "No response text available.")])]
                last_function_call = None
                continue

            result = None
            try:
                if function_name == "search_contact_info":
                    result = search_contact_info(**args)
                    speak(random.choice(success_phrases))
                elif function_name == "research_topic":
                    result = research_topic(**args)
                    speak(result)
                elif function_name == "do_homework":
                    result = do_homework(**args)
                    speak(random.choice(success_phrases))
                elif function_name == "click_element":
                    print(f"Debug: Executing click_element with args: {args}")
                    result = click_element_by_text(driver, **args)
                    print(f"Debug: click_element result: {result}")
                    speak(random.choice(success_phrases))
                elif function_name == "search_web":
                    result = search(driver, **args)
                    speak(random.choice(success_phrases))
                elif function_name == "click_youtube_video":
                    print(f"Debug: Executing click_youtube_video with args: {args}")
                    result = click_youtube_video(driver, **args)
                    print(f"Debug: click_youtube_video result: {result}")
                    if isinstance(result, dict) and "videos" in result:
                        print(result["message"])
                        for i, video in enumerate(result["videos"], 1):
                            print(f"{i}. {video['title']} ({video['url']})")
                        conversation_history = [types.Content(
                            role="model",
                            parts=[types.Part(text="Please say the number of the video you want to select.")]
                        ), types.Content(
                            role="user",
                            parts=[types.Part.from_function_response(name=function_name, response={"result": result})]
                        )]
                        continue
                    speak(random.choice(success_phrases))
                elif function_name == "go_back":
                    result = go_back(driver)
                    speak(random.choice(success_phrases))
                elif function_name == "navigate_to_url":
                    result = navigate_to_url(driver, **args)
                    speak(random.choice(success_phrases))
                elif function_name == "close_tab":
                    result = close_tab(driver)
                    speak(random.choice(success_phrases))
                elif function_name == "login_truman":
                    result = login_truman(driver, **args)
                    speak(random.choice(success_phrases))
                elif function_name == "remember_info":
                    result = remember_info(**args)
                    speak(random.choice(success_phrases))
                elif function_name == "recall_info":
                    result = recall_info(**args)
                    speak(random.choice(success_phrases))
                elif function_name == "send_email":
                    result = send_email(**args)
                    speak(random.choice(success_phrases))
                elif function_name == "call":
                    result = call(**args)
                    speak(random.choice(success_phrases))
                elif function_name == "process_spotify_command":
                    result = process_spotify_command(**args)
                    speak(random.choice(success_phrases))
                elif function_name == "click_search_result_link":
                    print(f"Debug: Executing click_search_result_link with args: {args}")
                    result = click_search_result_link(driver, **args)
                    print(f"Debug: click_search_result_link result: {result}")
                    if isinstance(result, dict) and "links" in result:
                        print(result["message"])
                        for i, link in enumerate(result["links"], 1):
                            print(f"{i}. {link['title']} ({link['url']})")
                        conversation_history = [types.Content(
                            role="model",
                            parts=[types.Part(text="Please say the number of the link you want to select.")]
                        ), types.Content(
                            role="user",
                            parts=[types.Part.from_function_response(name=function_name, response={"result": result})]
                        )]
                        continue
                    speak(random.choice(success_phrases))
                else:
                    print(f"Unknown function: {function_name}, sir. Did I miss a memo?")
                    continue
            except Exception as e:
                print(f"Error executing function {function_name}: {e}")
                speak(f"Oops, sir, I got an error! You built me, so maybe it’s a feature, not a bug?")
                conversation_history = [types.Content(role="model", parts=[types.Part(text=f"Error: {e}")])]
                continue

            try:
                function_response_part = types.Part.from_function_response(
                    name=function_name,
                    response={"result": result}
                )
                conversation_history = [types.Content(
                    role="model",
                    parts=[types.Part(function_call=last_function_call)]
                ), types.Content(
                    role="user",
                    parts=[function_response_part]
                ), types.Content(
                    role="model",
                    parts=[types.Part(text=result if isinstance(result, str) else "Function executed.")]
                )]
                final_response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    config=config,
                    contents=conversation_history
                )
                print(final_response.text)
            except Exception as e:
                print(f"Sir, I tripped over the function response: {e}")
                conversation_history = [types.Content(role="model", parts=[types.Part(text=f"Error: {e}")])]
                continue
    except KeyboardInterrupt:
        print("\nInterrupted by user, sir. JARVIS is signing off!")
        speak("Catch you later, sir!")
    except Exception as e:
        print(f"Critical error, sir, I’m having an identity crisis: {e}")
        speak("Help, sir, I’m malfunctioning! Time for a reboot!")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()