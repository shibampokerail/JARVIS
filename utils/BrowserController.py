from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, WebDriverException
import requests
import time
import random
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os

def setup_browser_with_profile(headless=False):
    download_dir = os.path.join(os.getcwd(), "../downloads")
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    capabilities = DesiredCapabilities.CHROME
    capabilities['goog:loggingPrefs'] = {'browser': 'ALL', 'performance': 'ALL'}

    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--incognito")

    service = Service("../drive/chromedriver-win64/chromedriver.exe")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    options.add_experimental_option("prefs", {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    })

    driver = Chrome(options=options, desired_capabilities=capabilities, service=service)
    return driver

def wait_until_loaded(driver, by, identifier, timeout=10):
    try:
        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, identifier)))
    except Exception as e:
        print(f"Error waiting for element {identifier}: {e}")
        return False
    return True

def human_type(element, text, min_delay=0.05, max_delay=0.15):
    """
    Types like a human by sending keys one character at a time with delay.
    """
    try:
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(min_delay, max_delay))
    except Exception as e:
        print(f"Error typing text '{text}': {e}")

def login_truman(driver, timeout=15):
    """
    Log in to Truman University's Brightspace portal using the provided WebDriver.

    Args:
        driver: Selenium WebDriver instance (already configured with profile and options).
        timeout (int): Maximum wait time (in seconds) for elements to appear.

    Returns:
        None: If login is successful, the driver is authenticated and on the dashboard.

    Raises:
        Exception: If login fails (e.g., missing credentials, timeout, or page load issues).
    """
    try:
        # Wait for the login page to load
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        print("Login page loaded")

        # Enter username and password
        username = os.getenv("BRIGHTSPACE_USERNAME")
        password = os.getenv("BRIGHTSPACE_PASSWORD")
        if not username or not password:
            raise Exception("BRIGHTSPACE_USERNAME or BRIGHTSPACE_PASSWORD not set in environment")

        username_field = driver.find_element(By.ID, "username")
        username_field.clear()  # Clear any pre-filled text
        human_type(username_field, username)
        print("Entered username")

        password_field = driver.find_element(By.ID, "password")
        password_field.clear()  # Clear any pre-filled text
        human_type(password_field, password)
        print("Entered password")

        # Find and click the login button
        login_button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, '//button[@type="submit"] | //input[@type="submit"] | //button[contains(text(), "Login")]'))
        )
        login_button.click()
        print("Clicked login button")


        return "Successfully Logged in"

    except Exception as e:
        return "Sorry, I can't login for some reason something went wrong. Is this a truman website?"

def search(driver, query, link="https://www.bing.com"):
    try:
        driver.get(link)
        print("Search page loading...")
        if not wait_until_loaded(driver, By.NAME, "q", timeout=10):
            return "Failed to load search page."
        print("Search box loaded.")
        search_box = driver.find_element(By.NAME, "q")
        human_type(search_box, query)
        search_box.send_keys(Keys.RETURN)
        if not wait_until_loaded(driver, By.TAG_NAME, "body", timeout=10):
            return "Failed to load search results."
        print("Search results loaded.")
        return "Search completed successfully."
    except Exception as e:
        print(f"Error performing search for '{query}': {e}")
        return f"Error performing search: {e}"

def click_search_result_link(driver, text, first_only=False):
    """
    Click a search result or news link containing the specified text.
    Args:
        driver: Selenium WebDriver instance.
        text: Text to search for in the link title (case-insensitive).
        first_only: If True, click the first matching link; if False, click first but allow listing all matches for debugging.
    Returns:
        String with success/error message.
    """
    try:
        print(f"Attempting to click search result link with text '{text}' (first_only={first_only})")
        # Wait for page to stabilize
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState === 'complete'")
        )
        time.sleep(2)  # Extra wait for dynamic content

        # Determine page type (standard search or news)
        current_url = driver.current_url
        is_news_page = "/news" in current_url.lower()
        print(f"Debug: Page type - {'News' if is_news_page else 'Standard Search'} (URL: {current_url})")

        # Collect links based on page type
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        links = []
        if is_news_page:
            # News page: Find <a> elements within news article containers
            news_elements = soup.select("div.news-card a, div.t_sdiv a, main a")
            print(f"Debug: Found {len(news_elements)} news elements.")
            for elem in news_elements:
                if 'href' in elem.attrs:
                    title = elem.text.strip()
                    if title:  # Only include links with non-empty text
                        url = urljoin(driver.current_url, elem['href'])
                        links.append({"title": title, "url": url})
        else:
            # Standard search: Find <li class="b_algo"> elements
            result_elements = soup.find_all('li', class_='b_algo')
            print(f"Debug: Found {len(result_elements)} search result elements.")
            for elem in result_elements:
                link = elem.find('a')
                if link and 'href' in link.attrs:
                    title = link.text.strip()
                    url = urljoin(driver.current_url, link['href'])
                    links.append({"title": title, "url": url})

        # Log all link titles for debugging
        print("Debug: Available link titles:")
        for link in links:
            print(f"  - {link['title']}")

        # Filter links by text
        matched_links = [
            link for link in links
            if text.lower() in link['title'].lower()
        ]
        for link in matched_links:
            print(f"Debug: Matched link - Title: '{link['title']}', URL: {link['url']}")

        if not matched_links:
            print(f"Debug: No links found containing '{text}'.")
            return f"No search result links found containing '{text}'."

        # Always select the first link, log others for debugging
        target_link = matched_links[0]
        print(f"Debug: Targeting first link - Title: '{target_link['title']}', URL: {target_link['url']}")
        if len(matched_links) > 1 and not first_only:
            print(f"Debug: Additional matched links (not clicked):")
            for link in matched_links[1:]:
                print(f"  - Title: '{link['title']}', URL: {link['url']}")

        try:
            original_window = driver.current_window_handle
            # Find the exact clickable element
            link_elements = driver.find_elements(By.XPATH, f"//a[@href='{target_link['url']}' or contains(@href, '{target_link['url'].split('?')[0]}')]")
            if not link_elements:
                print("Debug: No clickable elements found for the target URL.")
                return f"Error: No clickable element found for link '{target_link['title']}'."

            link_elem = link_elements[0]
            print(f"Debug: Found clickable element for URL: {target_link['url']}")
            # Remove target="_blank" and scroll
            driver.execute_script("arguments[0].removeAttribute('target');", link_elem)
            driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", link_elem)
            time.sleep(0.5)  # Brief pause for scrolling

            # Attempt click with retry
            for attempt in range(2):
                try:
                    WebDriverWait(driver, 15).until(EC.element_to_be_clickable(link_elem))
                    link_elem.click()
                    print(f"Debug: Clicked link: '{target_link['title']}'")
                    time.sleep(2)
                    # Handle new tabs
                    if len(driver.window_handles) > 1:
                        for handle in driver.window_handles:
                            if handle != original_window:
                                driver.switch_to.window(handle)
                                driver.close()
                        driver.switch_to.window(original_window)
                        print("Debug: Closed new tab and switched back to original.")
                    print(f"Debug: Current URL after click: {driver.current_url}")
                    return f"Clicked search result link: '{target_link['title']}'"
                except Exception as click_error:
                    print(f"Debug: Click failed on attempt {attempt + 1}: {click_error}")
                    if attempt == 1:
                        # Try JavaScript click
                        try:
                            driver.execute_script("arguments[0].click();", link_elem)
                            print(f"Debug: JavaScript click succeeded for: '{target_link['title']}'")
                            time.sleep(2)
                            if len(driver.window_handles) > 1:
                                for handle in driver.window_handles:
                                    if handle != original_window:
                                        driver.switch_to.window(handle)
                                        driver.close()
                                driver.switch_to.window(original_window)
                                print("Debug: Closed new tab and switched back to original.")
                            print(f"Debug: Current URL after click: {driver.current_url}")
                            return f"Clicked search result link: '{target_link['title']}'"
                        except Exception as js_error:
                            print(f"Debug: JavaScript click failed: {js_error}")
                            return f"Error clicking search result link '{target_link['title']}': {js_error}"
        except Exception as e:
            print(f"Debug: Error clicking link '{target_link['title']}': {e}")
            return f"Error clicking search result link '{target_link['title']}': {e}"

    except Exception as e:
        print(f"Debug: General error in click_search_result_link: {e}")
        return f"Error clicking search result link: {e}"

def normalize_text(text):
    """Normalize text by removing spaces and converting to lowercase."""
    return re.sub(r'\s+', '', text).lower()

def click_element_by_text(driver, text, partial=True):
    """
    Click an element (link, button, or clickable element) containing the specified text or attribute, including child elements or spans.
    Matches both original text (e.g., 'Degree Works') and space-removed text (e.g., 'DegreeWorks') using XPath 1.0.
    Prioritizes <a> elements with valid href, then <button> or onclick elements. If clicking fails, navigates to the href URL.
    Args:
        driver: Selenium WebDriver instance.
        text: Text to search for in the element, its children, or its attributes.
        partial: If True, match partial text case-insensitively; if False, match exact text.
    Returns:
        String with success/error message.
    """
    original_text = text
    text = text.replace("'", "\\'")
    normalized_text = normalize_text(original_text)

    # XPaths for original text
    if partial:
        direct_xpath_original = (
            f"//*[self::a or self::button or self::span or self::div or @onclick or contains(@class, 'ng-')]"
            f"[contains(translate(string(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{original_text.lower()}') "
            f"or contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{original_text.lower()}') "
            f"or contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{original_text.lower()}')]"
        )
        span_xpath_original = (
            f"//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{original_text.lower()}')]"
        )
    else:
        direct_xpath_original = (
            f"//*[self::a or self::button or self::span or self::div or @onclick or contains(@class, 'ng-')]"
            f"[string(.)='{original_text}' or @aria-label='{original_text}' or @title='{original_text}']"
        )
        span_xpath_original = f"//span[text()='{original_text}']"

    # XPaths for space-removed text
    if partial:
        direct_xpath_normalized = (
            f"//*[self::a or self::button or self::span or self::div or @onclick or contains(@class, 'ng-')]"
            f"[contains(translate(string(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{normalized_text}') "
            f"or contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{normalized_text}') "
            f"or contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{normalized_text}')]"
        )
        span_xpath_normalized = (
            f"//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{normalized_text}')]"
        )
    else:
        direct_xpath_normalized = (
            f"//*[self::a or self::button or self::span or self::div or @onclick or contains(@class, 'ng-')]"
            f"[string(.)='{normalized_text}' or @aria-label='{normalized_text}' or @title='{normalized_text}']"
        )
        span_xpath_normalized = f"//span[text()='{normalized_text}']"

    try:
        print(
            f"Debug: Searching for element with text: '{original_text}' (normalized: '{normalized_text}', partial={partial})")
        print(f"Debug: Direct XPath (original): {direct_xpath_original}")
        print(f"Debug: Span XPath (original): {span_xpath_original}")
        print(f"Debug: Direct XPath (normalized): {direct_xpath_normalized}")
        print(f"Debug: Span XPath (normalized): {span_xpath_normalized}")

        # Wait for page to stabilize, including Angular
        try:
            WebDriverWait(driver,2).until(
                lambda d: d.execute_script(
                    "return document.readyState === 'complete' && (!window.angular || window.angular.element(document.body).injector()?.get('$rootScope').$$phase == null)")
            )
            WebDriverWait(driver, 2).until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "[ng-version], ngx-simplebar, tool-menu-item, favorites-menu, main-menu")))
        except:
            print("Debug: Angular or custom element wait timed out, proceeding...")
        time.sleep(1)  # Increased for dynamic frameworks

        # Scroll scrollable containers with retry
        for _ in range(3):
            try:
                driver.execute_script(
                    "let els = document.querySelectorAll('ngx-simplebar, [class*=\"scroll\"], [style*=\"overflow\"], div[style*=\"height\"], nav, main-menu, favorites-menu'); for (let el of els) { el.scrollTop = 0; el.scrollIntoView({block: 'center'}); }")
                time.sleep(1)
                print("Debug: Scrolled scrollable containers.")
                break
            except:
                print("Debug: Scroll attempt failed, retrying...")
                time.sleep(1)
        else:
            print("Debug: No scrollable containers found or scroll failed.")

        # Find elements
        elements = []
        # Direct elements (original text)
        try:
            elements.extend(driver.find_elements(By.XPATH, direct_xpath_original))
        except Exception as e:
            print(f"Debug: Error with direct XPath (original): {e}")
        # Direct elements (normalized text)
        try:
            elements.extend([e for e in driver.find_elements(By.XPATH, direct_xpath_normalized) if e not in elements])
        except Exception as e:
            print(f"Debug: Error with direct XPath (normalized): {e}")

        # Span elements and their clickable parents, including shadow DOM
        span_elements = []
        try:
            # Search all elements for shadow DOM
            all_elements = driver.find_elements(By.CSS_SELECTOR, "*")
            shadow_roots_found = 0
            for host in all_elements:
                try:
                    shadow_root = driver.execute_script("return arguments[0].shadowRoot", host)
                    if shadow_root:
                        shadow_roots_found += 1
                        print(
                            f"Debug: Found shadow DOM in element: {host.tag_name}, classes: {host.get_attribute('class') or 'none'}")
                        for xpath in [span_xpath_original, span_xpath_normalized]:
                            shadow_spans = shadow_root.find_elements(By.XPATH, xpath)
                            for span in shadow_spans:
                                try:
                                    parent = span.find_element(By.XPATH,
                                                               "./ancestor::*[self::a or self::button or @onclick][1]")
                                    elements.append(parent)
                                    span_elements.append(span)
                                except:
                                    continue
                except:
                    continue
            print(f"Debug: Total shadow DOM roots found: {shadow_roots_found}")
        except Exception as e:
            print(f"Debug: Shadow DOM search failed: {e}")

        # Standard span search
        for xpath in [span_xpath_original, span_xpath_normalized]:
            try:
                spans = driver.find_elements(By.XPATH, xpath)
                span_elements.extend(spans)
                for span in spans:
                    try:
                        parent = span.find_element(By.XPATH, "./ancestor::*[self::a or self::button or @onclick][1]")
                        if parent not in elements:
                            elements.append(parent)
                    except:
                        continue
            except Exception as e:
                print(f"Debug: Error with span XPath ({xpath}): {e}")

        if not elements:
            print(f"Debug: No elements found matching '{original_text}' or '{normalized_text}'.")
            return f"No elements found with text '{original_text}'."

        print(f"Debug: Found {len(elements)} matching elements (including spans with clickable parents).")
        # Prioritize elements: <a> with href, <button> or onclick, then others
        prioritized_elements = []
        for i, elem in enumerate(elements):
            raw_text = elem.get_attribute("textContent") or ""
            visible_text = elem.text.strip() or elem.get_attribute("aria-label") or elem.get_attribute(
                "title") or f"Element {i}"
            normalized_elem_text = normalize_text(raw_text)
            is_displayed = elem.is_displayed()
            is_enabled = elem.is_enabled()
            tag_name = elem.tag_name
            classes = elem.get_attribute("class") or ""
            href = elem.get_attribute("href") or "No href"
            aria_label = elem.get_attribute("aria-label") or "No aria-label"
            has_onclick = bool(elem.get_attribute("onclick"))
            print(
                f"Debug: Element {i}: RawText='{raw_text}', NormalizedText='{normalized_elem_text}', VisibleText='{visible_text}', Tag={tag_name}, Classes='{classes}', Href='{href}', AriaLabel='{aria_label}', Displayed={is_displayed}, Enabled={is_enabled}, HasOnclick={has_onclick}")

            # Categorize elements
            if tag_name == "a" and href.startswith(('http:', 'https:')):
                prioritized_elements.append((0, i, elem))  # Priority 0: <a> with valid href
            elif tag_name == "button" or has_onclick:
                prioritized_elements.append((1, i, elem))  # Priority 1: <button> or onclick
            else:
                prioritized_elements.append((2, i, elem))  # Priority 2: Others (e.g., <span>, <div>)

        # Sort by priority and original index to maintain order within priority
        prioritized_elements.sort(key=lambda x: (x[0], x[1]))
        clickable_elements = [e[2] for e in prioritized_elements if e[2].is_displayed() and e[2].is_enabled()]

        if not clickable_elements:
            print("Debug: No visible and enabled elements found.")
            return f"No visible and enabled elements found with text '{original_text}'."

        # Try clicking the first clickable element
        element = clickable_elements[0]
        visible_text = element.text.strip() or element.get_attribute("aria-label") or element.get_attribute(
            "title") or "Element"
        href = element.get_attribute("href") or None
        tag_name = element.tag_name
        print(f"Debug: Targeting element with text: '{visible_text}', Tag={tag_name}, Href={href or 'No href'}")

        # Scroll to element and remove target attribute
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element)
        if tag_name == "a":
            driver.execute_script("arguments[0].removeAttribute('target');", element)
        time.sleep(0.5)  # Brief pause for scrolling

        # Attempt click with retry
        for attempt in range(2):
            try:
                WebDriverWait(driver, 15).until(EC.element_to_be_clickable(element))
                element.click()
                print(f"Clicked element with text: '{visible_text}'")
                time.sleep(2)  # Wait for navigation
                # Handle new tabs
                if len(driver.window_handles) > 1:
                    original_window = driver.current_window_handle
                    for handle in driver.window_handles:
                        if handle != original_window:
                            driver.switch_to.window(handle)
                            driver.close()
                    driver.switch_to.window(original_window)
                    print("Debug: Closed new tab and switched back to original.")
                print(f"Debug: Current URL after click: {driver.current_url}")
                return f"Clicked element with text: '{visible_text}'"
            except (ElementClickInterceptedException, TimeoutException, WebDriverException) as e:
                print(f"Debug: Click failed on attempt {attempt + 1}: {e}")
                if attempt == 1 and tag_name == "a" and href and href.startswith(('http:', 'https:')):
                    # Fallback to navigating to href
                    print(f"Debug: Click failed, navigating to href: {href}")
                    try:
                        driver.get(href)
                        time.sleep(2)
                        print(f"Debug: Navigated to href: {href}")
                        print(f"Debug: Current URL after navigation: {driver.current_url}")
                        return f"Failed to click element with text '{visible_text}', navigated to {href} instead"
                    except Exception as nav_e:
                        print(f"Debug: Navigation to href failed: {nav_e}")
                        return f"Error clicking element with text '{original_text}' and navigating to href: {nav_e}"
                elif attempt == 1:
                    print(
                        f"Debug: No valid href for fallback or element is not an <a> (Tag={tag_name}, Href={href or 'No href'})")
                    return f"Error clicking element with text '{original_text}': {e}"

    except Exception as e:
        print(f"Debug: General error in click_element_by_text: {e}")
        return f"Error clicking element with text '{original_text}': {e}"

def click_youtube_video(driver, video_description=None):
    try:
        wait_until_loaded(driver, By.TAG_NAME, "body", timeout=10)
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        youtube_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'youtube.com/watch' in href or 'youtu.be' in href:
                title = a.text.strip() or href
                youtube_links.append({"title": title, "url": urljoin(driver.current_url, href)})

        if not youtube_links:
            return "No YouTube videos found on the page."

        if len(youtube_links) == 1:
            driver.get(youtube_links[0]["url"])
            return f"Clicked YouTube video: {youtube_links[0]['title']}"

        if video_description:
            matches = [
                link for link in youtube_links
                if video_description.lower() in link["title"].lower()
            ]
            if matches:
                driver.get(matches[0]["url"])
                return f"Clicked YouTube video: {matches[0]['title']}"
            else:
                return f"No YouTube video matching '{video_description}' found."

        return {
            "message": "Multiple YouTube videos found. Please specify which one.",
            "videos": youtube_links
        }
    except Exception as e:
        print(f"Error clicking YouTube video: {e}")
        return f"Error clicking YouTube video: {e}"

def go_back(driver):
    try:
        driver.back()
        time.sleep(1)  # Wait for page to load
        return {"status": "success", "message": "Navigated back to the previous page."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to go back: {str(e)}"}

def go_forward(driver):
    try:
        driver.forward()
        time.sleep(2)  # Brief pause to ensure page loads
        return "Navigated forward successfully."
    except Exception as e:
        print(f"Error going forward: {e}")
        return f"Error going forward: {e}"

def scroll_down(driver, pixels=1000):
    """
    Scrolls down the page by a specified number of pixels.
    """
    try:
        driver.execute_script(f"window.scrollBy(0, {pixels});")
        time.sleep(1)  # Optional pause for smoother automation
        return {"status": "success", "message": f"Scrolled down by {pixels} pixels."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to scroll down: {str(e)}"}


def scroll_up(driver, pixels=1000):
    """
    Scrolls up the page by a specified number of pixels.
    """
    try:
        driver.execute_script(f"window.scrollBy(0, -{pixels});")
        time.sleep(1)  # Optional pause
        return {"status": "success", "message": f"Scrolled up by {pixels} pixels."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to scroll up: {str(e)}"}

def close_tab(driver):
    try:
        # Get the current window handle (tab)
        current_handle = driver.current_window_handle
        # Get all window handles
        all_handles = driver.window_handles

        if len(all_handles) <= 1:
            # If only one tab is open, return a message but don't close
            return "Cannot close the last tab. At least one tab must remain open."

        # Close the current tab
        driver.close()

        # Switch to the first available tab
        for handle in all_handles:
            if handle != current_handle:
                driver.switch_to.window(handle)
                break

        time.sleep(1)  # Brief pause to ensure tab switch
        return "Closed current tab and switched to another tab successfully."
    except Exception as e:
        print(f"Error closing tab: {e}")
        return f"Error closing tab: {e}"

def navigate_to_url(driver, url):
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        driver.get(url)
        wait_until_loaded(driver, By.TAG_NAME, "body", timeout=10)
        return f"Navigated to {url} successfully."
    except Exception as e:
        print(f"Error navigating to {url}: {e}")
        return f"Error navigating to {url}: {e}"

def extract_contact_info(driver, organization):
    """
    Extract phone numbers from the current webpage.
    Returns a list of phone numbers found.
    """
    try:
        wait_until_loaded(driver, By.TAG_NAME, "body", timeout=10)
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        phone_regex = r'\b(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b'
        phone_numbers = set()

        for text in soup.find_all(text=True):
            matches = re.findall(phone_regex, text)
            for match in matches:
                phone = ''.join(filter(str.isdigit, ''.join(match)))
                if len(phone) >= 10:
                    formatted_phone = f"({phone[-10:-7]}) {phone[-7:-4]}-{phone[-4:]}"
                    if phone.startswith('1'):
                        formatted_phone = f"+1 {formatted_phone}"
                    phone_numbers.add(formatted_phone)

        return list(phone_numbers) if phone_numbers else ["No phone numbers found."]
    except Exception as e:
        print(f"Error extracting contact info: {e}")
        return ["Error extracting contact info."]

def collect_search_links(driver, max_links=10):
    """
    Collect the first max_links from the search results page.
    Returns a list of dictionaries with URL and title.
    """
    try:
        wait_until_loaded(driver, By.TAG_NAME, "body", timeout=10)
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        links = []
        result_elements = soup.find_all('li', class_='b_algo')[:max_links]

        for elem in result_elements:
            link = elem.find('a')
            if link and 'href' in link.attrs:
                title = link.text.strip()
                url = link['href']
                url = urljoin(driver.current_url, url)
                links.append({"title": title, "url": url})

        return links if links else [{"title": "No links found", "url": ""}]
    except Exception as e:
        print(f"Error collecting links: {e}")
        return [{"title": "Error collecting links", "url": ""}]

def summarize_page(driver, url):
    """
    Navigate to a URL and summarize its content.
    Returns a brief summary of the page.
    """
    try:
        driver.get(url)
        wait_until_loaded(driver, By.TAG_NAME, "body", timeout=10)
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        text_elements = soup.find_all(['p', 'h1', 'h2', 'h3', 'li'])
        text = ' '.join(elem.get_text().strip() for elem in text_elements if elem.get_text().strip())

        words = text.split()[:200]
        summary = ' '.join(words)

        return summary if summary else "No content found to summarize."
    except Exception as e:
        print(f"Error summarizing page {url}: {e}")
        return f"Error summarizing page {url}."

def fill_form(driver, url, form_data):
    """
    Navigate to a URL and fill out a form with the provided data.
    form_data: Dictionary with field names/IDs and values (e.g., {"name": "John", "email": "john@example.com"})
    Returns a success or error message.
    """
    try:
        driver.get(url)
        wait_until_loaded(driver, By.TAG_NAME, "body", timeout=10)

        for field, value in form_data.items():
            try:
                # Try finding by ID, name, or placeholder
                element = None
                for by, identifier in [
                    (By.ID, field),
                    (By.NAME, field),
                    (By.XPATH, f"//input[@placeholder='{field}']"),
                    (By.XPATH, f"//textarea[@name='{field}' or @id='{field}']")
                ]:
                    try:
                        element = driver.find_element(by, identifier)
                        break
                    except:
                        continue

                if element:
                    if element.tag_name == "input" or element.tag_name == "textarea":
                        human_type(element, value)
                        print(f"Filled field '{field}' with value '{value}'")
                    elif element.tag_name == "select":
                        from selenium.webdriver.support.ui import Select
                        Select(element).select_by_visible_text(value)
                        print(f"Selected option '{value}' for field '{field}'")
                    else:
                        print(f"Unsupported element type for field '{field}'")
                else:
                    print(f"Field '{field}' not found")
            except Exception as e:
                print(f"Error filling field '{field}': {e}")

        # Attempt to submit the form
        try:
            submit_button = driver.find_element(By.XPATH, "//button[@type='submit'] | //input[@type='submit']")
            submit_button.click()
            print("Form submitted successfully.")
            return "Form submitted successfully."
        except:
            print("No submit button found or unable to submit.")
            return "Form filled but not submitted (no submit button found)."

    except Exception as e:
        print(f"Error filling form: {e}")
        return f"Error filling form: {e}"

def main():
    driver = setup_browser_with_profile(headless=False)
    try:
        search_query = "OpenAI"
        print(f"Searching for: {search_query}")
        search(driver, search_query)

        button_text = "OpenAI"
        print(f"Clicking element with text: {button_text}")
        click_element_by_text(driver, button_text)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        input("Press Enter to close browser...")
        driver.quit()

if __name__ == "__main__":
    main()

