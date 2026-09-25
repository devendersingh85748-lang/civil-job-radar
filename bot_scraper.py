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

# ==========================================
# 1. STRICT NON-CIVIL & OLD JUNK BLOCKER
# ==========================================
STRICT_BLOCK_LIST = [
    "civil services", "civil service", "civil judge", "civil court", "civil surgeon", "civil defence",
    "unfair means", "act, 20", "jharkhand act", "answer key", "rejection list", "exam_files.php",
    "debar", "tender", "quotation", "corrigendum", "archive", "recent examination", "no record found",
    "staff nurse", "nursing", "medical officer", "pharmacist", "constable", "stenographer",
    "typist", "ayurvedic", "homeopathic", "veterinary", "driver", "peon", "tgt ", "pgt ",
    "chsl", "mts ", "gd constable", "sub-inspector", "excise", "lady supervisor", "tet ",
    "ntpc graduate", "ntpc undergraduate", "alp ", "technician", "group d", "paramedical",
    "2019", "2020", "2021", "2022", "2023", "2024", "2025",
    "-01-2026", "-02-2026", "-03-2026", "-04-2026", "-05-2026", "-06-2026", "-07-2026"
]

def has_word(text: str, phrases: list) -> bool:
    for p in phrases:
        if re.search(r'\b' + re.escape(p) + r'\b', text):
            return True
    return False

# ==========================================
# 2. MASTER 4-SECTION CLASSIFIER (JOBS, EXAM DATES, ADMIT CARDS)
# ==========================================
def analyze_job_card(title: str, source: str):
    t = title.lower().strip()

    if len(t) < 18 or any(bad in t for bad in STRICT_BLOCK_LIST):
        return None

    is_private = any(x in source.lower() for x in ["private", "mnc", "epc"])

    # Extract dates if present
    date_pattern = r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})'
    found_dates = re.findall(date_pattern, title, re.IGNORECASE)
    today_str = datetime.now().strftime("%d %b %Y")
    start_date = found_dates[0] if len(found_dates) >= 2 else today_str
    end_date = found_dates[-1] if len(found_dates) >= 1 else "Check Official Notice"

    civil_exam_targets = [
        "junior engineer", "je", "jdlcce", "ssc je", "rrb je", "cen 03/",
        "assistant engineer", "ae", "civil", "polytechnic", "lecturer",
        "engineering services", "gate", "ese", "dfccil", "dmrc", "btsc", "jpsc", "jssc"
    ]

    # ------------------------------------------
    # A. CHECK FOR ADMIT CARD / HALL TICKET
    # ------------------------------------------
    admit_triggers = [
        "admit card", "hall ticket", "e-admit card", "call letter", "city intimation"
    ]
    if not is_private and any(trig in t for trig in admit_triggers) and has_word(t, civil_exam_targets):
        dip = has_word(t, ["je", "junior engineer", "jdlcce", "ssc je", "rrb je", "cen 03/", "diploma"])
        mtech = has_word(t, ["lecturer", "polytechnic", "gate", "ese", "scientist", "assistant professor"])
        btech = True
        if not dip and not mtech:
            dip = True

        header = "🩵 【 🎫 ADMIT CARD / HALL TICKET OUT 】"
        qual_code = f"{'D' if dip else ''}{'B' if btech else ''}{'M' if mtech else ''}"
        packed_category = f"ADMIT_CARD|{header}|{qual_code}|{start_date}|{end_date}"

        return {
            "header": header,
            "d_badge": "✅ <b>DIPLOMA</b>" if dip else "⬜ Diploma",
            "b_badge": "✅ <b>B.TECH</b>" if btech else "⬜ B.Tech",
            "m_badge": "✅ <b>M.TECH</b>" if mtech else "⬜ M.Tech",
            "start_date": start_date,
            "end_date": end_date,
            "packed_category": packed_category,
            "sector": "🎫 Admit Card Alert"
        }

    # ------------------------------------------
    # B. CHECK FOR UPCOMING EXAM DATES / SCHEDULE
    # ------------------------------------------
    exam_date_triggers = [
        "exam date", "examination date", "date of examination",
        "exam schedule", "examination schedule", "exam calendar",
        "examination calendar", "tentative schedule", "cbt date",
        "schedule of examination", "cbt-1", "cbt 1", "paper-i", "paper-ii"
    ]
    if not is_private and any(trig in t for trig in exam_date_triggers) and has_word(t, civil_exam_targets):
        dip = has_word(t, ["je", "junior engineer", "jdlcce", "ssc je", "rrb je", "cen 03/", "diploma"])
        mtech = has_word(t, ["lecturer", "polytechnic", "gate", "ese", "scientist", "assistant professor"])
        btech = True
        if not dip and not mtech:
            dip = True

        header = "🟧 【 📅 UPCOMING EXAM DATE / SCHEDULE 】"
        qual_code = f"{'D' if dip else ''}{'B' if btech else ''}{'M' if mtech else ''}"
        packed_category = f"EXAM_DATE|{header}|{qual_code}|{start_date}|{end_date}"

        return {
            "header": header,
            "d_badge": "✅ <b>DIPLOMA</b>" if dip else "⬜ Diploma",
            "b_badge": "✅ <b>B.TECH</b>" if btech else "⬜ B.Tech",
            "m_badge": "✅ <b>M.TECH</b>" if mtech else "⬜ M.Tech",
            "start_date": start_date,
            "end_date": end_date,
            "packed_category": packed_category,
            "sector": "📅 Upcoming Exam Schedule"
        }

    # Block non-job notices if not Admit Card or Exam Date
    non_job_notices = ["result", "merit list", "interview", "document verification", "syllabus", "press release", "cutoff", "score card"]
    if any(nj in t for nj in non_job_notices):
        return None

    # ------------------------------------------
    # C. CHECK FOR NEW RECRUITMENT / VACANCIES
    # ------------------------------------------
    if not is_private:
        recruitment_signals = [
            "recruitment", "advt", "advertisement", "vacancy", "vacancies",
            "notification", "apply online", "online application", "jdlcce",
            "ssc je", "rrb je", "employment notice", "walk-in", "engagement of", "cen "
        ]
        if not any(sig in t for sig in recruitment_signals):
            return None

    dip, btech, mtech = False, False, False
    header = ""
    short_cat = ""

    mtech_roles = [
        "polytechnic lecturer", "lecturer in civil", "lecturer", "assistant professor", "faculty",
        "scientist", "project scientist", "structural engineer", "structural design",
        "geotechnical engineer", "bridge design", "transportation engineer",
        "water resources", "bim engineer", "bim modeler", "research associate", "srf", "jrf"
    ]
    je_roles = [
        "junior engineer", "je civil", "je (civil)", "jdlcce", "ssc je", "rrb je",
        "diploma trainee", "diploma engineer", "site supervisor", "draughtsman civil", "overseer"
    ]
    ae_btech_roles = [
        "assistant engineer", "ae civil", "ae (civil)", "sub divisional officer",
        "executive engineer", "executive trainee", "graduate engineer trainee",
        "site engineer", "billing engineer", "planning engineer", "quantity surveyor",
        "highway engineer", "qa/qc engineer", "project engineer", "contracts engineer",
        "civil engineer", "civil engineering"
    ]

    if has_word(t, mtech_roles):
        mtech, btech = True, True
        if any(w in t for w in ["lecturer", "professor", "faculty", "polytechnic"]):
            header = "🟪 【 🎓 LECTURER / ACADEMIC FACULTY 】"
        elif any(w in t for w in ["scientist", "srf", "jrf", "research"]):
            header = "🟪 【 🔬 SCIENTIST / R&D PROJECT 】"
        else:
            header = "🟪 【 📐 M.TECH SPECIALIST / DESIGN 】"
        short_cat = "M.Tech"

    elif has_word(t, je_roles):
        dip, btech = True, True
        header = "🟨 【 👷 JUNIOR ENGINEER (JE) / DIPLOMA 】"
        short_cat = "Diploma"

    elif has_word(t, ae_btech_roles):
        btech = True
        if any(w in t for w in ["assistant engineer", "ae civil", "ae (civil)", "executive trainee", "sub divisional"]):
            header = "🟦 【 🏛️ ASSISTANT ENGINEER (AE) / PSU 】"
            mtech = True
        elif is_private or any(w in t for w in ["site engineer", "billing", "planning", "quantity surveyor", "qa/qc"]):
            header = "🟧 【 🏗️ MNC SITE / BILLING / PLANNING 】"
            dip = True
        else:
            header = "🟦 【 🏛️ B.TECH CIVIL RECRUITMENT 】"
        short_cat = "B.Tech"

    # ------------------------------------------
    # D. ZERO-MISS CATCHER FOR VAGUE GOVT "ADVT NO."
    # ------------------------------------------
    elif not is_private and any(v in t for v in ["advt. no", "advt no", "advertisement no", "employment notice no"]):
        dip, btech, mtech = True, True, True
        header = "🟨 【 🔔 NEW OFFICIAL ADVT (CHECK PDF) 】"
        short_cat = "B.Tech"
    else:
        return None

    d_badge = "✅ <b>DIPLOMA</b>" if dip else "⬜ Diploma"
    b_badge = "✅ <b>B.TECH</b>" if btech else "⬜ B.Tech"
    m_badge = "✅ <b>M.TECH</b>" if mtech else "⬜ M.Tech"

    qual_code = f"{'D' if dip else ''}{'B' if btech else ''}{'M' if mtech else ''}"
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
# 3. TELEGRAM RICH CARD SENDER
# ==========================================
def send_telegram_card(title, source, link, info):
    if not TELEGRAM_TOKEN:
        return

    safe_title = html.escape(title)
    safe_source = html.escape(source)
    cat_str = info["packed_category"]

    if cat_str.startswith("ADMIT_CARD"):
        date_label_1 = "🟢 <b>Notice Date:</b>"
        date_label_2 = "🎫 <b>Status:</b>"
        btn_label = "🎫 Download Admit Card / Hall Ticket ↗"
    elif cat_str.startswith("EXAM_DATE"):
        date_label_1 = "🟢 <b>Notice Date:</b>"
        date_label_2 = "📅 <b>Exam Schedule:</b>"
        btn_label = "📅 View Exam Date Notice ↗"
    else:
        date_label_1 = "🟢 <b>Notification Date:</b>"
        date_label_2 = "🔴 <b>Last Date:</b>"
        btn_label = "📄 View Official Notification / Apply ↗"

    card_text = (
        f"<b>{info['header']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>Notice:</b> {safe_title}\n"
        f"🏢 <b>Organization:</b> <code>{safe_source}</code> ({info['sector']})\n\n"
        f"🎓 <b>TARGET QUALIFICATION:</b>\n"
        f"{info['d_badge']}  |  {info['b_badge']}  |  {info['m_badge']}\n\n"
        f"📅 <b>IMPORTANT DATES:</b>\n"
        f"{date_label_1} {info['start_date']}\n"
        f"{date_label_2} {info['end_date']}\n"
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
                {"text": btn_label, "url": link}
            ]]
        }
    }
    try:
        requests.post(url, json=payload, timeout=10)
        time.sleep(1)
    except Exception as e:
        print(f"Telegram Error: {e}")

def process_item(title, source, link):
    if not title or not link or "exam_files.php" in link:
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
                print(f"[NEW UPDATE] {info['header']} -> {title}")
                send_telegram_card(title, source, link, info)
    except Exception as e:
        print(f"Database Warning: {e}")

# ==========================================
# 4. OFFICIAL GOVT, RRB, EXAM DATE & MNC SCRAPERS
# ==========================================
DIRECT_PORTALS = [
    {"name": "RRB Railways Official", "url": "https://www.rrbcdg.gov.in/", "base": "https://www.rrbcdg.gov.in"},
    {"name": "UPSC Official", "url": "https://upsc.gov.in/whats-new", "base": "https://upsc.gov.in"},
    {"name": "JSSC Jharkhand", "url": "https://jssc.jharkhand.gov.in/notices", "base": "https://jssc.jharkhand.gov.in"},
    {"name": "JPSC Jharkhand", "url": "https://www.jpsc.gov.in/", "base": "https://www.jpsc.gov.in"},
    {"name": "BTSC Bihar (JE/AE)", "url": "https://btsc.bihar.gov.in/latest-update", "base": "https://btsc.bihar.gov.in"},
    {"name": "UPPSC UP", "url": "https://uppsc.up.nic.in/CandidatePages/Notifications.aspx", "base": "https://uppsc.up.nic.in"},
    {"name": "DSSSB Delhi", "url": "https://dsssb.delhi.gov.in/vacancy-advertisements", "base": "https://dsssb.delhi.gov.in"},
    {"name": "DMRC Delhi Metro", "url": "https://www.delhimetrorail.com/pages/en/career", "base": "https://www.delhimetrorail.com"},
    {"name": "NCRTC (RRTS Metro)", "url": "https://ncrtc.in/jobs/", "base": "https://ncrtc.in"},
    {"name": "DFCCIL Railways", "url": "https://dfccil.com/Home/AllActiveCareer", "base": "https://dfccil.com"},
    {"name": "RITES Ltd", "url": "https://www.rites.com/Career", "base": "https://www.rites.com"},
    {"name": "CSIR-CBRI Roorkee", "url": "https://cbri.res.in/careers/", "base": "https://cbri.res.in"},
    {"name": "CSIR-CRRI Delhi", "url": "https://crridom.gov.in/recruitment", "base": "https://crridom.gov.in"}
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
        "source": "Exam Date Radar (SSC / RRB / State AE-JE)",
        "query": '("SSC JE" OR "RRB JE" OR "JSSC JE" OR "JPSC AE" OR "BPSC AE" OR "UPPSC AE" OR "BTSC JE" OR "Polytechnic Lecturer" OR "DFCCIL") ("Exam Date" OR "Exam Schedule" OR "CBT Date" OR "Examination Calendar")'
    },
    {
        "source": "Admit Card Radar (SSC / RRB / State AE-JE)",
        "query": '("SSC JE" OR "RRB JE" OR "JSSC JE" OR "JPSC" OR "BPSC" OR "UPPSC" OR "BTSC JE") ("Admit Card" OR "Hall Ticket" OR "City Intimation" OR "Call Letter")'
    },
    {
        "source": "Central & PSU Civil Recruitment",
        "query": '("SSC JE" OR "RRB JE" OR "NBCC" OR "NHAI" OR "NTPC" OR "PGCIL" OR "RITES" OR "RVNL" OR "IRCON") ("Civil Engineer" OR "Junior Engineer" OR "Assistant Engineer" OR "Executive Trainee") ("Recruitment" OR "Notification" OR "Vacancy")'
    }
]

def run_verified_feeds():
    for feed in VERIFIED_SEARCH_FEEDS:
        try:
            encoded_query = requests.utils.quote(f"{feed['query']} when:30d")
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:12]:
                title = item.find("title").text
                link = item.find("link").text
                process_item(title, feed["source"], link)
        except Exception as e:
            print(f"Feed Warning ({feed['source']}): {e}")

PRIVATE_ROLES = [
    {"role": "Civil Structural Design Engineer", "loc": "India"},
    {"role": "Civil Billing Planning Engineer", "loc": "India"},
    {"role": "Civil Site Engineer", "loc": "Gurugram"},
    {"role": "Bridge Highway Design Engineer", "loc": "India"},
    {"role": "Geotechnical Engineer", "loc": "India"},
    {"role": "Civil Engineering Lecturer", "loc": "India"}
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
            for card in soup.find_all("div", class_="base-card")[:6]:
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
                    process_item(full_title, f"Private MNC ({company})", clean_link)
        except Exception as e:
            print(f"Private Job Scrape Warning ({item['role']}): {e}")

if __name__ == "__main__":
    print("🚀 Starting 4-Section Master Civil Job, Exam Date & Admit Card Radar...")
    run_direct_scrapers()
    run_verified_feeds()
    run_private_mnc_jobs()
    print("✅ Scan Complete!")
