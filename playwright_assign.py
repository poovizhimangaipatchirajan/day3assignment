from playwright.sync_api import sync_playwright, TimeoutError
import pandas as pd
import json
import os
import random
import re
from datetime import datetime


# ==========================
# CONFIG
# ==========================

WHATSAPP_URL = "https://web.whatsapp.com"
LOGIN_TIMEOUT_MS = 300000

SCREENSHOT_DIR = "screenshots"
USER_DATA_DIR = "whatsapp_profile"

os.makedirs(
    SCREENSHOT_DIR,
    exist_ok=True
)


# ==========================
# HELPERS
# ==========================

def human_pause(page, min_sec=2, max_sec=5):
    page.wait_for_timeout(
        int(random.uniform(min_sec, max_sec) * 1000)
    )


def wait_for_login(page):

    print(
        "\nWaiting for WhatsApp login. If a QR code appears, "
        "scan it with WhatsApp on your phone; waiting up to 5 minutes..."
    )

    try:
        page.wait_for_selector(
            '#side, [aria-label="Chat list"], [data-testid="chat-list"], '
            '[aria-label="Search input"], '
            'div[contenteditable="true"][data-tab="3"]',
            timeout=LOGIN_TIMEOUT_MS
        )
    except TimeoutError:
        print(
            "WhatsApp login was not detected. Check that the QR code was "
            "scanned and that WhatsApp Web finished loading, then run again."
        )
        return False

    print("Login successful")
    return True


def replace_template(message, name):

    if pd.isna(message):
        message = "Hello {name}"

    return str(message).replace(
        "{name}",
        str(name)
    )


def first_visible_locator(page, selectors, timeout=10000):
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(
                state="visible",
                timeout=timeout
            )
            return locator
        except TimeoutError:
            continue

    raise TimeoutError(
        f"Could not find a visible element for selectors: {selectors}"
    )


def open_search_box(page):
    field_selectors = [
        '[aria-label="Search input"]',
        'div[contenteditable="true"][data-tab="3"]',
        'input[placeholder*="Search"]'
    ]

    for selector in field_selectors:
        field = page.locator(selector).first
        try:
            field.wait_for(state="visible", timeout=1500)
            field.click(timeout=2500)
            return field
        except TimeoutError:
            continue

    search_buttons = [
        'button[aria-label*="Search"]',
        '[role="button"][aria-label*="Search"]',
        'button:has([data-icon="search"])',
        '[data-icon="search"]'
    ]
    for selector in search_buttons:
        button = page.locator(selector).first
        try:
            button.wait_for(state="visible", timeout=1500)
            button.click(timeout=2500)
            return first_visible_locator(page, field_selectors, timeout=5000)
        except TimeoutError:
            continue

    raise TimeoutError(
        "Could not open WhatsApp search. Check that the chat list is loaded."
    )


def active_chat_matches_contact(page, query, fallback_query=None):
    try:
        header = first_visible_locator(
            page,
            ['#main header, [data-testid="conversation-panel-header"]'],
            timeout=5000
        )
        header_text = header.inner_text(timeout=5000).casefold()
    except TimeoutError:
        return False

    if fallback_query and fallback_query.casefold() in header_text:
        return True

    target_digits = re.sub(r"\D", "", query)
    header_digits = re.sub(r"\D", "", header_text)
    return len(target_digits) >= 10 and (
        header_digits.endswith(target_digits)
        or header_digits.endswith(target_digits[-10:])
    )


def search_contact(page, query, fallback_query=None):
    search_box = open_search_box(page)
    search_terms = [query]
    if fallback_query and fallback_query.casefold() != query.casefold():
        search_terms.append(fallback_query)

    chat_opened = False
    for search_term in search_terms:
        try:
            search_box.click(timeout=5000)
            search_box.fill(search_term, timeout=5000)
            page.wait_for_timeout(2000)

            result = page.locator("#pane-side").get_by_text(
                search_term,
                exact=False
            ).last
            result.wait_for(state="visible", timeout=5000)
            result_row = result.locator(
                "xpath=ancestor::*[@role='listitem' or @role='row'][1]"
            )
            if result_row.count():
                result_row.click(timeout=5000)
            else:
                result.click(timeout=5000)

            page.locator('footer div[contenteditable="true"]').first.wait_for(
                state="visible",
                timeout=5000
            )
            chat_opened = active_chat_matches_contact(
                page,
                query,
                fallback_query
            )
            if chat_opened:
                break
        except TimeoutError:
            continue

    if not chat_opened:
        phone_digits = re.sub(r"\D", "", query)
        if len(phone_digits) < 10:
            raise LookupError(
                f"Could not automatically open the chat for: {', '.join(search_terms)}"
            )

        page.goto(
            f"{WHATSAPP_URL}/send?phone={phone_digits}",
            wait_until="domcontentloaded"
        )
        try:
            first_visible_locator(
                page,
                [
                    'footer div[contenteditable="true"][role="textbox"]',
                    'footer [aria-label="Type a message"]',
                    'footer div[contenteditable="true"][data-tab="10"]'
                ],
                timeout=5000
            )
        except TimeoutError:
            raise LookupError(f"WhatsApp did not open a chat for {query}")

        if not active_chat_matches_contact(page, query, fallback_query):
            raise LookupError(
                f"Opened chat did not match {fallback_query or query}"
            )

    first_visible_locator(
        page,
        [
            'footer div[contenteditable="true"][role="textbox"]',
            'footer [aria-label="Type a message"]',
            'footer div[contenteditable="true"][data-tab="10"]'
        ]
    )


def extract_recent_messages(page, query, contact_name):
    if not active_chat_matches_contact(page, query, contact_name):
        raise LookupError(
            f"The active chat does not match {contact_name or query}"
        )

    incoming_bubbles = page.locator("#main div.message-in").all()
    messages = []
    text_selectors = [
        '[data-testid="selectable-text"]',
        ".selectable-text",
        "[data-pre-plain-text]"
    ]

    for bubble in incoming_bubbles:
        message_text = ""
        for selector in text_selectors:
            parts = bubble.locator(selector).all_inner_texts()
            message_text = "\n".join(
                part.strip() for part in parts if part.strip()
            )
            if message_text:
                break

        if not message_text:
            message_text = bubble.inner_text().strip()

        if message_text:
            messages.append(message_text)

    return messages[-3:]


def save_reports(report):
    report_date = datetime.now().strftime("%Y-%m-%d")
    json_path = f"whatsapp_report_{report_date}.json"
    excel_path = f"whatsapp_report_{report_date}.xlsx"

    with open(json_path, "w", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2, ensure_ascii=False)

    excel_report = [
        {
            **item,
            "recent_messages": json.dumps(
                item["recent_messages"],
                ensure_ascii=False
            )
        }
        for item in report
    ]
    excel_frame = pd.DataFrame(excel_report)
    try:
        excel_frame.to_excel(excel_path, index=False)
    except PermissionError:
        excel_path = (
            f"whatsapp_report_{report_date}_"
            f"{datetime.now():%H%M%S}.xlsx"
        )
        excel_frame.to_excel(excel_path, index=False)
        print(
            "The dated Excel report is open or locked; "
            f"saved this run as {excel_path} instead."
        )

    print(f"Reports saved: {json_path} and {excel_path}")


# ==========================
# CONTACT FILE LOADER
# ==========================

def load_contacts():

    CONTACTS_FILE = "contacts.xlsx"

    try:

        if not os.path.exists(CONTACTS_FILE):

            print(
                f"\n{CONTACTS_FILE} not found."
            )

            sample_df = pd.DataFrame([
                {
                    "Name": "John Doe",
                    "Phone": "919999999999",
                    "Message": "Hello {name}, how are you?"
                }
            ])

            sample_df.to_excel(
                CONTACTS_FILE,
                index=False
            )

            print(
                f"Created template file: {CONTACTS_FILE}"
            )

            return None

        contacts = pd.read_excel(
            CONTACTS_FILE
        )

        required_columns = [
            "Name",
            "Phone",
            "Message"
        ]

        for col in required_columns:

            if col not in contacts.columns:

                print(
                    f"Missing column: {col}"
                )

                return None

        if contacts.empty:

            print(
                "contacts.xlsx is empty."
            )

            return None

        return contacts

    except Exception as e:

        print(
            f"Error reading contacts.xlsx: {e}"
        )

        pd.DataFrame(
            columns=[
                "Name",
                "Phone",
                "Message"
            ]
        ).to_excel(
            CONTACTS_FILE,
            index=False
        )

        print(
            "New template file created."
        )

        return None


# ==========================
# MAIN
# ==========================

def main():

    contacts = load_contacts()

    if contacts is None:

        print(
            "\nPlease update contacts.xlsx and run again."
        )

        return

    report = []

    with sync_playwright() as p:

        browser = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False
        )

        page = browser.new_page()

        page.goto(
            WHATSAPP_URL,
            wait_until="load"
        )

        if not wait_for_login(page):
            browser.close()
            return

        for _, row in contacts.iterrows():

            name = str(
                row.get("Name", "")
            ).strip()

            phone = str(
                row.get("Phone", "")
            ).strip()

            message = replace_template(
                row.get("Message", ""),
                name
            )

            print(
                f"\nProcessing: {name}"
            )

            result = {
                "name": name,
                "phone": phone,
                "message": message,
                "status": "",
                "recent_messages": [],
                "screenshot": "",
                "timestamp": str(
                    datetime.now()
                )
            }

            try:
                query = phone or name
                if not query:
                    raise ValueError("Contact has no name or phone number")

                search_contact(page, query, name)
                human_pause(page)

                try:
                    result["recent_messages"] = extract_recent_messages(
                        page,
                        query,
                        name
                    )
                    print(
                        f"Extracted {len(result['recent_messages'])} "
                        f"incoming messages from {name or phone}"
                    )
                except Exception as extraction_error:
                    result["extraction_error"] = str(extraction_error)
                    print(f"Message extraction failed: {extraction_error}")

                message_box = first_visible_locator(
                    page,
                    [
                        'footer div[contenteditable="true"][role="textbox"]',
                        'footer [aria-label="Type a message"]',
                        'footer div[contenteditable="true"][data-tab="10"]'
                    ]
                )
                message_box.fill(message)
                message_box.press("Enter")

                page.wait_for_function(
                    """() => {
                        const composer = document.querySelector(
                            'footer div[contenteditable="true"][role="textbox"]'
                        ) || document.querySelector(
                            'footer [aria-label="Type a message"]'
                        ) || document.querySelector(
                            'footer div[contenteditable="true"][data-tab="10"]'
                        );
                        const text = composer && (
                            composer.innerText || composer.value || ""
                        );
                        return composer && text.trim() === "";
                    }""",
                    timeout=10000
                )

                sent_message = page.locator(
                    "div.message-out"
                ).filter(has_text=message).last

                safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", name or phone)
                screenshot_path = os.path.join(
                    SCREENSHOT_DIR,
                    f"{safe_name}_{datetime.now():%Y%m%d_%H%M%S}.png"
                )
                try:
                    sent_message.wait_for(state="visible", timeout=5000)
                    sent_message.screenshot(path=screenshot_path, timeout=5000)
                except TimeoutError:
                    page.screenshot(path=screenshot_path)

                human_pause(page)

                result["status"] = "SENT"
                result["screenshot"] = screenshot_path
                print(f"Sent message to {name or phone}")

            except Exception as e:

                result["status"] = (
                    f"ERROR: {e}"
                )
                print(
                    f"ERROR: {e}"
                )

            report.append(result)
            human_pause(page)

        print(
            f"\nProcessed {len(report)} contacts."
        )

        save_reports(report)

        browser.close()


if __name__ == "__main__":
    main()