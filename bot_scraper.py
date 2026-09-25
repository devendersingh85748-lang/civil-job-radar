import os
import time
import urllib3
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from supabase import create_client, Client

# Govt websites ke SSL certificate errors ko bypass karne ke liye
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

# ==========================================
# 1. QUALIFICATION & CIVIL FILTERS
# ==========================================
CATEGORIES = {
    "M.Tech (Lecturer / Scientist / Design)": [
        "lecturer", "polytechnic", "assistant professor", "faculty", "scientist",
        "structural engineer", "structural design", "geotechnical", "transportation",
        "water resources", "environmental", "bridge design", "m.tech", "mtech",
        "project scientist", "research associate", "srf", "jrf", "cbri", "crri", "bim"
    ],
    "B.Tech (AE / PSU / Site & Billing)": [
        "assistant engineer", "ae ", "a.e.", "sub divisional officer", "sdo",
        "executive engineer", "graduate engineer", "get ", "management trainee",
        "executive trainee", "gate ", "site engineer", "billing engineer",
        "planning engineer", "qs ", "quantity surveyor", "qa/qc", "highway engineer",
        "resident engineer", "project engineer", "contracts engineer", "civil engineer"
    ],
    "Diploma (JE / Technical / Supervisor)": [
        "junior engineer", "je ", "j.e.", "jdlcce", "ssc je", "rrb je",
        "diploma trainee", "det ", "overseer", "surveyor", "draughtsman",
        "site supervisor", "technical assistant", "work inspector", "amin"
    ]
}

# Non-engineering jobs ko block karne ke liye (Zero Spam)
EXCLUDE_WORDS = [
    "staff nurse", "nursing", "medical officer", "pharmacist", "constable",
    "stenographer", "typist", "anatomist", "ayurvedic", "homeopathic",
    "veterinary", "driver", "peon", "sweeper", "tgt arts", "pgt hindi"
]

# General notification words jo Civil ke liye zaroori ho sakte hain
GENERAL_CIVIL_TRIGGERS = [
    "civil", "engineering", "engineer", "je", "ae", "jdlcce", "technical",
    "polytechnic", "lecturer", "advt", "advertisement", "recruitment", "vacancy"
]

def classify_job(title: str) -> str:
    t = title.lower()
    if any(bad in t for bad in EXCLUDE_WORDS):
        return None

    for category, keywords in CATEGORIES.items():
        if any(k in t for k in keywords):
            return category

    # Agar general engineering/recruitment notice hai Official Govt site par
    if any(g in t for g in GENERAL_CIVIL_TRIGGERS):
        if "civil" in t or "engineering" in t or "jdlcce" in t or "polytechnic" in t:
            return "B.Tech / Diploma / M.Tech (General Civil)"
    return None

# ==========================================
# 2. DATABASE & TELEGRAM ALERT ENGINE
# ==========================================
def send_telegram_alert(title, source, category, link):
    msg = (
        f"🚨 *100% Verified Civil Engg Job Update*\n\n"
        f"📌 *Title:* {title}\n"
        f"🏛️ *Organization:* `{source}`\n"
        f"🎓 *Target Level:* *{category}*\n\n"
        f"🔗 [Open Official Link / Notification PDF]({link})"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }, timeout=10)
        time.sleep(1) # Telegram rate limit protection
    except Exception as e:
        print(f"Telegram Error: {e}")

def process_item(title, source, link):
    if not title or not link or len(title.strip()) < 8:
        return
    title = " ".join(title.split())
    category = classify_job(title)
    if not category:
        return

    try:
        # Check duplicate in Supabase
        existing = supabase.table("civil_jobs").select("id").eq("link", link).execute()
        if not existing.data:
            supabase.table("civil_jobs").insert({
                "title": title[:250],
                "source": source,
                "category": category,
                "link": link
            }).execute()
            print(f"[NEW] {source}: {title}")
            send_telegram_alert(title, source, category, link)
    except Exception as e:
        print(f"Supabase Error: {e}")

# ==========================================
# 3. DIRECT OFFICIAL GOVT PORTAL SCRAPERS
# ==========================================
DIRECT_PORTALS = [
    # Jharkhand & Neighbouring States
    {"name": "JSSC Jharkhand", "url": "https://jssc.jharkhand.gov.in/notices", "base": "https://jssc.jharkhand.gov.in"},
    {"name": "JPSC Jharkhand", "url": "https://www.jpsc.gov.in/exam_files.php", "base": "https://www.jpsc.gov.in/"},
    {"name": "BPSC Bihar", "url": "https://www.bpsc.bih.nic.in/", "base": "https://www.bpsc.bih.nic.in/"},
    {"name": "BTSC Bihar (JE/AE)", "url": "https://btsc.bihar.gov.in/latest-update", "base": "https://btsc.bihar.gov.in"},
    {"name": "UPPSC UP", "url": "https://uppsc.up.nic.in/CandidatePages/Notifications.aspx", "base": "https://uppsc.up.nic.in"},
    {"name": "WBPSC West Bengal", "url": "https://psc.wb.gov.in/all_announcement.jsp", "base": "https://psc.wb.gov.in/"},
    # Delhi / NCR & Metro / Rail
    {"name": "DSSSB Delhi", "url": "https://dsssb.delhi.gov.in/ vacancy-advertisements", "base": "https://dsssb.delhi.gov.in"},
    {"name": "DMRC Delhi Metro", "url": "https://www.delhimetrorail.com/pages/en/career", "base": "https://www.delhimetrorail.com"},
    {"name": "NCRTC (RRTS Metro)", "url": "https://ncrtc.in/jobs/", "base": "https://ncrtc.in"},
    {"name": "DFCCIL Railways", "url": "https://dfccil.com/Home/AllActiveCareer", "base": "https://dfccil.com"},
    {"name": "RITES Ltd", "url": "https://www.rites.com/Career", "base": "https://www.rites.com/"},
    {"name": "IRCON International", "url": "https://www.ircon.org/index.php?lang=en", "base": "https://www.ircon.org/"},
    # R&D / Scientist / M.Tech Specialist
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

# ==========================================
# 4. CENTRAL GOVT, PSUs, NIT/IIT & PRIVATE MNC ENGINE
# (Bypasses JS/Cloudflare blocks via Verified Feeds)
# ==========================================
VERIFIED_SEARCH_FEEDS = [
    # 1. Central Govt & Exams (SSC, RRB, UPSC, CPWD, CWC, BRO)
    {
        "source": "Central Govt (SSC / RRB / UPSC / NHAI)",
        "query": '(site:ssc.gov.in OR site:indianrailways.gov.in OR site:upsc.gov.in OR site:nhai.gov.in OR site:nbccindia.in) ("Junior Engineer" OR "Assistant Engineer" OR "Civil" OR "Recruitment" OR "JE")'
    },
    # 2. State JE / AE / Polytechnic Lecturer (Jharkhand, Bihar, UP, Haryana, MP, Rajasthan)
    {
        "source": "State Govt (JE / AE / Lecturer)",
        "query": '(site:jssc.jharkhand.gov.in OR site:jpsc.gov.in OR site:bpsc.bih.nic.in OR site:uppsc.up.nic.in OR site:upsssc.gov.in OR site:hpsc.gov.in OR site:hssc.gov.in) ("Civil" OR "Junior Engineer" OR "Assistant Engineer" OR "Lecturer" OR "Polytechnic")'
    },
    # 3. Maharatna / Navratna PSUs (NTPC, PGCIL, ONGC, IOCL, GAIL, BHEL,RVNL, THDC, NHPC)
    {
        "source": "PSU Civil Recruitment",
        "query": '(site:careers.ntpc.co.in OR site:powergrid.in OR site:iocl.com OR site:rvnl.org OR site:nhpcindia.com OR site:thdc.co.in OR site:npcilcareers.co.in) ("Civil" OR "Executive Trainee" OR "Diploma Trainee" OR "Assistant Engineer")'
    },
    # 4. M.Tech Special: Polytechnic Lecturer, NITs, IITs, CSIR (Faculty / Scientist / Project)
    {
        "source": "Academic & Research (M.Tech / B.Tech)",
        "query": '(site:ac.in OR site:res.in OR site:aicte-india.org) ("Civil Engineering" OR "Structural" OR "Geotechnical") ("Lecturer" OR "Assistant Professor" OR "Scientist" OR "Project Associate" OR "Guest Faculty")'
    },
    # 5. Top Private EPC & Construction Giants (L&T, Tata Projects, Shapoorji, Afcons, Dilip Buildcon, HCC, NCC, KEC)
    {
        "source": "Private EPC Giant (L&T / Tata / Afcons / Shapoorji)",
        "query": '("L&T Construction" OR "Larsen & Toubro" OR "Tata Projects" OR "Afcons" OR "Shapoorji Pallonji" OR "KEC International" OR "NCC Limited" OR "HG Infra") ("Civil Engineer" OR "Site Engineer" OR "Billing Engineer" OR "Planning Engineer" OR "Structural Engineer" OR "GET" OR "MT")'
    },
    # 6. Top Global Design & Consultancy MNCs (AECOM, WSP, AtkinsRéalis, Jacobs, Ramboll, Arup, Mott MacDonald, SMEC, Systra, Egis)
    {
        "source": "Global Design MNC (WSP / AECOM / Atkins / Jacobs / Systra)",
        "query": '("AECOM" OR "WSP" OR "AtkinsRealis" OR "Jacobs" OR "Mott MacDonald" OR "Ramboll" OR "Arup" OR "Systra" OR "Egis" OR "SMEC" OR "STUP Consultants") ("Structural Engineer" OR "Bridge Engineer" OR "Geotechnical" OR "Civil Engineer" OR "Highway" OR "Water Resources" OR "BIM") ("India" OR "Gurugram" OR "Noida" OR "Delhi" OR "Kolkata" OR "Mumbai" OR "Bengaluru" OR "Hyderabad")'
    }
]

def run_verified_feeds():
    for feed in VERIFIED_SEARCH_FEEDS:
        try:
            # Google News RSS with strict 7-day freshness filter (when:7d)
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

# ==========================================
# 5. DIRECT LINKEDIN & PRIVATE CAREERS SCRAPER (Public Guest API)
# ==========================================
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
            # LinkedIn Public Guest Job Search (Past 24 Hours: f_TPR=r86400)
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
                    clean_link = link_el["href"].split("?")[0] # Remove tracking params

                    full_title = f"{job_title} — {company} ({location})"
                    process_item(full_title, f"Private Direct ({company})", clean_link)
        except Exception as e:
            print(f"Private Job Scrape Warning ({item['role']}): {e}")

if __name__ == "__main__":
    print("🚀 Starting Complete Civil Engineering Job Radar...")
    run_direct_scrapers()
    run_verified_feeds()
    run_private_mnc_jobs()
    print("✅ Scan Complete!")
