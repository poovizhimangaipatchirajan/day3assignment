import pyautogui
import pyperclip
import pandas as pd
import time
import os
import re
from datetime import datetime

URL = "https://www.goodreturns.in/gold-rates/chennai.html"

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 1


def open_chrome():

    pyautogui.press("win")
    time.sleep(1)

    pyautogui.write("chrome")
    pyautogui.press("enter")

    time.sleep(5)


def open_gold_page():

    pyautogui.hotkey("ctrl", "l")

    pyautogui.write(URL)

    pyautogui.press("enter")

    time.sleep(8)


def copy_page_content():

    pyautogui.hotkey("ctrl", "a")
    time.sleep(1)

    pyautogui.hotkey("ctrl", "c")
    time.sleep(2)

    return pyperclip.paste()


def extract_gold_rates(page_text):

    match24 = re.search(
        r"₹([\d,]+)\s+per gram for 24 karat gold",
        page_text,
        re.IGNORECASE
    )

    match22 = re.search(
        r"₹([\d,]+)\s+per gram for 22 karat gold",
        page_text,
        re.IGNORECASE
    )

    match18 = re.search(
        r"₹([\d,]+)\s+per gram for 18 karat gold",
        page_text,
        re.IGNORECASE
    )

    rate24 = match24.group(1) if match24 else "N/A"
    rate22 = match22.group(1) if match22 else "N/A"
    rate18 = match18.group(1) if match18 else "N/A"

    return rate24, rate22, rate18


def create_excel_file(
    timestamp,
    rate24,
    rate22,
    rate18,
    filename
):

    df = pd.DataFrame([{
        "Date Time": timestamp,
        "24K Gold Rate": rate24,
        "22K Gold Rate": rate22,
        "18K Gold Rate": rate18
    }])

    df.to_excel(
        filename,
        index=False
    )


def open_excel_file(filename):

    os.startfile(
        os.path.abspath(filename)
    )

    time.sleep(8)


def take_screenshot(filename):

    image = pyautogui.screenshot()

    image.save(filename)


def main():

    now = datetime.now()

    timestamp = now.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    current_date = now.strftime(
        "%Y-%m-%d"
    )

    excel_file = (
        f"daily_report_{current_date}_{now.strftime('%H%M%S')}.xlsx"
    )

    screenshot_file = (
        f"daily_report_{current_date}_{now.strftime('%H%M%S')}.png"
    )

    print("Opening Chrome...")
    open_chrome()

    print("Opening Gold Rate Website...")
    open_gold_page()

    print("Copying Page Content...")
    page_text = copy_page_content()

    print("Extracting Gold Rates...")
    rate24, rate22, rate18 = extract_gold_rates(
        page_text
    )

    print("24K Gold Rate:", rate24)
    print("22K Gold Rate:", rate22)
    print("18K Gold Rate:", rate18)

    print("Creating Excel Report...")

    create_excel_file(
        timestamp,
        rate24,
        rate22,
        rate18,
        excel_file
    )

    print("Opening Excel Report...")
    open_excel_file(excel_file)

    print("Taking Screenshot...")
    take_screenshot(screenshot_file)

    print("\n✅ Report Generated Successfully")
    print("Excel File:", excel_file)
    print("Screenshot:", screenshot_file)
 

if __name__ == "__main__":
    main()