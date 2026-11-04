"""Builds the VANET AAT report (.docx) in the layout of the reference report.

Usage: python build_report.py PROJECT_DIR FIG_DIR LOGO OUT.docx [pages.json]
pages.json (optional) maps TOC keys to page numbers, found from a first render.
"""
import csv
import json
import os
import re
import sys

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Inches, Cm, RGBColor

PROJ, FIGS, LOGO, OUT = sys.argv[1:5]
PAGES = json.load(open(sys.argv[5])) if len(sys.argv) > 5 else {}
FONT = "Times New Roman"
TEXT_W = 6.27  # inches, A4 with 1 inch margins


def read(path):
    with open(os.path.join(PROJ, path), newline="") as f:
        return list(csv.DictReader(f))


S = {(r["experiment"], float(r["x"])): r for r in read("results/summary.csv")}
S2 = {(r["experiment"], float(r["x"])): r for r in read("results/plots2/summary.csv")}
O = {r["experiment"]: r for r in read("results/optimal/summary.csv")}
ORUNS = read("results/optimal/all_runs.csv")
ALLRUNS = read("results/all_runs.csv") + read("results/plots2/all_runs.csv") + ORUNS
MAXDEV = max(abs(float(r["pdr"]) + float(r["lossRate"]) - 100) for r in ALLRUNS)


def f1(x):
    return f"{float(x):.1f}"


def f2(x):
    return f"{float(x):.2f}"


# --------------------------------------------------------------------------- document setup
doc = Document()
st = doc.styles["Normal"]
st.font.name = FONT
st.font.size = Pt(12)
st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
st.paragraph_format.space_after = Pt(6)
st.paragraph_format.line_spacing = 1.5
for name in ("List Bullet", "List Number"):
    s = doc.styles[name]
    s.font.name = FONT
    s.font.size = Pt(12)
    s.paragraph_format.line_spacing = 1.5
    s.paragraph_format.space_after = Pt(3)

sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
    setattr(sec, side, Inches(1))

TAG = re.compile(r"(<b>|</b>|<i>|</i>|<sub>|</sub>|<sup>|</sup>|<c>|</c>)")


def runs(p, text, size=None, bold=False, italic=False, font=None):
    """Add text with inline <b>, <i>, <sub>, <sup>, <c> (code) markup."""
    state = {"b": bold, "i": italic, "sub": False, "sup": False, "c": False}
    for part in TAG.split(text):
        if not part:
            continue
        m = re.fullmatch(r"<(/?)(b|i|sub|sup|c)>", part)
        if m:
            state[m.group(2)] = not m.group(1)
            continue
        r = p.add_run(part)
        r.bold = state["b"]
        r.italic = state["i"]
        r.font.subscript = state["sub"]
        r.font.superscript = state["sup"]
        fn = "Courier New" if state["c"] else (font or FONT)
        r.font.name = fn
        r._element.rPr.rFonts.set(qn("w:eastAsia"), fn)
        if size:
            r.font.size = Pt(size)
        elif state["c"]:
            r.font.size = Pt(10.5)
    return p


def para(text, align=WD_ALIGN_PARAGRAPH.JUSTIFY, size=None, bold=False, italic=False, after=6, before=0,
         spacing=1.5, keep=False, indent=None, style=None):
    p = doc.add_paragraph(style=style)
    p.alignment = align
    pf = p.paragraph_format
    pf.space_after = Pt(after)
    pf.space_before = Pt(before)
    pf.line_spacing = spacing
    pf.keep_with_next = keep
    if indent is not None:
        pf.left_indent = Inches(indent)
    runs(p, text, size=size, bold=bold, italic=italic)
    return p


def bullet(text):
    p = doc.add_paragraph(style="List Bullet")
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    runs(p, text)
    return p


def numbered(items):
    for i, t in enumerate(items, 1):
        p = para(f"{i}. " + t, after=4)
        p.paragraph_format.left_indent = Inches(0.3)
        p.paragraph_format.first_line_indent = Inches(-0.3)


def chapter(n, title):
    p = para(f"CHAPTER {n}", align=WD_ALIGN_PARAGRAPH.CENTER, size=14, bold=True, after=0, keep=True)
    p.paragraph_format.page_break_before = True
    para(title.upper(), align=WD_ALIGN_PARAGRAPH.CENTER, size=16, bold=True, after=10, keep=True)


def section(title):
    para(title, align=WD_ALIGN_PARAGRAPH.LEFT, size=13, bold=True, before=8, after=4, keep=True)


def subhead(title):
    para(title, align=WD_ALIGN_PARAGRAPH.LEFT, bold=True, before=4, after=2, keep=True)


FIGN = [0]
TABN = [0]
FIGLIST = []
TABLIST = []


def figure(fname, caption, width=6.0, folder=None):
    FIGN[0] += 1
    path = os.path.join(folder or FIGS, fname)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.line_spacing = 1.0
    p.add_run().add_picture(path, width=Inches(width))
    para(f"Fig. {FIGN[0]}. {caption}", align=WD_ALIGN_PARAGRAPH.CENTER, size=11, italic=True, after=10,
         spacing=1.15)
    FIGLIST.append((f"Fig. {FIGN[0]}", caption))


def shade(cell, color="D9D9D9"):
    tcPr = cell._element.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:color"), "auto")
    sh.set(qn("w:fill"), color)
    tcPr.append(sh)


def table(caption, header, rows, widths, size=10, align=None, bold_first=False):
    TABN[0] += 1
    para(f"Table {TABN[0]}. {caption}", align=WD_ALIGN_PARAGRAPH.CENTER, size=11, bold=True, after=3,
         before=6, spacing=1.0, keep=True)
    TABLIST.append((f"Table {TABN[0]}", caption))
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    align = align or ["L"] + ["C"] * (len(header) - 1)
    for ri, row in enumerate([header] + rows):
        tr = t.rows[ri]
        trPr = tr._tr.get_or_add_trPr()
        cs = OxmlElement("w:cantSplit")
        trPr.append(cs)
        if ri == 0:
            th = OxmlElement("w:tblHeader")
            trPr.append(th)
        for ci, val in enumerate(row):
            c = tr.cells[ci]
            c.width = Inches(widths[ci])
            c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.line_spacing = 1.0
            if ri == 0:
                shade(c)
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                runs(p, str(val), size=size, bold=True)
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER if align[ci] == "C" else WD_ALIGN_PARAGRAPH.LEFT
                runs(p, str(val), size=size, bold=bold_first and ci == 0)
            if ri < len(rows):
                p.paragraph_format.keep_with_next = True
    for ci, w in enumerate(widths):
        t.columns[ci].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def code(lines, title=None):
    if title:
        para(title, align=WD_ALIGN_PARAGRAPH.LEFT, bold=True, after=2, before=4, keep=True)
    for i, ln in enumerate(lines):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_after = Pt(0)
        pf.space_before = Pt(0)
        pf.line_spacing = 1.0
        pf.left_indent = Inches(0.25)
        pf.keep_with_next = i < len(lines) - 1
        r = p.add_run(ln if ln else " ")
        r.font.name = "Courier New"
        r._element.rPr.rFonts.set(qn("w:eastAsia"), "Courier New")
        r.font.size = Pt(9.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


EQN = [0]


def eq(text):
    EQN[0] += 1
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.tab_stops.add_tab_stop(Inches(TEXT_W / 2), WD_TAB_ALIGNMENT.CENTER)
    pf.tab_stops.add_tab_stop(Inches(TEXT_W), WD_TAB_ALIGNMENT.RIGHT)
    pf.space_after = Pt(4)
    pf.line_spacing = 1.3
    runs(p, "\t" + text + f"\t({EQN[0]})")
    return EQN[0]


def page_break():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def border_section(s):
    sectPr = s._sectPr
    pb = OxmlElement("w:pgBorders")
    pb.set(qn("w:offsetFrom"), "page")
    for side in ("top", "left", "bottom", "right"):
        e = OxmlElement(f"w:{side}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), "12")
        e.set(qn("w:space"), "24")
        e.set(qn("w:color"), "000000")
        pb.append(e)
    sectPr.append(pb)


def page_number_footer(s, start):
    s.footer.is_linked_to_previous = False
    p = s.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run()
    for tag, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        if tag:
            fc = OxmlElement("w:fldChar")
            fc.set(qn("w:fldCharType"), tag)
            r._r.append(fc)
        else:
            it = OxmlElement("w:instrText")
            it.set(qn("xml:space"), "preserve")
            it.text = txt
            r._r.append(it)
    r.font.name = FONT
    r.font.size = Pt(11)
    pg = OxmlElement("w:pgNumType")
    pg.set(qn("w:start"), str(start))
    s._sectPr.append(pg)


# --------------------------------------------------------------------------- team
TEAM = [("Zain Mahedi", "1WA23CS056"), ("Thanish A Shetty", "1WA23CS017"),
        ("Vaibhav S Keerthi", "1WA23CS028"), ("Vikas Shashi", "1WA23CS043")]
TITLE = "Performance Analysis of VANETs for Traffic Efficiency and Road Traffic Safety Using NS-3"
GUIDE, GUIDE_ROLE, HOD = "Dr. K. Panimozhi", "Associate Professor", "Dr. Kavitha Sooda"

# --------------------------------------------------------------------------- cover page
border_section(sec)
para("B.M.S. COLLEGE OF ENGINEERING", align=WD_ALIGN_PARAGRAPH.CENTER, size=20, bold=True, after=2, before=12)
para("(Autonomous Institute, Affiliated to VTU)", align=WD_ALIGN_PARAGRAPH.CENTER, size=14, bold=True,
     after=0, spacing=1.2)
para("Bull Temple Road, Basavanagudi, Bengaluru - 560019", align=WD_ALIGN_PARAGRAPH.CENTER, size=14, bold=True,
     after=8, spacing=1.2)
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run().add_picture(LOGO, width=Inches(1.15))
para("Presentation Report under Alternate Assessment Tool (AAT)", align=WD_ALIGN_PARAGRAPH.CENTER, after=0)
para("Course: Network Programming", align=WD_ALIGN_PARAGRAPH.CENTER, after=6)
para(TITLE, align=WD_ALIGN_PARAGRAPH.CENTER, size=16, bold=True, italic=True, after=8, spacing=1.2)
para("Submitted in partial fulfilment of the requirements for the award of degree",
     align=WD_ALIGN_PARAGRAPH.CENTER, after=2)
for t in ("BACHELOR OF ENGINEERING", "IN", "COMPUTER SCIENCE AND ENGINEERING"):
    para(t, align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, after=0)
para("By", align=WD_ALIGN_PARAGRAPH.CENTER, before=6, after=0)
for name, usn in TEAM:
    p = doc.add_paragraph()
    p.paragraph_format.tab_stops.add_tab_stop(Inches(1.2), WD_TAB_ALIGNMENT.LEFT)
    p.paragraph_format.tab_stops.add_tab_stop(Inches(3.6), WD_TAB_ALIGNMENT.LEFT)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.15
    runs(p, f"\t{name}\t{usn}")
para("Under the guidance of", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, before=10, after=0)
para(GUIDE, align=WD_ALIGN_PARAGRAPH.CENTER, size=13, bold=True, after=0)
para(GUIDE_ROLE, align=WD_ALIGN_PARAGRAPH.CENTER, after=8)
para("Department of Computer Science and Engineering", align=WD_ALIGN_PARAGRAPH.CENTER, size=16, bold=True,
     after=0)
para("2026-2027", align=WD_ALIGN_PARAGRAPH.CENTER, size=15, bold=True, after=0)

# --------------------------------------------------------------------------- certificate
s2 = doc.add_section(WD_SECTION.NEW_PAGE)
s2._sectPr.remove(s2._sectPr.find(qn("w:pgBorders")))
hdr = doc.add_table(rows=1, cols=2)
hdr.autofit = False
hdr.columns[0].width = Inches(1.2)
hdr.columns[1].width = Inches(5.0)
c0, c1 = hdr.rows[0].cells
c0.width, c1.width = Inches(1.2), Inches(5.0)
c0.paragraphs[0].add_run().add_picture(LOGO, width=Inches(0.85))
c1.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
for i, (t, sz) in enumerate((("B.M.S. COLLEGE OF ENGINEERING", 12), ("( Autonomous Institute, Affiliated to VTU )", 10),
                             ("Bull Temple Road, Basavanagudi,", 10), ("Bengaluru - 560019", 10))):
    pp = c1.paragraphs[0] if i == 0 else c1.add_paragraph()
    pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pp.paragraph_format.space_after = Pt(1)
    pp.paragraph_format.line_spacing = 1.0
    runs(pp, t, size=sz, bold=True)
para("", after=6)
para("Department of Computer Science and Engineering", align=WD_ALIGN_PARAGRAPH.CENTER, size=14, bold=True,
     after=10)
para("C E R T I F I C A T E", align=WD_ALIGN_PARAGRAPH.CENTER, size=14, bold=True, after=10)
names = ", ".join(f"<b>{n} ({u})</b>" for n, u in TEAM)
para(f"This is to certify that the Presentation Report under Alternate Assessment Tool entitled "
     f"“<b><i>{TITLE}</i></b>” is a bona-fide work carried out by {names} in partial fulfilment for the "
     f"award of degree of Bachelor of Engineering in <b>Computer Science and Engineering</b> from "
     f"<b>Visvesvaraya Technological University, Belagavi</b> during the year <b>2026-2027</b>. It is certified "
     f"that all corrections/suggestions indicated for Internal Assessments have been incorporated in the report "
     f"deposited in the departmental library. The Presentation Report has been approved as it satisfies the "
     f"academic requirements in respect of AAT prescribed for the Bachelor of Engineering Degree.", size=11,
     spacing=1.3)
for _ in range(7):
    para("", after=6)
p = doc.add_paragraph()
p.paragraph_format.tab_stops.add_tab_stop(Inches(TEXT_W), WD_TAB_ALIGNMENT.RIGHT)
p.paragraph_format.line_spacing = 1.0
p.paragraph_format.space_after = Pt(0)
runs(p, f"{GUIDE}\t{HOD}", size=11, bold=True)
p = doc.add_paragraph()
p.paragraph_format.tab_stops.add_tab_stop(Inches(TEXT_W), WD_TAB_ALIGNMENT.RIGHT)
p.paragraph_format.line_spacing = 1.0
runs(p, "Course Coordinator\tProfessor and HOD", size=11, bold=True)

# --------------------------------------------------------------------------- table of contents
s3 = doc.add_section(WD_SECTION.NEW_PAGE)
page_number_footer(s3, 3)
s2.footer.is_linked_to_previous = False

CHAPTERS = [
    ("Abstract", []), ("Objectives", []), ("Introduction", []), ("Literature review", []), ("Research gap", []),
    ("Problem statement", []),
    ("Methodology / implementation", ["7.1 Proposed Architecture", "7.2 Mathematical Model",
                                      "7.3 Network Communication Model", "7.4 Proposed Algorithm",
                                      "7.5 Socket Programming Implementation"]),
    ("Performance evaluation", ["8.1 Experimental Setup", "8.2 Performance Metrics",
                                "8.3 Experiments and Procedure", "8.4 Fairness and Validity of the Comparison"]),
    ("Output and results", ["9.1 Comparative Analysis", "9.2 Validation of the Approach",
                            "9.3 Visualisation of the Sweeps", "9.4 Final Optimal Solution", "9.5 Observations"]),
    ("Conclusion", []), ("References", []),
]


def toc_line(left, title, key, bold=False, sub=False):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(0)
    pf.line_spacing = 1.15
    pf.tab_stops.add_tab_stop(Inches(0.95 if not sub else 1.3), WD_TAB_ALIGNMENT.LEFT)
    pf.tab_stops.add_tab_stop(Inches(TEXT_W), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
    if sub:
        pf.left_indent = Inches(0.4)
        pf.first_line_indent = Inches(0)
    runs(p, f"{left}\t{title}\t{PAGES.get(key, '0')}", size=11 if not sub else 10.5, bold=bold)


para("TABLE OF CONTENTS", align=WD_ALIGN_PARAGRAPH.CENTER, size=13, bold=True, after=6)
for i, (name, subs) in enumerate(CHAPTERS, 1):
    toc_line(f"Chapter {i}", name, f"ch{i}", bold=True)
    for s_ in subs:
        num, title = s_.split(" ", 1)
        toc_line(num, title, num, sub=True)

# placeholders for figure/table lists are filled after the body is built (titles known only then)
toc_fig_anchor = para("LIST OF FIGURES", align=WD_ALIGN_PARAGRAPH.LEFT, size=12, bold=True, before=10, after=3)
toc_tab_anchor = para("LIST OF TABLES", align=WD_ALIGN_PARAGRAPH.LEFT, size=12, bold=True, before=10, after=3)

# =========================================================================== CHAPTER 1
b, o = O["baseline"], O["optimal"]
est = float(S[("density", 60.0)]["pdr_mean"])
for e, x in (("range", 250.0), ("speed", 10.0), ("load", 50.0), ("density", 80.0)):
    est *= float(S[(e, x)]["pdr_mean"]) / float(S[("density", 60.0)]["pdr_mean"])
EST = est

chapter(1, "Abstract")
para("Vehicular ad hoc networks (VANETs) let cars exchange safety and traffic messages directly with each other, "
     "without a base station. Whether these messages arrive depends on how many vehicles are on the road, how fast "
     "they drive, how much data they send and how far their radios reach. This project measures these four effects "
     "with the NS-3 network simulator (ns-3.48). We built a 2 km, four-lane highway on which vehicles drive in both "
     "directions, route with AODV over an IEEE 802.11p radio and exchange ten constant-rate UDP flows for 100 "
     "seconds. Starting from a baseline of 60 vehicles, 20 m/s, 100 kbit/s per flow and a 150 m range, we varied "
     "one factor at a time and ran every test point with five random seeds (95 runs), measuring packet delivery "
     "ratio (PDR), end-to-end delay, throughput and packet loss with FlowMonitor. Communication range had the "
     f"strongest effect (PDR {f1(S[('range', 50.0)]['pdr_mean'])}% at 50 m to {f1(S[('range', 250.0)]['pdr_mean'])}% "
     f"at 250 m), followed by speed ({f1(S[('speed', 10.0)]['pdr_mean'])}% at 10 m/s to "
     f"{f1(S[('speed', 25.0)]['pdr_mean'])}% at 25 m/s) and load ({f1(S[('load', 50.0)]['pdr_mean'])}% at 50 kbit/s "
     f"to {f1(S[('load', 750.0)]['pdr_mean'])}% at 750 kbit/s). Density helped only up to 60–80 vehicles. A second "
     "variation with a different baseline and eight seeds (200 runs) confirmed the trends. Finally we simulated the "
     "combination of the best value of every factor (80 vehicles, 10 m/s, 50 kbit/s, 250 m). Over ten seeds it "
     f"raised PDR from {f1(b['pdr_mean'])}% to {f1(o['pdr_mean'])}% and cut the delay from {f1(b['delayMs_mean'])} ms "
     f"to {f1(o['delayMs_mean'])} ms, but it stayed well below the {EST:.0f}% that a simple multiplication of the "
     "single-factor gains predicts, because the factors interact.")

# =========================================================================== CHAPTER 2
chapter(2, "Objectives")
para("The aims of this assessment were:")
for t in [
    "To understand socket programming basics as used in NS-3: UDP senders and receivers, binding to ports and a "
    "callback that runs every time a packet arrives.",
    "To build a highway VANET in NS-3 in which vehicles move in both directions, route with AODV over an IEEE "
    "802.11p radio and exchange UDP traffic.",
    "To measure packet delivery ratio, end-to-end delay, throughput and packet loss rate for the data traffic, "
    "excluding the AODV control traffic.",
    "To study the effect of vehicle density, vehicle speed, traffic load and communication range one at a time, "
    "with several random seeds and error bars.",
    "To check that the results are correct and repeatable: fix bugs found on the way, repeat runs and confirm the "
    "trends with a second, independent parameter variation.",
    "To visualise what happens inside a run (vehicle positions, data hops, route discovery and route errors) with "
    "packet-level traces, animations and NetAnim.",
    "To find the best value of each factor, measure the combined optimal configuration in the simulator and check "
    "how much each factor contributes to it.",
]:
    bullet(t)

# =========================================================================== CHAPTER 3
chapter(3, "Introduction")
section("3.1 Network Programming and the Application")
para("Network programming means writing programs that run on different devices and send messages to each other. "
     "Our application is communication between vehicles. Cars that can talk to each other can warn the cars behind "
     "them about a sudden brake, an accident or a traffic jam, and can share their speed and position so that "
     "traffic flows more smoothly. These uses fall into two groups: <b>road traffic safety</b> (warnings that must "
     "arrive quickly and reliably) and <b>traffic efficiency</b> (information that helps vehicles choose speed and "
     "route) [2], [3].")
para("Every vehicle carries a small radio and acts as a router for the others, so a message can hop from car to "
     "car until it reaches the destination. Such a network is called a vehicular ad hoc network (VANET). Testing "
     "this on a real road needs many cars and is unsafe, so we used a simulator. A program describes the road, the "
     "vehicles and their radios, and the simulator records exactly what happens to every packet. We follow the "
     "evaluation framework of Malnar and Jevtić [1], which uses NS-3 to measure how a VANET performs as the "
     "conditions change.")
section("3.2 Sockets, Protocols and System Calls")
para("A socket is the standard way for a program to send and receive data. On Linux, a program creates a socket "
     "and uses system calls such as <i>socket()</i>, <i>bind()</i>, <i>sendto()</i> and <i>recvfrom()</i> [22], "
     "[23]. NS-3 has a Socket class that works the same way [24]. In our scenario every sender runs an NS-3 "
     "OnOffApplication. It creates a UDP socket, connects it to the receiver's address and port and calls "
     "<i>Send()</i> at a constant rate. Every receiver runs a PacketSink, which binds a UDP socket to its port and "
     "registers a receive callback that runs whenever a packet arrives.")
para("TCP resends lost data and slows down when the network is busy, which adds delay that a safety warning "
     "cannot afford. UDP sends each packet once without waiting for an acknowledgement. A late warning is useless, "
     "so vehicular messages are normally sent over UDP, and all our data flows use UDP. The routing protocol is "
     "itself a network program: AODV sends its route requests, replies and errors as UDP packets on port 654, "
     "using the same sockets and the same radio channel as the data.")
section("3.3 Vehicular Ad Hoc Networks and IEEE 802.11p")
para("A VANET has no fixed access point. Vehicles move fast, often in opposite directions, so the links between "
     "them last only a few seconds and the topology changes all the time [2], [9]. On a highway the network is "
     "almost one-dimensional: a message must be passed along the road, and a gap between groups of vehicles that is "
     "longer than the radio range splits the network into parts that cannot reach each other [12].")
para("The radio standard for vehicles is IEEE 802.11p, which became part of IEEE 802.11 as the \"outside the "
     "context of a BSS\" (OCB) mode [5], [6]. It works in the 5.9 GHz band with 10 MHz channels, which makes the "
     "symbols longer and more robust to the fast-changing radio channel of moving vehicles. In the United States it "
     "is the basis of Dedicated Short-Range Communications (DSRC) [4]. Recent ns-3 versions no longer include the "
     "<i>wave</i> module that provided the OCB MAC, so we configure the 802.11p physical layer through the "
     "<i>wifi</i> module and use an ad hoc MAC.")
section("3.4 Routing and Quality of Service")
para("We use AODV (Ad hoc On-Demand Distance Vector) routing [7], [8]. AODV looks for a route only when a "
     "vehicle has data to send: it floods a route request (RREQ), the destination answers with a route reply "
     "(RREP) along the reverse path, and when a link on the route breaks a route error (RERR) is sent so that the "
     "source can search again. Hello messages tell each vehicle which neighbours are in range. Route discovery "
     "costs time and channel capacity, and in a VANET it must be repeated often because links break quickly.")
para("Quality of Service (QoS) describes how well the network serves the traffic. We use four measures: "
     "<b>packet delivery ratio</b> (the share of packets that arrive), <b>end-to-end delay</b> (time a packet "
     "takes), <b>throughput</b> (data delivered per second) and <b>packet loss rate</b> (the share that never "
     "arrives). Safety applications in particular need a high delivery ratio and a delay of the order of 100 ms "
     "or less [3], [4].")
section("3.5 Tools and Languages Used")
for t in [
    "NS-3 (version 3.48), a discrete-event network simulator written in C++ [20], built on macOS. The scenario "
    "was first written for ns-3.45 and runs unchanged on ns-3.48.",
    "C++ for the simulation program <i>vanet-highway.cc</i>, using the ns-3 wifi, aodv, internet, mobility, "
    "applications, flow-monitor and netanim modules [24].",
    "FlowMonitor, an NS-3 tool that records packets sent, packets received and delay for every flow [21].",
    "Bash for the experiment runners (<i>run_experiments.sh</i>, <i>make_animations.sh</i>), which run the "
    "simulations in parallel with xargs.",
    "Python 3 with numpy and matplotlib for merging the results, computing mean and standard deviation and "
    "drawing graphs (<i>plot_results.py</i>) and for animating traced runs (<i>animate_trace.py</i>, "
    "<i>animate_sweep.py</i>).",
    "NetAnim 3.110, the ns-3 animator, for viewing individual runs, and git for version control.",
]:
    bullet(t)

# =========================================================================== CHAPTER 4
chapter(4, "Literature review")
para("We studied twenty-one refereed papers, standards and book chapters (IEEE, ACM, Springer and other refereed "
     "venues) on vehicular networking, routing, mobility, medium access and simulation. They are grouped by theme "
     "below and summarised in Table 1.")
para("<b>Evaluation framework.</b> Malnar and Jevtić propose a framework for evaluating VANETs in NS-3: a road "
     "scenario, a routing protocol and a set of metrics (delivery ratio, delay, throughput) measured while one "
     "condition at a time is changed [1]. Our study follows this approach.")
para("<b>Vehicular networks and standards.</b> Hartenstein and Laberteaux give a tutorial survey of VANETs and "
     "their safety and efficiency applications [2]. Karagiannis et al. review requirements, architectures and "
     "standards, including the delay needs of safety applications [3]. Kenney describes the DSRC standards in the "
     "United States [4], and Jiang and Delgrossi explain how IEEE 802.11p adapts Wi-Fi to vehicles [5]; the "
     "amendment itself is [6].")
para("<b>Routing.</b> Perkins and Royer introduced AODV [7], later standardised as RFC 3561 [8]. Li and Wang "
     "survey routing in VANETs and show that fast topology change is the main difficulty [9]. Broch et al. found "
     "that mobility and load strongly affect ad hoc routing [10]. Ni et al. describe the broadcast storm problem: "
     "flooding in a dense network causes redundant transmissions and collisions [11], which is what happens to RREQ "
     "floods. Wisitpongphan et al. show that sparse highway networks are often disconnected and need "
     "store-carry-forward ideas [12].")
para("<b>Mobility.</b> Härri et al. classify mobility models for VANETs [13], and Camp et al. survey mobility "
     "models for ad hoc networks [25]. Bai et al. show that the mobility pattern, and especially the relative speed "
     "of nodes, changes routing performance [14].")
para("<b>Medium access and capacity.</b> Bianchi's model shows that Wi-Fi throughput is limited by stations "
     "competing and colliding on the channel [15]. Gupta and Kumar show that the capacity per node of a multi-hop "
     "wireless network falls as the network grows [16]. Torrent-Moreno et al. measure how reception in 802.11 "
     "vehicular networks falls with distance and load [17].")
para("<b>Simulation tools.</b> Veins couples a network simulator with the SUMO road traffic simulator [18], [19]. "
     "Riley and Henderson describe ns-3 [20], and Carneiro et al. describe FlowMonitor [21].")
LIT = [
    ("[1]", "Malnar & Jevtić (2020)", "NS-3 framework for VANET performance evaluation", "Framework we follow"),
    ("[2]", "Hartenstein & Laberteaux (2008)", "Tutorial survey of VANETs", "Safety and efficiency uses"),
    ("[3]", "Karagiannis et al. (2011)", "Requirements, architectures, standards", "Delay needs of safety apps"),
    ("[4]", "Kenney (2011)", "DSRC standards in the USA", "Radio band and channel"),
    ("[5]", "Jiang & Delgrossi (2008)", "IEEE 802.11p for vehicles", "PHY we configure"),
    ("[6]", "IEEE 802.11p (2010)", "WAVE amendment to IEEE 802.11", "Standard used"),
    ("[7]", "Perkins & Royer (1999)", "On-demand route discovery (AODV)", "Routing protocol used"),
    ("[8]", "Perkins et al. (2003)", "RFC 3561: AODV specification", "Reference for AODV"),
    ("[9]", "Li & Wang (2007)", "Survey of VANET routing", "Why links break"),
    ("[10]", "Broch et al. (1998)", "Comparison of ad hoc routing protocols", "Mobility and load matter"),
    ("[11]", "Ni et al. (1999)", "Broadcast storm problem", "Cost of RREQ floods"),
    ("[12]", "Wisitpongphan et al. (2007)", "Routing in sparse VANETs", "Disconnection at low density"),
    ("[13]", "Härri et al. (2009)", "VANET mobility models", "Choice of mobility model"),
    ("[14]", "Bai et al. (2003)", "Impact of mobility on routing", "Effect of speed"),
    ("[15]", "Bianchi (2000)", "Model of 802.11 DCF throughput", "Channel saturation"),
    ("[16]", "Gupta & Kumar (2000)", "Capacity of wireless networks", "Multi-hop capacity limit"),
    ("[17]", "Torrent-Moreno et al. (2004)", "Reception rates in 802.11 VANETs", "Effect of load and distance"),
    ("[18]", "Sommer et al. (2011)", "Veins: coupled network and road simulation", "Alternative tool chain"),
    ("[19]", "Krajzewicz et al. (2012)", "SUMO road traffic simulator", "Realistic traffic (future work)"),
    ("[20]", "Riley & Henderson (2010)", "The ns-3 simulator", "Simulation platform"),
    ("[21]", "Carneiro et al. (2009)", "FlowMonitor for ns-3", "Measurement tool used"),
]
table("Summary of the reviewed literature", ["Ref.", "Work (year)", "Main contribution", "Relevance to this work"],
      [list(r) for r in LIT], [0.5, 1.75, 2.15, 1.85], align=["C", "L", "L", "L"])
para("In short, the effects of mobility, density and load on ad hoc routing are well known in general, and NS-3 "
     "offers a framework to measure them. But many studies report single runs, vary one factor without asking "
     "whether the best values work together, and use the older 802.11p (wave) module that is no longer in current "
     "ns-3.")

# =========================================================================== CHAPTER 5
chapter(5, "Research gap")
para("The literature review shows these gaps:")
numbered([
    "<b>Single runs.</b> Many simulation studies report one run per setting. With mobile vehicles the result "
    "depends strongly on where the vehicles start, so a single run can show a trend that is not real.",
    "<b>Factors studied alone.</b> Density, speed, load and range are usually varied one at a time [1], [10]. "
    "Whether the best value of each factor still helps when the others are also at their best is rarely measured; "
    "it is often assumed that the gains simply add up.",
    "<b>Current tools.</b> The ns-3 wave module that provided the 802.11p MAC has been removed, so there are few "
    "open, reproducible 802.11p set-ups for current ns-3 versions.",
    "<b>Separating range from fading.</b> With a realistic fading model, range and loss are mixed together. A "
    "hard range cut-off isolates the effect of how far the radio reaches.",
])
para("<b>Selected research gap.</b> We choose one gap, combining the first, second and third: there is a lack of a "
     "reproducible, multi-seed study of AODV over IEEE 802.11p in current ns-3 that measures the effect of "
     "density, speed, load and range on delivery ratio, delay, throughput and loss, and that measures (instead of "
     "estimating) the combined best configuration and the contribution of each factor to it. The fourth point is "
     "a design choice and is treated as a limitation.")

# =========================================================================== CHAPTER 6
chapter(6, "Problem statement")
para("<b>Problem statement.</b> To design, build and run in NS-3 a highway VANET in which vehicles route with AODV "
     "over IEEE 802.11p and exchange UDP traffic; to measure how packet delivery ratio, end-to-end delay, "
     "throughput and packet loss change with vehicle density, vehicle speed, traffic load and communication range; "
     "and to find and verify the configuration that gives the most reliable delivery.")
para("<b>In simple terms.</b> Let N be the number of vehicles, v their mean speed, R the sending rate of each flow "
     "and r the radio range. For each of the four, we change it while keeping the others fixed and record the "
     "PDR P(N, v, R, r). We then look for the combination that gives the highest P and check it in the "
     "simulator.")
para("<b>Research questions.</b> (1) How does each factor change PDR, delay, throughput and loss? (2) Which factor "
     "matters most? (3) Do the trends hold for a different baseline and more seeds? (4) What PDR and delay does "
     "the combination of the best values give, and is it what the single-factor results predict? (5) Does each "
     "factor still help once the others are at their best?")
para("<b>Scope and assumptions.</b> This is a simulation of a straight two-way highway with constant-velocity "
     "vehicles. The radio reaches exactly r metres (no fading or obstacles). There are no roadside units; all "
     "traffic is vehicle-to-vehicle. Traffic is unicast, constant-rate UDP between random vehicle pairs, not "
     "broadcast safety beacons. AODV and the ns-3 wifi model are used with their default settings, and no ns-3 "
     "library file is modified.")

# =========================================================================== CHAPTER 7
chapter(7, "Methodology / implementation")
section("7.1 Proposed Architecture")
para("The scenario is a straight highway 2000 m long with two lanes in each direction, 5 m apart (Fig. 1). "
     "Vehicles are placed at random positions along the road; vehicle i uses lane i mod 4, so half drive east and "
     "half drive west. Each vehicle drives at the mean speed multiplied by a random factor between 0.8 and 1.2, so "
     "vehicles overtake each other. A vehicle that drives off one end of the road re-enters at the other end, so "
     "the number of vehicles on the road stays constant during the run. Ten vehicles are chosen as senders; each "
     "sends a constant-rate UDP flow to a randomly chosen receiver. All other vehicles relay packets.")
figure("fig_scenario.png", "Simulation scenario: two-way highway and multi-hop AODV routes")
para("The work was done in stages. Each stage is saved in the git history of the project (Table 2).")
table("Development stages and the programs built", ["Stage", "Program / output", "Change", "Role"], [
    ["1", "vanet-highway.cc, run_experiments.sh, plot_results.py", "Highway scenario, sweep runner, graphs",
     "Baseline study"],
    ["2", "run_experiments.sh, plot_results.py", "Sweep values and baseline configurable; separate plots folder",
     "Enables new variations"],
    ["3", "vanet-highway.cc (--trace), animate_trace.py", "Packet-level event trace and single-run animation",
     "Visual check"],
    ["4", "vanet-highway.cc, animate_sweep.py, make_animations.sh",
     "Wrap-around bug fixed; NetAnim output; sweep animations; all results regenerated", "Final main results"],
    ["5", "results/plots2", "Second variation: new baseline, wider ranges, 8 seeds", "Robustness check"],
    ["6", "results/optimal", "Combined best configuration and leave-one-out runs, 10 seeds", "Optimal solution"],
], [0.5, 2.0, 2.45, 1.3], align=["C", "L", "L", "C"])
subhead("Node architecture")
para("Every vehicle has the same protocol stack (Fig. 2). Senders and receivers differ only in the application "
     "they run. The data passes down the sender's stack, is relayed by other vehicles at the network layer by "
     "AODV, and passes up the receiver's stack. FlowMonitor watches the IP layer of every vehicle and records "
     "each packet of every flow.")
figure("fig_architecture.png", "Protocol stack of a vehicle and the path of a data packet", width=5.9)
table("Roles of the vehicles", ["Role", "Responsibility"], [
    ["Every vehicle (N)", "Moves at constant velocity; runs IPv4, AODV and an 802.11p radio; can relay packets"],
    ["Sender (10 distinct vehicles)", "OnOffApplication: constant-rate UDP, 512-byte payload, to port 9000 + f; "
                                      "starts at a random time in 10–11 s, stops at 95 s"],
    ["Receiver (random, not the sender)", "PacketSink bound to UDP port 9000 + f; receive callback counts packets"],
    ["Relay (any vehicle on the route)", "Forwards data and AODV messages hop by hop"],
    ["FlowMonitor (all vehicles)", "Records packets sent and received and their delay for each flow"],
    ["Trace / NetAnim (optional)", "Records positions, frames on air and AODV messages for animations"],
], [2.1, 4.15], align=["L", "L"])

section("7.2 Mathematical Model")
para("<b>Mobility.</b> Vehicle i starts at a random position x<sub>i</sub>(0) on a road of length L = 2000 m, "
     "with direction d<sub>i</sub> = +1 (east) or −1 (west) and speed v<sub>i</sub> = v̄ · U(0.8, 1.2). Its "
     "position at time t is")
eq("x<sub>i</sub>(t) = ( x<sub>i</sub>(0) + d<sub>i</sub> · v<sub>i</sub> · t )  mod  L")
para("<b>Links.</b> With the hard range cut-off, vehicles i and j can hear each other at time t only if")
eq("| p<sub>i</sub>(t) − p<sub>j</sub>(t) |  ≤  r")
para("where p is the position (x, lane) and r the communication range. With N vehicles spread over L, a vehicle "
     "has on average about")
eq("n̄  ≈  2 · r · N / L")
para("neighbours. For the baseline (N = 60, r = 150 m) this is about 9 neighbours; at r = 50 m it is 3 and at "
     "r = 250 m it is 15. With only a few neighbours, a gap longer than r appears easily and splits the road into "
     "isolated groups [12].")
para("<b>Hops.</b> A sender and receiver chosen at random on a road of length L are on average L/3 ≈ 667 m apart, "
     "so a route needs about")
eq("h̄  ≈  L / (3 · r)")
para("hops: about 4.4 at r = 150 m, 2.7 at r = 250 m and 13 at r = 50 m. Every extra hop is another chance for "
     "a collision or a broken link.")
para("<b>Link lifetime.</b> Two vehicles with relative speed Δv stay in range for at most")
eq("T<sub>link</sub>  ≈  2 · r / Δv")
para("For vehicles in opposite directions Δv ≈ 2v̄: at v̄ = 20 m/s and r = 150 m a link lasts at most 7.5 s, "
     "at 10 m/s about 15 s. Faster vehicles therefore break routes more often and force AODV to search again "
     "[9], [14].")
para("<b>Offered load.</b> Each flow sends R kbit/s in packets of S = 512 bytes, i.e. R · 1000 / (8 · S) "
     "packets per second (24.4 packets/s at 100 kbit/s). Because every packet is sent once per hop, the channel "
     "time that the flows need grows with the number of hops:")
eq("C  ≈  n<sub>f</sub> · R · h̄")
para("For the baseline (n<sub>f</sub> = 10 flows) this is about 10 × 100 × 4.4 ≈ 4.4 Mbit/s of transmissions "
     "on a 6 Mbit/s channel, before MAC overhead, AODV messages and collisions. At 750 kbit/s per flow it is many "
     "times the channel capacity, so the channel saturates [15], [16].")
para("<b>Metrics.</b> Let tx<sub>f</sub> and rx<sub>f</sub> be the packets sent and received by data flow f, "
     "D<sub>f</sub> the sum of the delays of its received packets and T<sub>f</sub> the time the flow was "
     "sending. Over the n<sub>f</sub> data flows of a run:")
eq("PDR = 100 · Σ rx<sub>f</sub> / Σ tx<sub>f</sub>")
eq("Delay = Σ D<sub>f</sub> / Σ rx<sub>f</sub>")
eq("Throughput = (1 / n<sub>f</sub>) · Σ ( rx<sub>f</sub> · 8 · S / T<sub>f</sub> )")
eq("Loss = 100 · ( Σ tx<sub>f</sub> − Σ rx<sub>f</sub> ) / Σ tx<sub>f</sub>  =  100 − PDR")
para("Throughput counts only the payload, so it can be compared directly with the offered rate R. Each test point "
     "is run with k seeds; we report the mean and the sample standard deviation")
eq("m = (1/k) · Σ y<sub>s</sub>,     σ = √( Σ (y<sub>s</sub> − m)<sup>2</sup> / (k − 1) )")
para("<b>Optimal configuration.</b> For each factor j with tested values V<sub>j</sub>, the best value is the one "
     "with the highest mean PDR, and the optimal configuration combines them:")
EQ_OPT = eq("x<sub>j</sub>* = argmax<sub>x ∈ V<sub>j</sub></sub> PDR<sub>j</sub>(x),      "
            "c* = (N*, v*, R*, r*)")
para("If the factors were independent, the PDR of c* could be estimated from the baseline PDR<sub>0</sub> and "
     "the gain of each factor:")
EQ_EST = eq("PDR<sub>est</sub> = PDR<sub>0</sub> · Π<sub>j</sub> ( PDR<sub>j</sub>(x<sub>j</sub>*) / "
            "PDR<sub>0</sub> )")
para(f"Section 9.4 compares this estimate ({EST:.1f}%) with the value measured in the simulator.")

section("7.3 Network Communication Model")
para("All data flows are UDP flows between vehicles that are usually out of direct radio range, so packets are "
     "passed along hop by hop by other vehicles on routes found by AODV. Each sender is an NS-3 OnOffApplication "
     "set to be always on, so it sends a steady stream at its DataRate with a fixed PacketSize. Senders start at a "
     "random time between 10 and 11 s, so AODV hello messages have already filled the neighbour tables, and stop at "
     "95 s, leaving 5 s for packets still on the way. Receivers run a PacketSink with a UDP socket bound to the "
     "flow's port.")
para("The flow of one packet is: the OnOff application calls Send() on its UDP socket; IPv4 asks AODV for a "
     "route (and buffers the packet while AODV searches); the packet is handed to the 802.11p MAC, sent at "
     "6 Mbit/s and acknowledged by the next hop; relays repeat this until the receiver's socket gets the packet "
     "and its callback runs. The messages used are listed in Table 4. AODV messages use the same channel as the "
     "data, so they compete with it. FlowMonitor recognises the data flows by their destination port and leaves "
     "the AODV flows out of the results.")
table("Messages and ports used in the network", ["Message", "From → to", "Port", "When", "Purpose"], [
    ["UDP data (512 B payload)", "Sender → receiver (multi-hop)", "9000–9009", "Constant rate, 10–95 s",
     "Application traffic"],
    ["RREQ", "Source → all (flooded)", "654", "When a route is needed", "Route discovery"],
    ["RREP", "Destination → source (unicast)", "654", "Answer to RREQ", "Route set-up"],
    ["RERR", "Vehicle at a broken link → sources", "654", "When a link breaks", "Route repair"],
    ["HELLO (RREP, TTL 1)", "Every vehicle → neighbours", "654", "About every 1 s", "Neighbour detection"],
    ["802.11 ACK", "Next hop → previous hop", "–", "After each unicast frame", "MAC reliability"],
], [1.5, 1.75, 0.75, 1.25, 1.0], align=["L", "L", "C", "L", "L"], size=9.5)
para("Figure 4 (Section 7.4) shows these messages for one flow: route discovery at the start, data delivery and "
     "the repair of a route after a link breaks.")

section("7.4 Proposed Algorithm")
para("One simulation run is the program vanet-highway.cc (Fig. 3). It takes the four factors and the seed on the "
     "command line, builds the scenario, runs 100 simulated seconds and appends one row of results to a CSV file.")
figure("fig_flowchart.png", "Flowchart of one simulation run (vanet-highway.cc)", width=4.3)
code([
    "1  parse N, v, R, r, RngRun from the command line",
    "2  create N vehicles; for i in 0..N-1:",
    "3      lane <- i mod 4;  direction <- +1 if lane < 2 else -1",
    "4      x <- U(0, L);  speed <- v * U(0.8, 1.2)",
    "5  install 802.11p PHY (6 Mbit/s), ad hoc MAC, RangePropagationLoss(r)",
    "6  install IPv4 + AODV; assign addresses 10.1.0.0/16",
    "7  shuffle vehicles; senders <- first 10; for each flow f:",
    "8      dst <- random vehicle != src;  port <- 9000 + f",
    "9      PacketSink on dst:port;  OnOff(src -> dst:port, rate R, 512 B)",
    "10     start <- 10 + U(0, 1);  stop <- 95",
    "11 install FlowMonitor; every 0.1 s: WrapPositions()",
    "12 run the simulator until t = 100 s",
    "13 for each FlowMonitor flow: if UDP to a data port: add tx, rx, delay",
    "14 compute PDR, delay, throughput, loss; append one row to the CSV file",
], "Algorithm 1: One simulation run (vanet-highway.cc, simplified)")
code([
    "1  for each sweep in {density, speed, load, range}:",
    "2      for each value x of the sweep:",
    "3          set the factor to x, keep the other three at the baseline",
    "4          for seed in 1..SEEDS: add job (sweep, x, seed)",
    "5  run all jobs in parallel (xargs -P JOBS); skip jobs whose CSV already exists",
    "6  plot_results.py: merge CSVs; mean and std per (sweep, x); draw 5 graphs",
], "Algorithm 2: Parameter sweeps (run_experiments.sh and plot_results.py)")
code([
    "1  for each factor j: x_j* <- tested value with the highest mean PDR",
    "2  c* <- (N*, v*, R*, r*);  run c* and the baseline with seeds 1..10",
    "3  for each factor j: run c* with factor j set back to its baseline value",
    "4  compare the measured PDR of c* with the estimate of Equation (" + str(EQ_EST) + ")",
], "Algorithm 3: Finding and checking the optimal configuration")
figure("fig_sequence.png", "Sequence diagram of route discovery, data delivery and route repair",
       width=5.8)

section("7.5 Socket Programming Implementation")
para("The program is a single C++ file, vanet-highway.cc (453 lines), copied into the scratch folder of ns-3 and "
     "built with ./ns3 build. The main parts are shown below.")
subhead("Keeping vehicles on the road (WrapPositions)")
para("A vehicle that leaves the road re-enters at the other end. We found that ns-3's "
     "ConstantVelocityMobilityModel::SetPosition also sets the velocity to zero, so in an early version vehicles "
     "stopped for good after their first wrap; by t = 60 s about two thirds of them were parked. The fix restores "
     "the velocity after moving the vehicle, and all results were regenerated:")
code([
    "Vector pos = mob->GetPosition();",
    "if (pos.x > length || pos.x < 0) {",
    "    Vector vel = mob->GetVelocity();",
    "    pos.x += pos.x > length ? -length : length;",
    "    mob->SetPosition(pos);",
    "    mob->SetVelocity(vel);   // SetPosition sets the velocity to zero",
    "}",
    "Simulator::Schedule(interval, &WrapPositions, vehicles, length, interval);",
])
subhead("Radio: IEEE 802.11p with a hard range cut-off")
code([
    "YansWifiChannelHelper channel;",
    "channel.SetPropagationDelay(\"ns3::ConstantSpeedPropagationDelayModel\");",
    "channel.AddPropagationLoss(\"ns3::RangePropagationLossModel\",",
    "                           \"MaxRange\", DoubleValue(range));",
    "WifiHelper wifi;",
    "wifi.SetStandard(WIFI_STANDARD_80211p);",
    "wifi.SetRemoteStationManager(\"ns3::ConstantRateWifiManager\",",
    "    \"DataMode\", StringValue(\"OfdmRate6MbpsBW10MHz\"),",
    "    \"ControlMode\", StringValue(\"OfdmRate6MbpsBW10MHz\"));",
    "mac.SetType(\"ns3::AdhocWifiMac\");",
])
subhead("Routing and addresses")
code([
    "AodvHelper aodv;",
    "InternetStackHelper internet;",
    "internet.SetRoutingHelper(aodv);",
    "internet.Install(vehicles);",
    "address.SetBase(\"10.1.0.0\", \"255.255.0.0\");",
])
subhead("UDP sender and receiver sockets")
para("For each flow the receiver gets a PacketSink bound to the flow's port, and the sender an OnOffApplication "
     "that sends to the receiver's address and port at a constant rate:")
code([
    "PacketSinkHelper sink(\"ns3::UdpSocketFactory\",",
    "                      InetSocketAddress(Ipv4Address::GetAny(), port));",
    "sink.Install(vehicles.Get(dst));",
    "OnOffHelper onoff(\"ns3::UdpSocketFactory\",",
    "                  InetSocketAddress(interfaces.GetAddress(dst), port));",
    "onoff.SetConstantRate(DataRate(dataRateKbps * 1000), packetSize);",
    "ApplicationContainer srcApp = onoff.Install(vehicles.Get(src));",
    "srcApp.Start(Seconds(appStart + startJitter->GetValue()));",
    "srcApp.Stop(Seconds(appStop));",
])
para("Inside ns-3 these helpers use the Socket API in the same way as a Linux program uses system calls. "
     "PacketSink calls Socket::CreateSocket() with the UDP socket factory (like <i>socket()</i>), Bind() to the "
     "port (like <i>bind()</i>) and SetRecvCallback(), and reads packets with RecvFrom() (like "
     "<i>recvfrom()</i>). OnOffApplication creates a UDP socket, calls Connect() to the receiver's address and "
     "then Send() for each packet at intervals of 8 · S / R seconds (like <i>connect()</i> and "
     "<i>send()</i>).")
subhead("Measuring only the data flows")
code([
    "for (const auto& [flowId, st] : monitor->GetFlowStats()) {",
    "    Ipv4FlowClassifier::FiveTuple t = classifier->FindFlow(flowId);",
    "    if (t.protocol != 17 || activeTime.count(t.destinationPort) == 0)",
    "        continue;                       // skip AODV control traffic",
    "    txPackets += st.txPackets;",
    "    rxPackets += st.rxPackets;",
    "    delaySum  += st.delaySum.GetSeconds();",
    "    throughputSum += st.rxPackets * packetSize * 8.0",
    "                     / activeTime[t.destinationPort] / 1000.0;",
    "}",
])
subhead("Running the program")
para("A single run, and the full set of sweeps, are started with:")
code([
    "./ns3 run \"vanet-highway --nVehicles=60 --speed=20 --dataRateKbps=100 \\",
    "           --range=150 --RngRun=1\"",
    "NS3_DIR=~/ns-allinone-3.48/ns-3.48 bash run_experiments.sh",
    "python3 plot_results.py results",
])
para("Two optional switches record what happens inside a run without changing the results row: --trace=FILE writes "
     "one line per event (Table 5) for the Python animation scripts, and --netanim=FILE.xml writes a NetAnim "
     "animation in which senders are orange and receivers green.")
table("Events written by the --trace option", ["Line", "Fields", "Meaning"], [
    ["F", "flow, src, dst, port, start", "Flow definition"],
    ["P", "t, node, x, y", "Vehicle position (every 0.1 s)"],
    ["S", "t, node, port, uid", "Application sends a data packet"],
    ["R", "t, node, port, uid, delayMs", "Receiver gets a data packet"],
    ["D", "t, node, nextHop, port, uid", "A data frame goes on air (one per hop and retry)"],
    ["C", "t, node, type", "An AODV frame goes on air (RREQ, RREP, RERR, HELLO)"],
], [0.6, 2.4, 3.25], align=["C", "L", "L"])

# =========================================================================== CHAPTER 8
chapter(8, "Performance evaluation")
section("8.1 Experimental Setup")
para("All runs were done on the same Apple Silicon laptop (macOS, 18 cores) with ns-3.48, using the settings in "
     "Table 6. NS-3 uses fixed pseudo-random number streams, so running the same command with the same --RngRun "
     "gives exactly the same result; different seeds give different start positions, speeds and flow pairs. One run "
     "takes about 25 s of CPU time, and 18 runs are done in parallel.")
table("Simulation parameters", ["Parameter", "Value"], [
    ["Simulator", "ns-3.48 (scenario written for ns-3.45), macOS"],
    ["Road", "Straight highway, 2000 m, 2 lanes per direction, 5 m apart, wrap-around at the ends"],
    ["Mobility", "Constant velocity; speed = mean × U(0.8, 1.2); half the vehicles in each direction"],
    ["PHY / MAC", "IEEE 802.11p (5.9 GHz, 10 MHz channel), 6 Mbit/s OFDM, 20 dBm, ad hoc MAC"],
    ["Propagation", "Constant-speed delay; RangePropagationLossModel, MaxRange = r"],
    ["Routing", "AODV (ns-3 default settings)"],
    ["Traffic", "10 UDP flows (OnOff → PacketSink), 512-byte payload, distinct random senders"],
    ["Timing", "100 s simulated; flows start at U(10, 11) s and stop at 95 s"],
    ["Baseline", "60 vehicles, 20 m/s, 100 kbit/s per flow, 150 m range"],
    ["Seeds", "5 per test point (main sweeps), 8 (second variation), 10 (optimal study)"],
    ["Measurement", "FlowMonitor, data flows only; one CSV row per run"],
], [1.5, 4.75], align=["L", "L"])
section("8.2 Performance Metrics")
para("The metrics in Table 7 are computed at the end of every run from FlowMonitor, using Equations (7) to (10), "
     "and averaged over the seeds of each test point. Dropped packets have no receive time, so the average delay is "
     "taken over received packets only. The flows stop at 95 s and the simulation at 100 s, so every run ends with a "
     "5 s drain period in which packets still in queues can arrive; a packet that has not arrived by 100 s counts as "
     "lost (FlowMonitor CheckForLostPackets). Throughput is measured over the time each flow was sending, from its "
     "start time to 95 s, and counts payload bits only. The start-up period before 10 s, in which AODV learns its "
     "neighbours, carries no data and is therefore not part of any metric.")
table("Performance metrics", ["Metric", "Meaning", "Unit", "Source"], [
    ["Packet delivery ratio", "rx / tx × 100, over all data flows", "%", "FlowMonitor"],
    ["End-to-end delay", "Total delay of received packets / packets received", "ms", "FlowMonitor"],
    ["Throughput", "Mean over flows of payload bits received / time the flow was sending", "kbit/s per flow",
     "FlowMonitor"],
    ["Packet loss rate", "(tx − rx) / tx × 100", "%", "FlowMonitor"],
    ["Mean ± std", "Mean and sample standard deviation over the seeds", "–", "plot_results.py"],
], [1.4, 2.75, 0.9, 1.2], align=["L", "L", "C", "C"])
section("8.3 Experiments and Procedure")
para("Each sweep varies one factor and keeps the other three at the baseline (Table 8). Every test point is run "
     "with several seeds; the graphs show the mean with standard-deviation error bars. The whole procedure is "
     "automated (Fig. 5): run_experiments.sh writes one job per run and runs them in parallel, each run appends "
     "one CSV row, and plot_results.py merges the rows, computes the statistics and draws the graphs. An "
     "interrupted batch can be restarted with the same command, because finished runs are skipped.")
table("Experiments", ["Experiment", "Values", "Fixed at", "Seeds", "Runs", "Graphs"], [
    ["Density", "20, 40, 60, 80, 100 vehicles", "Baseline", "5", "25", "Density vs PDR; density vs loss"],
    ["Speed", "10, 15, 20, 25 m/s (36–90 km/h)", "Baseline", "5", "20", "Speed vs delay"],
    ["Load", "50, 100, 250, 500, 750 kbit/s per flow", "Baseline", "5", "25", "Load vs throughput"],
    ["Range", "50, 100, 150, 200, 250 m", "Baseline", "5", "25", "Range vs PDR"],
    ["Second variation", "Density 30–130, speed 5–35, load 25–1000, range 75–325",
     "70 veh., 15 m/s, 150 kbit/s, 175 m", "8", "200", "Same four graphs"],
    ["Optimal study", "Optimal, baseline and 4 leave-one-out configurations", "See Section 9.4", "10", "60", "PDR, delay, loss bars"],
], [1.0, 1.75, 1.2, 0.5, 0.45, 1.35], align=["L", "L", "L", "C", "C", "L"], size=9.5)
figure("fig_workflow.png", "Experiment workflow, from the job list to the graphs and the optimal configuration")
section("8.4 Fairness and Validity of the Comparison")
para("Within a sweep, every test point uses the same seeds 1 to 5, so the same random streams set the start "
     "positions, speeds and flow pairs; only the varied factor differs. The baseline point is the same configuration "
     "in all four sweeps and gives identical results in each (36.98% PDR), which confirms that the sweeps share it. "
     "The second variation uses a different baseline, different values and eight seeds, so it checks that the "
     "trends do not depend on our particular choices. The optimal configuration and the baseline were both run with "
     "the same ten seeds, so they are compared on the same random streams.")
para("Two limits apply to all results. First, run-to-run variation is large (a standard deviation of about 6 to 15 "
     "PDR points with 5 seeds), so neighbouring test points can overlap. Second, the radio model has a hard range "
     "and no fading, so absolute PDR values are specific to this model; the trends are what we compare.")

# =========================================================================== CHAPTER 9
chapter(9, "Output and results")
section("9.1 Comparative Analysis")
para("Table 9 lists the mean and standard deviation of every test point of the four main sweeps (5 seeds each). "
     "The baseline (60 vehicles, 20 m/s, 100 kbit/s, 150 m) appears once in each sweep.")
rows = []
labels = {"density": ("Density", "veh."), "speed": ("Speed", "m/s"), "load": ("Load", "kbit/s"),
          "range": ("Range", "m")}
for e in ("density", "speed", "load", "range"):
    for (ee, x), r in sorted(S.items()):
        if ee != e:
            continue
        rows.append([labels[e][0], f"{x:g} {labels[e][1]}", f"{f1(r['pdr_mean'])} ± {f1(r['pdr_std'])}",
                     f"{f1(r['delayMs_mean'])} ± {f1(r['delayMs_std'])}",
                     f"{f1(r['throughputKbps_mean'])} ± {f1(r['throughputKbps_std'])}", f1(r["lossRate_mean"])])
table("Results of the four parameter sweeps (mean ± standard deviation, 5 seeds)",
      ["Sweep", "Value", "PDR (%)", "Delay (ms)", "Throughput (kbit/s/flow)", "Loss (%)"], rows,
      [0.9, 1.0, 1.15, 1.2, 1.3, 0.7], size=9.5)

subhead("Vehicle density")
figure("density_vs_pdr.png", "Vehicle density versus packet delivery ratio (AODV; 20 m/s, 100 kbit/s, 150 m; 5 seeds)", width=4.6,
       folder=os.path.join(PROJ, "results/plots"))
para(f"PDR rises from {f1(S[('density', 20.0)]['pdr_mean'])}% with 20 vehicles to "
     f"{f1(S[('density', 60.0)]['pdr_mean'])}% with 60 and {f1(S[('density', 80.0)]['pdr_mean'])}% with 80, then "
     f"falls to {f1(S[('density', 100.0)]['pdr_mean'])}% with 100 vehicles (Fig. 6). With 20 vehicles a vehicle has "
     "only about 3 neighbours (Equation 3), the road often splits into groups that cannot reach each other and "
     f"packets wait for routes that never form; the delay is {f1(S[('density', 20.0)]['delayMs_mean'])} ms. More "
     f"vehicles fill the gaps and the delay falls to {f1(S[('density', 80.0)]['delayMs_mean'])} ms at 80. With 100 "
     "vehicles each RREQ flood reaches about 15 neighbours, and route discovery and channel contention start to "
     "cost more than the extra connectivity gives [11].")
figure("density_vs_loss.png", "Vehicle density versus packet loss rate (AODV; 20 m/s, 100 kbit/s, 150 m; 5 seeds)",
       width=4.6, folder=os.path.join(PROJ, "results/plots"))
para(f"Packet loss is the mirror image of PDR (Fig. 7): it falls from {f1(S[('density', 20.0)]['lossRate_mean'])}% "
     f"with 20 vehicles to {f1(S[('density', 80.0)]['lossRate_mean'])}% with 80 and rises again to "
     f"{f1(S[('density', 100.0)]['lossRate_mean'])}% with 100. Even at its lowest, more than 60% of the packets are "
     "lost at the baseline speed, load and range, which shows how hard multi-hop delivery along a 2 km road is.")
subhead("Vehicle speed")
figure("speed_vs_delay.png", "Mean vehicle speed versus average end-to-end delay (AODV; 60 vehicles, 100 kbit/s, 150 m; 5 seeds)", width=4.6,
       folder=os.path.join(PROJ, "results/plots"))
para(f"Delay rises from {f1(S[('speed', 10.0)]['delayMs_mean'])} ms at 10 m/s to "
     f"{f1(S[('speed', 25.0)]['delayMs_mean'])} ms at 25 m/s (Fig. 8), with a dip at 20 m/s that lies inside the "
     f"error bars. PDR falls steadily from {f1(S[('speed', 10.0)]['pdr_mean'])}% to "
     f"{f1(S[('speed', 25.0)]['pdr_mean'])}%. Both happen because links between vehicles break sooner "
     "(Equation 5): AODV spends more time rediscovering routes, and packets are buffered or dropped meanwhile.")
subhead("Traffic load")
figure("load_vs_throughput.png", "Offered load versus delivered throughput per flow (AODV; 60 vehicles, 20 m/s, 150 m; 5 seeds)", width=4.6,
       folder=os.path.join(PROJ, "results/plots"))
para(f"Delivered throughput grows from {f1(S[('load', 50.0)]['throughputKbps_mean'])} to "
     f"{f1(S[('load', 750.0)]['throughputKbps_mean'])} kbit/s per flow as the offered load grows from 50 to "
     "750 kbit/s, but it falls further and further below the offered rate (dashed line, Fig. 9): about 39% of the "
     f"offered rate arrives at 50 kbit/s and only {f1(S[('load', 750.0)]['pdr_mean'])}% at 750 kbit/s. The shared "
     "6 Mbit/s channel saturates (Equation 6), so more packets collide or are dropped from full queues. The delay "
     f"at 50 kbit/s ({f1(S[('load', 50.0)]['delayMs_mean'])} ± {f1(S[('load', 50.0)]['delayMs_std'])} ms) is higher "
     "than at 100 kbit/s; we have not found the reason, and the error bar is large.")
subhead("Communication range")
figure("range_vs_pdr.png", "Communication range versus packet delivery ratio (AODV; 60 vehicles, 20 m/s, 100 kbit/s; 5 seeds)", width=4.6,
       folder=os.path.join(PROJ, "results/plots"))
para(f"Range has the strongest effect. PDR rises from {f1(S[('range', 50.0)]['pdr_mean'])}% at 50 m to "
     f"{f1(S[('range', 250.0)]['pdr_mean'])}% at 250 m, and the delay falls from "
     f"{f1(S[('range', 50.0)]['delayMs_mean'])} ms to {f1(S[('range', 250.0)]['delayMs_mean'])} ms (Fig. 10). At "
     "50 m a vehicle has about 3 neighbours and a route would need about 13 hops (Equation 4), so the road splits "
     "into isolated groups and most packets never find a route. A longer range gives more neighbours and shorter "
     "routes.")
subhead("Comparison of the factors")
figure("fig_factor_effect.png", "PDR at the worst and best tested value of each factor", width=5.6)
FAC = []
for name, e, vals, u in (("Range", "range", [50, 100, 150, 200, 250], "m"),
                         ("Load", "load", [50, 100, 250, 500, 750], "kbit/s"),
                         ("Density", "density", [20, 40, 60, 80, 100], "veh."),
                         ("Speed", "speed", [10, 15, 20, 25], "m/s")):
    p = {v: float(S[(e, float(v))]["pdr_mean"]) for v in vals}
    vb, vw = max(p, key=p.get), min(p, key=p.get)
    FAC.append([name, f"{vals[0]}–{vals[-1]} {u}", f"{p[vw]:.1f} ({vw} {u})", f"{p[vb]:.1f} ({vb} {u})",
                f"{p[vb] - p[vw]:.1f}", f"{p[vb] - float(S[('density', 60.0)]['pdr_mean']):+.1f}"])
table("Effect of each factor on PDR", ["Factor", "Tested", "Worst PDR (%)", "Best PDR (%)", "Span (points)",
                                       "Best vs baseline"], FAC, [0.8, 1.35, 1.3, 1.3, 0.75, 0.75], size=9.5)
para("Range changes PDR the most, both over the tested values (47 points) and as an improvement over the baseline "
     "(+16 points). Speed is the second-best way to improve on the baseline (+9 points). High load and low density "
     "hurt a lot, but going below the baseline load or above the baseline density helps only a little (Fig. 11, "
     "Table 10).")

section("9.2 Validation of the Approach")
para("We checked the results in seven ways (Table 11).")
s5 = [r for r in ORUNS if r["experiment"] == "baseline" and r["run"] == "1"][0]
table("Validation checks", ["Check", "What was done", "Result"], [
    ["Repeatability", "Baseline seeds 1–5 run again for this report",
     f"Identical to the last digit (seed 1: {s5['txPackets']} sent, {s5['rxPackets']} received)"],
    ["Shared baseline", "Baseline point compared across the four sweeps", "Same 36.98% PDR in all four"],
    ["Bug fix", "Vehicles stopped after wrapping (velocity reset to zero)",
     "Velocity restored; every result regenerated"],
    ["Metric consistency", "Throughput compared with PDR × offered rate",
     f"Load 250: {f1(S[('load', 250.0)]['pdr_mean'])}% × 250 = "
     f"{float(S[('load', 250.0)]['pdr_mean']) * 2.5:.1f} ≈ {f1(S[('load', 250.0)]['throughputKbps_mean'])} kbit/s"],
    ["PDR and loss", "PDR + loss compared for every run (95 + 200 + 60 runs)",
     "Sum is 100% in every run (to within 0.001 points)"],
    ["Control traffic", "Only UDP flows to the data ports counted", "AODV flows excluded from all metrics"],
    ["Second variation", "New baseline, wider ranges, 8 seeds (200 runs)", "Same trends (Fig. 12, Table 12)"],
], [1.3, 2.35, 2.6], align=["L", "L", "L"], size=9.5)
subhead("Second parameter variation")
para("To check that the trends do not depend on our choice of baseline and values, we ran a second variation with "
     "a baseline of 70 vehicles, 15 m/s, 150 kbit/s and 175 m, wider ranges of values and eight seeds per point "
     "(Fig. 12, Table 12).")
figure("fig_plots2.png", "Second variation (8 seeds): density vs PDR, speed vs delay, load vs throughput and "
                         "range vs PDR", width=6.2)
r2 = []
for e, vals, u in (("density", [30, 50, 70, 90, 110, 130], "veh."), ("speed", [5, 10, 15, 20, 25, 30, 35], "m/s"),
                   ("load", [25, 75, 150, 300, 600, 1000], "kbit/s"), ("range", [75, 125, 175, 225, 275, 325], "m")):
    r2.append([labels[e][0], f"{vals[0]}–{vals[-1]} {u}",
               " / ".join(f1(S2[(e, float(v))]["pdr_mean"]) for v in vals)])
table("PDR (%) in the second variation, in the order of the tested values", ["Sweep", "Values", "PDR (%)"], r2,
      [0.9, 1.3, 4.05], align=["L", "L", "L"], size=9.5)
para(f"The trends are the same. PDR falls steadily with speed ({f1(S2[('speed', 5.0)]['pdr_mean'])}% at 5 m/s to "
     f"{f1(S2[('speed', 35.0)]['pdr_mean'])}% at 35 m/s) and with load ({f1(S2[('load', 25.0)]['pdr_mean'])}% to "
     f"{f1(S2[('load', 1000.0)]['pdr_mean'])}%). Density is flat up to 70 vehicles and then falls. Range adds the "
     f"most at short ranges ({f1(S2[('range', 75.0)]['pdr_mean'])}% at 75 m to {f1(S2[('range', 175.0)]['pdr_mean'])}% "
     f"at 175 m) but levels off above about 225 m ({f1(S2[('range', 225.0)]['pdr_mean'])}%, "
     f"{f1(S2[('range', 275.0)]['pdr_mean'])}%, {f1(S2[('range', 325.0)]['pdr_mean'])}%), while the delay rises "
     f"again ({f1(S2[('range', 225.0)]['delayMs_mean'])} to {f1(S2[('range', 325.0)]['delayMs_mean'])} ms). So the "
     "gain from range does not continue for ever: once the road is connected, a longer range mainly adds contention.")

section("9.3 Visualisation of the Sweeps")
para("To see what happens inside a run, make_animations.sh runs seed 1 of every test point with tracing on, and "
     "animate_sweep.py draws all values of one sweep on one clock, with a live bar of the metric that the sweep's "
     "graph plots. Figures 13 and 14 are snapshots at t = 30 s. Orange squares are senders, blue arcs are data "
     "hops on air, light blue dots are route requests, red crosses are route errors and green circles are "
     "delivered packets.")
figure("range_sweep_t30.png", "Range sweep at t = 30 s (seed 1): longer range gives longer hops and more "
                              "deliveries", width=6.2, folder=os.path.join(PROJ, "results/animations"))
para("At 50 m (top row) almost no data hops are on air: senders cannot find routes. As the range grows, the arcs "
     "get longer and more packets are delivered. At 200 m many route errors (red) appear as links break and are "
     "repaired.")
figure("density_sweep_t30.png", "Density sweep at t = 30 s (seed 1)", width=6.2,
       folder=os.path.join(PROJ, "results/animations"))
para("With 20 vehicles the road has long empty gaps and the senders are isolated. With more vehicles the gaps "
     "close and more packets are delivered. All rows use the same seed, so a single run can differ from the "
     "5-seed mean: with seed 1, 100 vehicles reach 40% PDR, although the 5-seed mean drops to 29% there.")

section("9.4 Final Optimal Solution")
para("Table 13 lists the best tested value of each factor, using the 5-seed means of Table 9.")
table("Best tested value of each factor (5 seeds)", ["Factor", "Best value", "PDR (%)", "Delay (ms)", "Loss (%)",
                                                     "Why"], [
    ["Density", "80 vehicles", f1(S[("density", 80.0)]["pdr_mean"]), f1(S[("density", 80.0)]["delayMs_mean"]),
     f1(S[("density", 80.0)]["lossRate_mean"]), "Sweet spot: 20 is too sparse, 100 has too much contention"],
    ["Load", "50 kbit/s (lowest)", f1(S[("load", 50.0)]["pdr_mean"]), f1(S[("load", 50.0)]["delayMs_mean"]),
     f1(S[("load", 50.0)]["lossRate_mean"]), "Less traffic means less contention; throughput is lower"],
    ["Range", "250 m (highest)", f1(S[("range", 250.0)]["pdr_mean"]), f1(S[("range", 250.0)]["delayMs_mean"]),
     f1(S[("range", 250.0)]["lossRate_mean"]), "More neighbours, fewer hops, no isolated groups"],
    ["Speed", "10 m/s (lowest)", f1(S[("speed", 10.0)]["pdr_mean"]), f1(S[("speed", 10.0)]["delayMs_mean"]),
     f1(S[("speed", 10.0)]["lossRate_mean"]), "Links last longer, fewer route breaks"],
], [0.75, 1.15, 0.65, 0.7, 0.6, 2.4], align=["L", "L", "C", "C", "C", "L"], size=9.5)
para("Combining them gives the candidate optimal configuration c* = (80 vehicles, 10 m/s, 50 kbit/s, 250 m). If the "
     f"factors did not interact, Equation ({EQ_EST}) would predict a PDR of "
     f"{f1(S[('density', 60.0)]['pdr_mean'])}% × "
     + " × ".join(f"{float(S[(e, x)]['pdr_mean']) / float(S[('density', 60.0)]['pdr_mean']):.3f}"
                  for e, x in (("density", 80.0), ("load", 50.0), ("range", 250.0), ("speed", 10.0)))
     + f" ≈ {EST:.1f}%. Instead of relying on this estimate, we ran c* and the baseline in the simulator with the "
       "same ten seeds (Table 14, Fig. 15).")
table("Baseline and optimal configuration (mean ± standard deviation, 10 seeds)",
      ["Measure", "Baseline", "Optimal", "Change"], [
          ["Vehicles / speed", "60 / 20 m/s", "80 / 10 m/s", "–"],
          ["Load / range", "100 kbit/s / 150 m", "50 kbit/s / 250 m", "–"],
          ["Packet delivery ratio", f"{f1(b['pdr_mean'])} ± {f1(b['pdr_std'])}%", f"{f1(o['pdr_mean'])} ± "
                                                                                   f"{f1(o['pdr_std'])}%",
           f"+{float(o['pdr_mean']) - float(b['pdr_mean']):.1f} points (× "
           f"{float(o['pdr_mean']) / float(b['pdr_mean']):.2f})"],
          ["Average delay", f"{f1(b['delayMs_mean'])} ± {f1(b['delayMs_std'])} ms",
           f"{f1(o['delayMs_mean'])} ± {f1(o['delayMs_std'])} ms",
           f"{100 * (float(o['delayMs_mean']) / float(b['delayMs_mean']) - 1):.0f}%".replace("-", "−")],
          ["Packet loss rate", f"{f1(b['lossRate_mean'])}%", f"{f1(o['lossRate_mean'])}%",
           f"{float(o['lossRate_mean']) - float(b['lossRate_mean']):.1f} points".replace("-", "−")],
          ["Throughput per flow", f"{f1(b['throughputKbps_mean'])} kbit/s (of 100)",
           f"{f1(o['throughputKbps_mean'])} kbit/s (of 50)", "Lower: half the offered load"],
          ["Estimate, Equation (" + str(EQ_EST) + ")", "–", f"{EST:.1f}% PDR",
           f"Measured is {EST - float(o['pdr_mean']):.1f} points lower"],
      ], [1.6, 1.55, 1.55, 1.55], align=["L", "C", "C", "C"], size=9.5)
figure("fig_optimal.png", "PDR, delay and packet loss of the baseline and the optimal configuration (10 seeds)",
       width=6.2)
para(f"The optimal configuration raises PDR from {f1(b['pdr_mean'])}% to {f1(o['pdr_mean'])}% and cuts the "
     f"average delay by about {100 * (1 - float(o['delayMs_mean']) / float(b['delayMs_mean'])):.0f}%, from "
     f"{f1(b['delayMs_mean'])} ms to {f1(o['delayMs_mean'])} ms, well inside the 100 ms that safety applications "
     f"need. It is also far more predictable: the standard deviation of PDR falls from {f1(b['pdr_std'])} to "
     f"{f1(o['pdr_std'])} points, and it beats the baseline on every one of the ten seeds (Fig. 16). However, the "
     f"measured PDR is about {EST - float(o['pdr_mean']):.0f} points below the {EST:.0f}% estimate, and only "
     f"{float(o['pdr_mean']) - float(S[('range', 250.0)]['pdr_mean']):.0f} points above the best single change "
     f"(250 m range alone, {f1(S[('range', 250.0)]['pdr_mean'])}%). The gains of the factors do not multiply.")
figure("fig_per_seed.png", "PDR of every run of the baseline and the optimal configuration", width=5.4)
subhead("Leave-one-out check")
para("To see how much each factor contributes once the others are already at their best, we ran c* four more "
     "times, each time putting one factor back to its baseline value (Table 15, Fig. 17).")
LOO = [("optimal", "None (optimal)", "80, 10, 50, 250"), ("loo_density", "Density 80 → 60", "60, 10, 50, 250"),
       ("loo_speed", "Speed 10 → 20 m/s", "80, 20, 50, 250"), ("loo_load", "Load 50 → 100 kbit/s", "80, 10, 100, 250"),
       ("loo_range", "Range 250 → 150 m", "80, 10, 50, 150"), ("baseline", "All four (baseline)", "60, 20, 100, 150")]
table("Leave-one-out check (10 seeds)", ["Factor put back", "N, v, R, r", "PDR (%)", "Delay (ms)",
                                         "Throughput (kbit/s/flow)", "PDR vs optimal"], [
    [lab, cfg, f"{f1(O[k]['pdr_mean'])} ± {f1(O[k]['pdr_std'])}", f"{f1(O[k]['delayMs_mean'])} ± "
                                                                    f"{f1(O[k]['delayMs_std'])}",
     f1(O[k]["throughputKbps_mean"]),
     "–" if k == "optimal" else f"{float(O[k]['pdr_mean']) - float(o['pdr_mean']):+.1f}".replace("-", "−")] for k, lab, cfg in LOO
], [1.45, 1.1, 1.0, 1.0, 1.0, 0.7], align=["L", "C", "C", "C", "C", "C"], size=9.5)
figure("fig_loo.png", "Leave-one-out check: PDR when one factor is put back to its baseline value", width=5.8)
para(f"Putting speed, load or range back each costs 6 to 8 PDR points and raises the delay (to about "
     f"{f1(O['loo_load']['delayMs_mean'])} ms for load and {f1(O['loo_range']['delayMs_mean'])} ms for range), so "
     f"these three factors all still help in the combination. Density is different: with 60 instead of 80 "
     f"vehicles the PDR is {f1(O['loo_density']['pdr_mean'])} ± {f1(O['loo_density']['pdr_std'])}%, slightly "
     f"higher than {f1(o['pdr_mean'])} ± {f1(o['pdr_std'])}% but well within one standard deviation. With a 250 m "
     "range each vehicle already has about 15–20 neighbours, so adding vehicles no longer improves connectivity and "
     "mainly adds contention. The density optimum therefore moves down when the range grows: this interaction "
     "is why the single-factor gains do not multiply.")
subhead("Recommended configuration")
para("<b>Final optimal solution.</b> Communication range 250 m, mean speed 10 m/s, offered load 50 kbit/s per "
     "flow and 60–80 vehicles per 2 km of four-lane highway. We keep 80 vehicles as the final value because 60 and "
     "80 give the same PDR within the error bars, and 80 gives a much more consistent result "
     f"(standard deviation {f1(o['pdr_std'])} against {f1(O['loo_density']['pdr_std'])} points). Measured over ten "
     f"seeds, this configuration delivers {f1(o['pdr_mean'])}% of the packets with an average delay of "
     f"{f1(o['delayMs_mean'])} ms and a loss rate of {f1(o['lossRate_mean'])}%.")
para("Of the four factors, only two are design choices: the range (set by the transmit power and the receiver "
     "sensitivity) and the load (set by how often applications send). Speed and density describe the traffic, so "
     "the optimal solution says under which conditions the network works best, for example dense, slower traffic "
     "near a junction or a speed-limited zone. If the goal is throughput rather than reliability, a higher load is "
     "better: at 100 kbit/s per flow the network delivers "
     f"{f1(O['loo_load']['throughputKbps_mean'])} kbit/s per flow instead of {f1(o['throughputKbps_mean'])}, at "
     "the cost of 8 PDR points.")

section("9.5 Observations")
for t in [
    "Range is the most important factor. A short range splits the highway into isolated groups; a longer range "
    "gives more neighbours and fewer hops. Above about 225 m the gain levels off and the delay rises again.",
    "Faster vehicles lose more packets and wait longer, because links last a shorter time and AODV must find new "
    "routes more often.",
    "The shared channel saturates quickly. Even at the baseline only about a third of the offered traffic "
    "arrives, and at 750 kbit/s per flow less than a fifth does.",
    "Density has a sweet spot: too few vehicles leave gaps, too many cause route-discovery floods and contention. "
    "The sweet spot moves to fewer vehicles when the range is longer.",
    "Lower loss does not always mean lower delay: at 50 kbit/s per flow PDR is the highest of the load sweep but "
    "the delay is also the highest.",
    "Run-to-run variation is large, so several seeds are essential. A single seed can even show the opposite of "
    "the trend (100 vehicles with seed 1).",
    "The combination of the best values works (PDR 36.0% to 59.1%), but the gains do not add up: the measured "
    f"PDR is about {EST - float(o['pdr_mean']):.0f} points below the multiplicative estimate.",
]:
    bullet(t)

# =========================================================================== CHAPTER 10
chapter(10, "Conclusion")
para(f"<b>Main findings.</b> In our highway VANET with AODV over IEEE 802.11p, communication range had the "
     f"strongest effect on delivery: PDR rose from {f1(S[('range', 50.0)]['pdr_mean'])}% at 50 m to "
     f"{f1(S[('range', 250.0)]['pdr_mean'])}% at 250 m and the delay fell from "
     f"{f1(S[('range', 50.0)]['delayMs_mean'])} ms to {f1(S[('range', 250.0)]['delayMs_mean'])} ms. Higher speed "
     f"lowered PDR ({f1(S[('speed', 10.0)]['pdr_mean'])}% to {f1(S[('speed', 25.0)]['pdr_mean'])}%) and raised the "
     f"delay ({f1(S[('speed', 10.0)]['delayMs_mean'])} to {f1(S[('speed', 25.0)]['delayMs_mean'])} ms). A higher "
     f"load raised the delivered throughput ({f1(S[('load', 50.0)]['throughputKbps_mean'])} to "
     f"{f1(S[('load', 750.0)]['throughputKbps_mean'])} kbit/s per flow) but lowered the share delivered "
     f"({f1(S[('load', 50.0)]['pdr_mean'])}% to {f1(S[('load', 750.0)]['pdr_mean'])}%). Density helped up to 60–80 "
     "vehicles and then hurt. A second variation with a different baseline and eight seeds confirmed these trends "
     "and showed that the gain from range levels off above about 225 m.")
para(f"<b>Optimal solution.</b> Combining the best value of each factor (80 vehicles, 10 m/s, 50 kbit/s per flow, "
     f"250 m) and measuring it over ten seeds raised PDR from {f1(b['pdr_mean'])}% to {f1(o['pdr_mean'])}%, cut the "
     f"delay from {f1(b['delayMs_mean'])} ms to {f1(o['delayMs_mean'])} ms and made the result much more "
     f"consistent (standard deviation {f1(b['pdr_std'])} to {f1(o['pdr_std'])} points). It is "
     f"{EST - float(o['pdr_mean']):.0f} points below the {EST:.0f}% that multiplying the single-factor gains "
     "predicts. The leave-one-out runs show why: speed, load and range each still add 6–8 points, but density no "
     "longer helps once the range is long, and 60 vehicles do as well as 80.")
para("<b>Contribution.</b> We built a reproducible 802.11p and AODV highway scenario for current ns-3 without the "
     "removed wave module, measured the four factors with several seeds and error bars, found and fixed a mobility "
     "bug that had stopped most vehicles, and measured, rather than estimated, the combined optimal configuration "
     "and the contribution of each factor to it. This answers the research gap chosen in Chapter 5.")
para("<b>Limitations.</b> (1) The radio reaches exactly r metres; there is no fading, shadowing or obstacles, so "
     "the absolute PDR values are specific to this model. (2) Vehicles drive at constant velocity on a straight "
     "road; there is no car-following, lane changing or junctions. (3) Traffic is unicast constant-rate UDP between "
     "random pairs, not the periodic broadcast beacons of real safety applications. (4) Only AODV with default "
     "settings is tested. (5) The ad hoc MAC is used instead of the 802.11p OCB mode. (6) The optimum was searched "
     "one factor at a time over a few tested values; a full grid could find a slightly better combination. "
     "(7) The delay peak at 50 kbit/s is not explained. (8) Even with 5–10 seeds the error bars are wide. (9) These "
     "are network metrics: they show whether safety messages arrive reliably and in time, but they do not by "
     "themselves show that real crashes or congestion are reduced.")
para("<b>Future work.</b> (a) Use a realistic propagation model (for example Nakagami fading) instead of the hard "
     "range. (b) Drive the vehicles with SUMO, through ns-3's trace support or Veins [18], [19]. (c) Compare AODV "
     "with other routing protocols such as OLSR, DSDV and GPSR, and with broadcast safety beacons. (d) Search the "
     "four factors jointly on a grid around the optimum, with more seeds. (e) Add roadside units, and finally "
     "test on real 802.11p hardware.")

# =========================================================================== CHAPTER 11
chapter(11, "References")
REFS = [
    "M. Malnar and N. Jevtić, “A framework for performance evaluation of VANETs using NS-3 simulator,” "
    "<i>Promet – Traffic &amp; Transportation</i>, vol. 32, no. 2, pp. 255–268, 2020, doi: 10.7307/ptt.v32i2.3227.",
    "H. Hartenstein and K. P. Laberteaux, “A tutorial survey on vehicular ad hoc networks,” <i>IEEE Commun. "
    "Mag.</i>, vol. 46, no. 6, pp. 164–171, Jun. 2008.",
    "G. Karagiannis, O. Altintas, E. Ekici, G. Heijenk, B. Jarupan, K. Lin, and T. Weil, “Vehicular networking: "
    "A survey and tutorial on requirements, architectures, challenges, standards and solutions,” <i>IEEE Commun. "
    "Surveys Tuts.</i>, vol. 13, no. 4, pp. 584–616, 4th Quart. 2011.",
    "J. B. Kenney, “Dedicated short-range communications (DSRC) standards in the United States,” <i>Proc. "
    "IEEE</i>, vol. 99, no. 7, pp. 1162–1182, Jul. 2011.",
    "D. Jiang and L. Delgrossi, “IEEE 802.11p: Towards an international standard for wireless access in vehicular "
    "environments,” in <i>Proc. IEEE Vehicular Technology Conf. (VTC Spring)</i>, Singapore, 2008, "
    "pp. 2036–2040.",
    "<i>IEEE Standard for Information Technology – Part 11: Wireless LAN Medium Access Control (MAC) and Physical "
    "Layer (PHY) Specifications, Amendment 6: Wireless Access in Vehicular Environments</i>, IEEE Std "
    "802.11p-2010, Jul. 2010.",
    "C. E. Perkins and E. M. Royer, “Ad-hoc on-demand distance vector routing,” in <i>Proc. 2nd IEEE Workshop on "
    "Mobile Computing Systems and Applications (WMCSA)</i>, New Orleans, LA, USA, 1999, pp. 90–100.",
    "C. Perkins, E. Belding-Royer, and S. Das, “Ad hoc On-Demand Distance Vector (AODV) routing,” IETF, RFC 3561, "
    "Jul. 2003.",
    "F. Li and Y. Wang, “Routing in vehicular ad hoc networks: A survey,” <i>IEEE Veh. Technol. Mag.</i>, "
    "vol. 2, no. 2, pp. 12–22, Jun. 2007.",
    "J. Broch, D. A. Maltz, D. B. Johnson, Y.-C. Hu, and J. Jetcheva, “A performance comparison of multi-hop "
    "wireless ad hoc network routing protocols,” in <i>Proc. ACM/IEEE MobiCom</i>, Dallas, TX, USA, 1998, "
    "pp. 85–97.",
    "S.-Y. Ni, Y.-C. Tseng, Y.-S. Chen, and J.-P. Sheu, “The broadcast storm problem in a mobile ad hoc network,” "
    "in <i>Proc. ACM/IEEE MobiCom</i>, Seattle, WA, USA, 1999, pp. 151–162.",
    "N. Wisitpongphan, F. Bai, P. Mudalige, V. Sadekar, and O. Tonguz, “Routing in sparse vehicular ad hoc "
    "wireless networks,” <i>IEEE J. Sel. Areas Commun.</i>, vol. 25, no. 8, pp. 1538–1556, Oct. 2007.",
    "J. Härri, F. Filali, and C. Bonnet, “Mobility models for vehicular ad hoc networks: A survey and taxonomy,” "
    "<i>IEEE Commun. Surveys Tuts.</i>, vol. 11, no. 4, pp. 19–41, 4th Quart. 2009.",
    "F. Bai, N. Sadagopan, and A. Helmy, “IMPORTANT: A framework to systematically analyze the impact of mobility "
    "on performance of routing protocols for adhoc networks,” in <i>Proc. IEEE INFOCOM</i>, San Francisco, CA, "
    "USA, 2003, vol. 2, pp. 825–835.",
    "G. Bianchi, “Performance analysis of the IEEE 802.11 distributed coordination function,” <i>IEEE J. Sel. "
    "Areas Commun.</i>, vol. 18, no. 3, pp. 535–547, Mar. 2000.",
    "P. Gupta and P. R. Kumar, “The capacity of wireless networks,” <i>IEEE Trans. Inf. Theory</i>, vol. 46, "
    "no. 2, pp. 388–404, Mar. 2000.",
    "M. Torrent-Moreno, D. Jiang, and H. Hartenstein, “Broadcast reception rates and effects of priority access in "
    "802.11-based vehicular ad-hoc networks,” in <i>Proc. 1st ACM Int. Workshop on Vehicular Ad Hoc Networks "
    "(VANET)</i>, Philadelphia, PA, USA, 2004, pp. 10–18.",
    "C. Sommer, R. German, and F. Dressler, “Bidirectionally coupled network and road traffic simulation for "
    "improved IVC analysis,” <i>IEEE Trans. Mobile Comput.</i>, vol. 10, no. 1, pp. 3–15, Jan. 2011.",
    "D. Krajzewicz, J. Erdmann, M. Behrisch, and L. Bieker, “Recent development and applications of SUMO – "
    "Simulation of Urban MObility,” <i>Int. J. Adv. Syst. Meas.</i>, vol. 5, no. 3&amp;4, pp. 128–138, 2012.",
    "G. F. Riley and T. R. Henderson, “The ns-3 network simulator,” in <i>Modeling and Tools for Network "
    "Simulation</i>, K. Wehrle, M. Güneş, and J. Gross, Eds. Berlin, Germany: Springer, 2010, pp. 15–34.",
    "G. Carneiro, P. Fortuna, and M. Ricardo, “FlowMonitor: A network monitoring framework for the network "
    "simulator 3 (NS-3),” in <i>Proc. 4th Int. ICST Conf. Performance Evaluation Methodologies and Tools "
    "(VALUETOOLS)</i>, Pisa, Italy, 2009.",
    "W. R. Stevens, B. Fenner, and A. M. Rudoff, <i>UNIX Network Programming, Volume 1: The Sockets Networking "
    "API</i>, 3rd ed. Boston, MA, USA: Addison-Wesley, 2003.",
    "Linux man-pages project, “socket(7)” and “udp(7),” online documentation, https://man7.org/linux/man-pages/.",
    "ns-3 Consortium, “ns-3 documentation: wifi, aodv, flow-monitor and netanim modules,” release ns-3.48, "
    "https://www.nsnam.org/documentation/.",
    "T. Camp, J. Boleng, and V. Davies, “A survey of mobility models for ad hoc network research,” <i>Wireless "
    "Commun. Mobile Comput.</i>, vol. 2, no. 5, pp. 483–502, 2002.",
]
for i, r in enumerate(REFS, 1):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.left_indent = Inches(0.45)
    pf.first_line_indent = Inches(-0.45)
    pf.tab_stops.add_tab_stop(Inches(0.45), WD_TAB_ALIGNMENT.LEFT)
    pf.space_after = Pt(4)
    pf.line_spacing = 1.15
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    runs(p, f"[{i}]\t" + r.replace("&amp;", "&"), size=11)

# --------------------------------------------------------------------------- figure / table lists
def insert_after(anchor, items, key_prefix):
    last = anchor
    for left, title in items:
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_after = Pt(0)
        pf.line_spacing = 1.15
        pf.left_indent = Inches(0.95)
        pf.first_line_indent = Inches(-0.95)
        pf.tab_stops.add_tab_stop(Inches(0.95), WD_TAB_ALIGNMENT.LEFT)
        pf.tab_stops.add_tab_stop(Inches(TEXT_W), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        runs(p, f"{left}\t{title}\t{PAGES.get(left, '0')}", size=10.5)
        last._p.addnext(p._p)
        last = p


insert_after(toc_tab_anchor, TABLIST, "t")
insert_after(toc_fig_anchor, FIGLIST, "f")

doc.core_properties.title = TITLE
doc.core_properties.author = ", ".join(n for n, _ in TEAM)
doc.save(OUT)
json.dump({"figs": FIGLIST, "tabs": TABLIST, "chapters": [c for c, _ in CHAPTERS],
           "sections": [s for _, ss in CHAPTERS for s in ss]}, open(OUT + ".keys.json", "w"))
print("saved", OUT, len(FIGLIST), "figures", len(TABLIST), "tables")
