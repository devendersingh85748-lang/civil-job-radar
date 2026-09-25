import os
import re
import time
import html
import urllib3
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SUPABASE_URL = "https://hnrodyjundgwylskvhbj.supabase.co"
SUPABASE_KEY = (os.environ.get("SUPABASE_KEY") or "sb_publishable_LdGBnlTBOeTRo9bpxnAZ8Q_y67l0BVy").strip()
TELEGRAM_TOKEN = (os.environ.get("TELEGRAM_TOKEN") or "").strip()
CHAT_ID = (os.environ.get("CHAT_ID") or "1061824304").replace("Id:", "").replace("id:", "").strip()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

EXCLUDE_WORDS = [
    "staff nurse", "nursing", "medical officer", "pharmacist", "constable",
    "stenographer", "typist", "anatomist", "ayurvedic", "homeopathic",
    "veterinary", "driver", "peon", "sweeper", "tgt arts", "pgt hindi"
]

# ==========================================
# 1. SMART ROLE HEADER, QUALIFICATION & DATE EXTRACTOR
# ==========================================
def analyze_job_card(title: str, source: str):
    t = title.lower()
    if any(bad in t for bad in EXCLUDE_WORDS):
        return None

    is_private = any(x in source.lower() for x in ["private", "mnc", "epc"])

    # Default qualification flags
    dip, btech, mtech = False, False, False
    header = ""
    short_cat = ""

    # 1. Check M.Tech / Lecturer / Scientist / Specialist Design
    if any(k in t for k in [
        "lecturer", "polytechnic", "assistant professor", "faculty", "scientist",
        "structural", "geotechnical", "transportation", "water resources",
        "bridge design", "m.tech", "mtech", "research associate", "srf", "jrf", "bim"
    ]):
        mtech = True
        btech = True
        if "lecturer" in t or "professor" in t or "faculty" in t or "polytechnic" in t:
            header = "🟪 【 🎓 LECTURER / ACADEMIC FACULTY 】"
        elif "scientist" in t or "srf" in t or "jrf" in t or "research" in t:
            header = "🟪 【 🔬 SCIENTIST / R&D PROJECT 】"
        else:
            header = "🟪 【 📐 M.TECH SPECIALIST / DESIGN 】"
        short_cat = "M.Tech"

    # 2. Check Diploma / JE Level
    elif any(k in t for k in [
        "junior engineer", "je ", "j.e.", "jdlcce", "ssc je", "rrb je",
        "diploma", "det ", "overseer", "surveyor", "draughtsman",
        "site supervisor", "technical assistant", "work inspector", "amin"
    ]):
        dip = True
        btech = True  # B.Tech is also eligible in SSC JE, RRB JE, JSSC JE, etc.
        header = "🟨 【 👷 JUNIOR ENGINEER (JE) / DIPLOMA 】"
        short_cat = "Diploma"

    # 3. Check B.Tech / AE / PSU / Site & Billing
    elif any(k in t for k in [
        "assistant engineer", "ae ", "a.e.", "sdo", "executive engineer",
        "graduate engineer", "get ", "management trainee", "executive trainee",
        "gate ", "site engineer", "billing", "planning", "quantity surveyor",
        "qa/qc", "highway", "resident engineer", "project engineer", "contracts", "civil"
    ]):
        btech = True
        if any(x in t for x in ["assistant engineer", "ae ", "a.e.", "sdo", "executive", "gate ", "psu"]):
            header = "🟦 【 🏛️ ASSISTANT ENGINEER (AE) / PSU 】"
            mtech = True
        elif is_private or any(x in t for x in ["site", "billing", "planning", "qa/qc", "qs"]):
            header = "🟧 【 🏗️ MNC SITE / BILLING / PLANNING 】"
            dip = True
        else:
            header = "🟦 【 🏛️ B.TECH CIVIL RECRUITMENT 】"
        short_cat = "B.Tech"

    else:
        return None

    # Extract dates if mentioned in title/notice text
    date_pattern = r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})'
    found_dates = re.findall(date_pattern, title, re.IGNORECASE)

    today_str = datetime.now().strftime("%d %b %Y")
    start_date = found_dates[0] if len(found_dates) >= 2 else today_str
    end_date = found_dates[-1] if len(found_dates) >= 1 else "Refer Official PDF"

    # Build visual badge string
    d_badge = "✅ <b>DIPLOMA</b>" if dip else "⬜ Diploma"
    b_badge = "✅ <b>B.TECH</b>" if btech else "⬜ B.Tech"
    m_badge = "✅ <b>M.TECH</b>" if mtech else "⬜ M.Tech"

    qual_code = f"{'D' if dip else ''}{'B' if btech else ''}{'M' if mtech else ''}"

    # Pack metadata into category column so Supabase needs zero schema changes
    packed_category = f"{short_cat}|{header}|{qual_code}|{start_date}|{end_date}"

    return {
        "header": header,
        "d_badge": d_badge,
        "b_badge": b_badge,
        "m_badge": m_badge,
        "start_date": start_date,
        "end_date": end_date,
        "packed_category": packed_category,
        "sector": "🏢 Private MNC" if is_private else "🏛️ Govt / PSU"
    }

# ==========================================
# 2. TELEGRAM RICH CARD SENDER (HTML + BUTTON)
# ==========================================
def send_telegram_card(title, source, link, info):
    if not TELEGRAM_TOKEN:
        return

    safe_title = html.escape(title)
    safe_source = html.escape(source)

    card_text = (
        f"<b>{info['header']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>Post:</b> {safe_title}\n"
        f"🏢 <b>Dept/Org:</b> <code>{safe_source}</code> ({info['sector']})\n\n"
        f"🎓 <b>ELIGIBILITY HIGHLIGHT:</b>\n"
        f"{info['d_badge']}  |  {info['b_badge']}  |  {info['m_badge']}\n\n"
        f"📅 <b>IMPORTANT DATES:</b>\n"
        f"🟢 <b>Start / Posted:</b> {info['start_date']}\n"
        f"🔴 <b>Last Date:</b> {info['end_date']}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": card_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "📄 Official Notification / Apply Now ↗", "url": link}
            ]]
        }
    }
    try:
        requests.post(url, json=payload, timeout=10)
        time.sleep(1)
    except Exception as e:
        print(f"Telegram Error: {e}")

def process_item(title, source, link):
    if not title or not link or len(title.strip()) < 8:
        return
    title = " ".join(title.split())
    info = analyze_job_card(title, source)
    if not info:
        return

    try:
        api_url = f"{SUPABASE_URL}/rest/v1/civil_jobs"
        check = requests.get(
            api_url,
            headers=SUPABASE_HEADERS,
            params={"link": f"eq.{link}", "select": "id"},
            timeout=10
        )
        if check.status_code == 200 and len(check.json()) == 0:
            ins = requests.post(
                api_url,
                headers=SUPABASE_HEADERS,
                json={
                    "title": title[:250],
                    "source": source,
                    "category": info["packed_category"],
                    "link": link
                },
                timeout=10
            )
            if ins.status_code in [200, 201, 204]:
                print(f"[NEW CARD] {info['header']} -> {title}")
                send_telegram_card(title, source, link, info)
    except Exception as e:
        print(f"Database Warning: {e}")

# ==========================================
# 3. SCRAPERS (GOVT + PSU + R&D + MNC)
# ==========================================
DIRECT_PORTALS = [
    {"name": "JSSC Jharkhand", "url": "https://jssc.jharkhand.gov.in/notices", "base": "https://jssc.jharkhand.gov.in"},
    {"name": "JPSC Jharkhand", "url": "https://www.jpsc.gov.in/exam_files.php", "base": "https://www.jpsc.gov.in/"},
    {"name": "BPSC Bihar", "url": "https://www.bpsc.bih.nic.in/", "base": "https://www.bpsc.bih.nic.in/"},
    {"name": "BTSC Bihar (JE/AE)", "url": "https://btsc.bihar.gov.in/latest-update", "base": "https://btsc.bihar.gov.in"},
    {"name": "UPPSC UP", "url": "https://uppsc.up.nic.in/CandidatePages/Notifications.aspx", "base": "https://uppsc.up.nic.in"},
    {"name": "WBPSC West Bengal", "url": "https://psc.wb.gov.in/all_announcement.jsp", "base": "https://psc.wb.gov.in/"},
    {"name": "DSSSB Delhi", "url": "https://dsssb.delhi.gov.in/vacancy-advertisements", "base": "https://dsssb.delhi.gov.in"},
    {"name": "DMRC Delhi Metro", "url": "https://www.delhimetrorail.com/pages/en/career", "base": "https://www.delhimetrorail.com"},
    {"name": "NCRTC (RRTS Metro)", "url": "https://ncrtc.in/jobs/", "base": "https://ncrtc.in"},
    {"name": "DFCCIL Railways", "url": "https://dfccil.com/Home/AllActiveCareer", "base": "https://dfccil.com"},
    {"name": "RITES Ltd", "url": "https://www.rites.com/Career", "base": "https://www.rites.com/"},
    {"name": "IRCON International", "url": "https://www.ircon.org/index.php?lang=en", "base": "https://www.ircon.org/"},
    {"name": "CSIR-CBRI Roorkee", "url": "https://cbri.res.in/careers/", "base": "https://cbri.res.in"},
    {"name": "CSIR-CRRI Delhi", "url": "https://crridom.gov.in/recruitment", "base": "https://crridom.gov.in"},
    {"name": "NIH Roorkee (Hydrology)", "url": "https://nihroorkee.gov.in/career-opportunities", "base": "https://nihroorkee.gov.in"}
]

def run_direct_scrapers():
    for portal in DIRECT_PORTALS:
        try:
            r = requests.get(portal["url"], headers=HEADERS, timeout=15, verify=False)
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                title = a.get_text(" ", strip=True)
                href = a["href"].strip()
                if not href or href.startswith("javascript") or href == "#":
                    continue
                full_link = href if href.startswith("http") else f"{portal['base'].rstrip('/')}/{href.lstrip('/')}"
                process_item(title, portal["name"], full_link)
        except Exception as e:
            print(f"Direct Scrape Warning ({portal['name']}): {e}")

VERIFIED_SEARCH_FEEDS = [
    {
        "source": "Central Govt (SSC / RRB / UPSC / NHAI)",
        "query": '(site:ssc.gov.in OR site:indianrailways.gov.in OR site:upsc.gov.in OR site:nhai.gov.in OR site:nbccindia.in) ("Junior Engineer" OR "Assistant Engineer" OR "Civil" OR "Recruitment" OR "JE")'
    },
    {
        "source": "State Govt (JE / AE / Lecturer)",
        "query": '(site:jssc.jharkhand.gov.in OR site:jpsc.gov.in OR site:bpsc.bih.nic.in OR site:uppsc.up.nic.in OR site:upsssc.gov.in OR site:hpsc.gov.in OR site:hssc.gov.in) ("Civil" OR "Junior Engineer" OR "Assistant Engineer" OR "Lecturer" OR "Polytechnic")'
    },
    {
        "source": "PSU Civil Recruitment",
        "query": '(site:careers.ntpc.co.in OR site:powergrid.in OR site:iocl.com OR site:rvnl.org OR site:nhpcindia.com OR site:thdc.co.in OR site:npcilcareers.co.in) ("Civil" OR "Executive Trainee" OR "Diploma Trainee" OR "Assistant Engineer")'
    },
    {
        "source": "Academic & Research (M.Tech / B.Tech)",
        "query": '(site:ac.in OR site:res.in OR site:aicte-india.org) ("Civil Engineering" OR "Structural" OR "Geotechnical") ("Lecturer" OR "Assistant Professor" OR "Scientist" OR "Project Associate" OR "Guest Faculty")'
    },
    {
        "source": "Private EPC Giant (L&T / Tata / Afcons / Shapoorji)",
        "query": '("L&T Construction" OR "Larsen & Toubro" OR "Tata Projects" OR "Afcons" OR "Shapoorji Pallonji" OR "KEC International" OR "NCC Limited" OR "HG Infra") ("Civil Engineer" OR "Site Engineer" OR "Billing Engineer" OR "Planning Engineer" OR "Structural Engineer" OR "GET" OR "MT")'
    },
    {
        "source": "Global Design MNC (WSP / AECOM / Atkins / Jacobs / Systra)",
        "query": '("AECOM" OR "WSP" OR "AtkinsRealis" OR "Jacobs" OR "Mott MacDonald" OR "Ramboll" OR "Arup" OR "Systra" OR "Egis" OR "SMEC" OR "STUP Consultants") ("Structural Engineer" OR "Bridge Engineer" OR "Geotechnical" OR "Civil Engineer" OR "Highway" OR "Water Resources" OR "BIM") ("India" OR "Gurugram" OR "Noida" OR "Delhi" OR "Kolkata" OR "Mumbai" OR "Bengaluru" OR "Hyderabad")'
    }
]

def run_verified_feeds():
    for feed in VERIFIED_SEARCH_FEEDS:
        try:
            encoded_query = requests.utils.quote(f"{feed['query']} when:7d")
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:15]:
                title = item.find("title").text
                link = item.find("link").text
                process_item(title, feed["source"], link)
        except Exception as e:
            print(f"Feed Warning ({feed['source']}): {e}")

PRIVATE_ROLES = [
    {"role": "Civil Structural Engineer", "loc": "India"},
    {"role": "Civil Billing Planning Engineer", "loc": "India"},
    {"role": "Civil Site Engineer", "loc": "Gurugram"},
    {"role": "Bridge Highway Design Engineer", "loc": "India"},
    {"role": "Geotechnical Water Resources Engineer", "loc": "India"},
    {"role": "Civil Engineering Lecturer Faculty", "loc": "India"}
]

def run_private_mnc_jobs():
    for item in PRIVATE_ROLES:
        try:
            url = (
                f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"
                f"keywords={requests.utils.quote(item['role'])}&"
                f"location={requests.utils.quote(item['loc'])}&"
                f"f_TPR=r86400&start=0"
            )
            r = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            for card in soup.find_all("div", class_="base-card")[:8]:
                title_el = card.find("h3", class_="base-search-card__title")
                company_el = card.find("h4", class_="base-search-card__subtitle")
                loc_el = card.find("span", class_="job-search-card__location")
                link_el = card.find("a", class_="base-card__full-link")

                if title_el and company_el and link_el:
                    job_title = title_el.get_text(strip=True)
                    company = company_el.get_text(strip=True)
                    location = loc_el.get_text(strip=True) if loc_el else "India"
                    clean_link = link_el["href"].split("?")[0]

                    full_title = f"{job_title} — {company} ({location})"
                    process_item(full_title, f"Private Direct ({company})", clean_link)
        except Exception as e:
            print(f"Private Job Scrape Warning ({item['role']}): {e}")

if __name__ == "__main__":
    print("🚀 Starting Structured Card Civil Job Radar...")
    run_direct_scrapers()
    run_verified_feeds()
    run_private_mnc_jobs()
    print("✅ Scan Complete!")
