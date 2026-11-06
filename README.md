# College Event Management System (CEMS)

A Django-based web platform designed to streamline, track, and automate college event approvals and verified student attendance.

---

## 🚀 Key Features

1. **5-Stage Dynamic Approval Pipeline**:
   - **Stage 1 (Unit Head)**: Dynamically resolves to Department Head (HOD) for academic proposals or Club President for society events.
   - **Stage 2 (HR Review)**: Scheduling, leave, and staffing oversight.
   - **Stage 3 (Dean of Research)**: Keynote speaker vetting and intellectual/academic merit review.
   - **Stage 4 (Dean of Accounts)**: Budget scrutiny with the unique ability to **revise allocations with written reasoning**.
   - **Stage 5 (Dean of Academics / Director)**: Executive approval triggering automated operational logistics emails.

2. **Revision Cycle Tracking**:
   - When any approver requests revisions or rejects, written remarks are mandatory.
   - Proposers can edit and resubmit; the proposal re-routes through the full chain with a clear **`Revision Cycle N`** badge and previous remark history.

3. **Automated Campus Logistics Hook**:
   - Stage 5 clearance automatically records and emails notifications to **Mess / Catering**, **Transport / Fleet**, and **Auditorium / AV Maintenance** teams with exact timestamps and requirements.

4. **Anti-Proxy Live Check-In (QR Code + Front Selfie)**:
   - Event coordinators launch a large, high-contrast QR display for projector screens.
   - Students scan the QR code and must capture a live front-camera selfie (`navigator.mediaDevices.getUserMedia`) to eliminate proxy check-ins.

5. **Guaranteed Feedback Loop**:
   - Attendance status remains `CHECKED_IN` until the student completes a structured 3-factor feedback survey.
   - Upon survey submission, attendance flips to **`VERIFIED`**, ensuring high institutional survey participation rates.

6. **Post-Event Compliance & Audit Report**:
   - Aggregates budgeted vs. actual allocation, turnout metrics, and average ratings with qualitative feedback for easy printing or PDF export.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.12, Django 6.1
- **Database**: SQLite
- **Frontend**: HTML5, Tailwind CSS, Vanilla JavaScript
- **Hardware/APIs**: HTML5 Camera API (`MediaDevices.getUserMedia`), QR generation via `qrcode` + `Pillow`
- **Cost**: 100% Free & Open Source

---

## ⚡ Quickstart Guide

### 1. Run the Development Server
```powershell
cd C:\Users\abhis\.gemini\antigravity\scratch\college_event_system
python manage.py runserver
```
Visit **`http://127.0.0.1:8000/`** in your browser.

### 2. Reset or Re-seed Demo Data at Any Time
```powershell
python manage.py seed_data
```

---

## 👥 Demo Accounts & Personas (Password: `password123`)

The application includes an **instant identity switcher bar** at the top of every page, or you can log in manually with:

| Persona | Username | Role / Department | Responsibility |
|:---|:---|:---|:---|
| **Prof. Alan Turing** | `faculty` | Faculty / Computer Science | Files proposals, launches live QR screen, views compliance |
| **Dr. Grace Hopper** | `hod_cs` | HOD / Computer Science | Stage 1 Approver for CS Department proposals |
| **Alex Johnson** | `club_head` | Club President / Robotics | Stage 1 Approver for Club proposals |
| **Sarah Jenkins** | `hr_admin` | Human Resources (HR) | Stage 2 Approver (Timetable & staff duty leave) |
| **Dr. Richard Feynman** | `dean_research` | Dean of Research | Stage 3 Approver (Speaker vetting & academic merit) |
| **Dr. Milton Friedman** | `dean_accounts` | Dean of Accounts | Stage 4 Approver (Budget adjustments & reasons) |
| **Dr. APJ Kalam** | `dean_academics` | Dean of Academics / Director | Stage 5 Final Clearance (Triggers logistics emails) |
| **John Doe** | `student1` | Student (CS21B001) | Registers for events, performs selfie check-in & feedback |
| **Jane Smith** | `student2` | Student (ME21B015) | Registered student volunteer |

---

## 🧪 Running Automated Tests
```powershell
python manage.py test
```
Verifies the complete 5-stage pipeline, budget revision handling, logistics notification dispatch, revision cycle counters, and the feedback verification gate.
