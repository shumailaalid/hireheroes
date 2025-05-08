# app.py
import streamlit as st
import pandas as pd
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time, re, csv
from webdriver_manager.chrome import ChromeDriverManager
import tempfile, shutil
# ─── your existing scraper logic, refactored into a function ───────────────
def scrape_e5_army(download_dir: Path, username: str, password: str) -> pd.DataFrame:
    # set up download folder
    user_data_dir = tempfile.mkdtemp(prefix="chropro_")

    prefs = {
        "download.default_directory": str(download_dir),
        "plugins.always_open_pdf_externally": True,
    }
    opt = webdriver.ChromeOptions()
    # **no** --headless, so the GUI still appears
    opt.add_argument(f"--user-data-dir={user_data_dir}")          # <-- here
    opt.add_argument("--start-maximized")
    opt.add_argument("--disable-blink-features=Auto")
    # … your prefs …

    # This downloads the correct Linux64 binary, puts it in ~/.cache, and ensures +x
    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=opt)
    wait   = WebDriverWait(driver, 20)

    # helper to scroll & click
    def scroll_and_click(by, locator, timeout=20):
        elem = wait.until(EC.presence_of_element_located((by, locator)))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
        wait.until(EC.element_to_be_clickable((by, locator))).click()
        return elem

    # 0. login
    driver.get("https://jobs.hireheroesusa.org/employers/sign_in")
    time.sleep(2)
    driver.find_element(By.CSS_SELECTOR, "input[type='email']").send_keys(username)
    driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "input[name='commit'],button[type='submit']").click()
    time.sleep(5)

    # 1. open filtered Army E-5
    driver.get("https://jobs.hireheroesusa.org/profiles?last_service_rank=E-5&military_branch=Army")
    time.sleep(5)

    # 2. collect profile URLs
    profiles = {a.get_attribute("href")
                for a in driver.find_elements(By.XPATH, "//a[contains(@href,'/profiles/')]")}
    print(f"Found {len(profiles)} profiles.")

    # prepare CSV
    csv_path = "profiles.csv"
    fieldnames = ["full_name","email","phone","linkedin","resume_url",
                  "resume_downloaded","profile_url","Rank","Branch"]
    write_header = not Path(csv_path).exists()

    with open(csv_path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()

        for idx, url in enumerate(profiles, 1):
            driver.get(url)
            time.sleep(5)

            # scrape name
            try:
                full_name = driver.find_element(By.CSS_SELECTOR, "h3.u-mb--small").text.strip()
            except:
                full_name = ""

            # linkedin on page?
            try:
                linkedin_on_page = driver.find_element(
                    By.XPATH, "//a[contains(@href,'linkedin.com')]"
                ).get_attribute("href")
            except:
                linkedin_on_page = ""

            # clear downloads
            for f in download_dir.glob("*"):
                f.unlink(missing_ok=True)

            # download resume
            resume_downloaded = False
            resume_url = ""
            email = phone = linkedin_pdf = ""
            try:
                dl = scroll_and_click(By.XPATH, "//a[contains(.,'Download Resume')]")
                resume_url = dl.get_attribute("href")
                # wait for PDF
                end = time.time() + 60
                while time.time() < end:
                    if not list(download_dir.glob("*.crdownload")):
                        break
                    time.sleep(0.5)
                time.sleep(2)
                pdfs = list(download_dir.glob("*.pdf"))
                if pdfs:
                    # parse pdf here (reuse your pdf_file_to_contacts)
                    from your_module import pdf_file_to_contacts
                    info = pdf_file_to_contacts(pdfs[0])
                    email = info["email"]
                    phone = info["phone"]
                    linkedin_pdf = info["linkedin"]
                    resume_downloaded = True
                    pdfs[0].unlink()
            except Exception as e:
                print("Resume download/parse failed:", e)

            linkedin_final = linkedin_on_page or linkedin_pdf

            row = {
                "full_name": full_name,
                "email": email or "Not Found",
                "phone": phone or "Not Found",
                "linkedin": linkedin_final or "Not Found",
                "resume_url": resume_url,
                "resume_downloaded": resume_downloaded,
                "Rank":"E-5","Branch":"Army","profile_url":url
            }
            writer.writerow(row)
            time.sleep(2)

    driver.quit()
    # return results as DataFrame
    return pd.read_csv(csv_path)


# ─────────────────────────────────────────────────────────────────────────────
# Streamlit UI
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="E-5 Army Scraper", layout="wide")
st.title("Hire Heroes USA: Army E-5 Profiles")

USERNAME ='33'## st.secrets["HHU_USER"]
PASSWORD = ''##st.secrets["HHU_PASS"]
DOWNLOAD_DIR = Path("downloads")

if st.button("Run Scraper (Chrome GUI will pop up)"):
    with st.spinner("Running Selenium…"):
        df = scrape_e5_army(DOWNLOAD_DIR, USERNAME, PASSWORD)
    st.success(f"Finished – {len(df)} rows")
    st.dataframe(df)

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download CSV", csv_bytes, "profiles.csv", "text/csv")

