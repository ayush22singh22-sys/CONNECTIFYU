# College Event Management System (CEMS India)

A comprehensive Django-based web application tailored for Indian engineering colleges and universities to digitize event proposals, streamline multi-stage approvals, and guarantee authentic, anti-proxy student attendance.

---

## 🇮🇳 Indian College Institutional Framework

### 1. 3 Configurable Approval Chains + Custom Chain Option
Every proposal passes through a strictly verified approval pipeline. While preliminary approvers differ based on event type, the **Dean of Finance & Accounts**, **Dean of Academic Affairs**, and **Director of the Institute** are **strictly mandatory in all pipelines**:

1. **Option A: Academic & Research Event Chain**
   - *Best for*: National/International Conferences, Seminars, Workshops, Faculty Development Programs (FDPs).
   - *Flow*: `Head of Department (HOD)` &rarr; `Dean (R&D)` &rarr; `Dean (Finance & Accounts)*` &rarr; `Dean (Academic Affairs)*` &rarr; `Director (Final Clearance)*`

2. **Option B: Student Club, Cultural & Sports Fest Chain**
   - *Best for*: Technical Fests (Hackathons), Cultural Celebrations, Society Contests, Inter-College Derbies.
   - *Flow*: `Faculty Advisor / Club In-Charge` &rarr; `Dean of Student Welfare (DSW)` &rarr; `Dean (Finance & Accounts)*` &rarr; `Dean (Academic Affairs)*` &rarr; `Director (Final Clearance)*`

3. **Option C: Institute-Wide Mega Event & Conclave Chain**
   - *Best for*: Annual Convocation, Foundation Day, Industry-Academia Conclaves.
   - *Flow*: `Registrar (HR & Admin)` &rarr; `Dean (Research & Planning)` &rarr; `Dean (Finance & Accounts)*` &rarr; `Dean (Academic Affairs)*` &rarr; `Director (Final Clearance)*`

4. **Option D: Custom Approval Chain Builder**
   - Organizers can select any combination of preliminary approvers (HOD, Club In-charge, Registrar, Dean R&D, Dean Student Welfare).
   - **Statutory Gate**: `Dean (Finance)` &rarr; `Dean (Academics)` &rarr; `Director` are permanently locked into the chain as the final stages to guarantee institute compliance.

---

### 2. Role-Scoped Portals & Default Dashboard Routing
- **Clean Dashboard Default**: Switching roles via the top identity bar immediately routes the user directly to their entity dashboard (`/`).
- **Student Dashboard**: Shows registered campus events, verification certificates, pending check-ins, and upcoming fests. Students are strictly prohibited from proposing or publishing events.
- **Approver Dashboard**: Features a prominent **Pending Review Queue** highlighting proposals awaiting their specific review stage.

---

### 3. Financial Scrutiny in Indian Rupees (₹ INR)
- Proposals capture requested budget in Indian Rupees (`₹`).
- **Dean of Finance & Accounts** has special statutory authority during their stage to revise and sanction the budget amount with a recorded justification.

---

### 4. Anti-Proxy Attendance & Guaranteed Feedback Gate
- **Dynamic Projected QR**: Faculty beam the event QR code onto the auditorium projector screen.
- **Front-Camera Selfie**: Students scan with their phone and must take a live front-camera selfie using the HTML5 `MediaDevices.getUserMedia()` API to eliminate proxy sign-ins.
- **Feedback Gatekeeper**: Attendance is held at `CHECKED_IN` until the student submits a 3-category 5-star feedback survey, upon which it flips to **`VERIFIED`** (ensuring 100% feedback collection).

---

### 5. Automated Operational Logistics Dispatch
Upon the Director's final clearance, the system automatically emails formal work orders to:
- **Hostel Mess & Catering**: `catering.mess@college.ac.in`
- **Transport & Vehicle Fleet**: `estate.transport@college.ac.in`
- **Auditorium, Estate, AV & Genset**: `maintenance.av@college.ac.in`

---

## 👥 Authentic Indian Personas (Password: `password123`)

| Persona | Username | Role / Department | Responsibilities |
| :--- | :--- | :--- | :--- |
| **Prof. Rajesh Sharma** | `faculty` | Faculty Coordinator (CSE Dept) | Drafts proposals, selects approval chains, projects live QR |
| **Dr. K. V. Ramanathan** | `hod_cse` | Head of Department (HOD CSE) | Stage 1 Approver for Academic proposals |
| **Prof. Priya Nair** | `club_lead` | Faculty Advisor (Robotics Society) | Stage 1 Approver for Club / Technical fest events |
| **Smt. Sunita Deshmukh** | `registrar` | Registrar (Admin & Establishment) | Stage 1 Approver for Institute-wide mega events |
| **Dr. P. Venkatraman** | `dean_research` | Dean of Research & Consultancy (R&D) | Keynote speaker vetting & academic review |
| **Dr. Alok Sen** | `dean_dsw` | Dean of Student Welfare (DSW) | Student affairs & festival safety clearance |
| **Dr. Suresh Chandra** | `dean_finance` | Dean of Finance & Accounts (Mandatory) | Budget sanction & revision in Indian Rupees (₹) |
| **Dr. Meenakshi Sundaram** | `dean_academics` | Dean of Academic Affairs (Mandatory) | Academic calendar alignment & duty leave clearance |
| **Dr. R. Chidambaram** | `director` | Director of the Institute (Mandatory) | Executive clearance & automated logistics trigger |
| **Aarav Patel** | `student1` | Student (21BCSE101) | Event registration, selfie check-in, feedback submission |
| **Ananya Sen** | `student2` | Student (21BECE034) | Verified student attendee |

---

## ⚡ Quickstart

### 1. Launch the Server
```powershell
cd C:\Users\abhis\.gemini\antigravity\scratch\college_event_system
python manage.py runserver
```
Visit **`http://127.0.0.1:8000/`** in your browser.

### 2. Re-seed Demo Data (At Any Time)
```powershell
python manage.py seed_data
```

### 3. Run Automated Test Suite
```powershell
python manage.py test
```
*(All 3 lifecycle test suites pass: academic chain, custom chain builder, and student permission block).*
