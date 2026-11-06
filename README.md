# College Event Management System (CEMS India)

A comprehensive Django-based web platform designed for Indian engineering colleges and universities to automate event proposal approvals, manage institutional scrutiny, and enforce anti-proxy student attendance.

---

## 🚀 Key Implemented Features

### 1. Pre-Provisioned Institutional Database (No Self-Registration)
- **Zero Public Sign-Ups**: All student, faculty, HOD, and dean accounts are pre-provisioned in the institutional database. This prevents unauthenticated users from assuming administrative or student roles.
- **Superadmin Management**: The superadmin (`admin`) has full access to the **Institutional User Directory** (`/superadmin/users/`) and the **Django Admin Portal** (`/admin/`) to add, update, or remove users, assign departments, and reset credentials.

### 2. Faculty Poster Upload & Final Publish Gate
- Once the **Director of the Institute** grants final executive clearance, the event is **not automatically published** to students.
- The proposal enters **`Approved (Pending Poster & Publish)`** status.
- The faculty coordinator is given a dedicated publishing screen to:
  - Upload an official event banner/poster image (or pick from curated themes).
  - Review the final approved budget and logistics dispatches.
  - Click the final **"Publish Event to Campus Portal"** button.
- Only after this step does the event appear on the Student Portal for registration.

### 3. Dynamic Rotating QR Code for Anti-Proxy Attendance
- On the auditorium projector screen (`/events/<id>/live/`), the QR code **rotates automatically every 20 seconds** with an animated countdown ring.
- Generated using a time-window HMAC signature (`ROTATION_INTERVAL = 20s`).
- **Replay Protection**: If a student takes a photo of the QR code and sends it to an absent friend via WhatsApp/Telegram, the token expires in 20 seconds and the server rejects the late check-in.
- **Selfie Verification**: Valid scan triggers the live front-camera selfie capture.
- **Feedback Gate**: Attendance flips from `CHECKED_IN` to `VERIFIED` only after completing a mandatory 3-factor feedback survey.

### 4. 3 Pre-Set Approval Chains + Custom Chain Builder
- **Option A (Academic/Research)**: `HOD` &rarr; `Dean (R&D)` &rarr; `Dean (Finance)*` &rarr; `Dean (Academics)*` &rarr; `Director*`
- **Option B (Student Club/Fest)**: `Club Advisor` &rarr; `Dean (Student Welfare)*` &rarr; `Dean (Finance)*` &rarr; `Dean (Academics)*` &rarr; `Director*`
- **Option C (Institute Mega Event)**: `Registrar` &rarr; `Dean (Research/Planning)` &rarr; `Dean (Finance)*` &rarr; `Dean (Academics)*` &rarr; `Director*`
- **Option D (Custom Chain)**: Publisher selects custom initial reviewers; `Dean (Finance)`, `Dean (Academics)`, and `Director` are locked as mandatory.

---

## 👥 Pre-Provisioned Demo Accounts (Password: `password123`)

| Username | Role | Full Name & Department | Notes |
|:---|:---|:---|:---|
| **`admin`** | **Superadmin** | Central Administrator (IT Centre) | Full access to `/admin/` and `/superadmin/users/` |
| **`faculty`** | **Faculty** | Prof. Rajesh Sharma (CSE Dept) | Proposes events, uploads poster, publishes to campus |
| **`faculty_ece`** | **Faculty** | Dr. Arvind Swaminathan (ECE Dept) | Coordinator for ECE Department events |
| **`hod_cse`** | **HOD** | Dr. K. V. Ramanathan (HOD CSE) | Stage 1 Approver for CSE events |
| **`hod_ece`** | **HOD** | Dr. Sunita Kulkarni (HOD ECE) | Stage 1 Approver for ECE events |
| **`hod_mech`** | **HOD** | Dr. Vikramaditya Rathore (HOD Mech) | Stage 1 Approver for Mechanical events |
| **`club_lead`** | **Club Head** | Prof. Priya Nair (Robotics Society) | Faculty Advisor for student club events |
| **`registrar`** | **Registrar** | Smt. Sunita Deshmukh (Admin/HR) | Approver for Institute-wide conclaves |
| **`dean_research`**| **Dean** | Dr. P. Venkatraman (Dean R&D) | Speaker vetting & academic review |
| **`dean_dsw`** | **Dean** | Dr. Alok Sen (Dean Student Welfare) | Club & festival safety review |
| **`dean_finance`** | **Dean (Mandatory)** | Dr. Suresh Chandra (Dean Finance) | Budget sanction & revision in ₹ INR |
| **`dean_academics`**| **Dean (Mandatory)** | Dr. Meenakshi Sundaram (Dean Academics) | Academic schedule & duty leaves |
| **`director`** | **Director (Mandatory)**| Dr. R. Chidambaram (Director) | Final executive clearance & logistics hook |
| **`student1`** | **Student** | Aarav Patel (21BCSE101 - CSE) | Pre-enrolled student attendee |
| **`student2`** | **Student** | Ananya Sen (21BECE034 - ECE) | Pre-enrolled verified volunteer |
| **`student3`** | **Student** | Rohan Gupta (22BMEE012 - Mech) | Pre-enrolled student participant |

---

## ⚡ Quickstart

### 1. Start Server
```powershell
cd C:\Users\abhis\.gemini\antigravity\scratch\college_event_system
python manage.py runserver
```
Visit **`http://127.0.0.1:8000/`** in your browser.

### 2. Live Demo Testing Steps:
1. **Test Poster Upload & Publish**:
   - Switch to **`faculty`** (Prof. Rajesh Sharma).
   - In "My Event Proposals", notice `NCGAIS-2026` has status **"Approved by Director (Awaiting Faculty Poster & Publish)"**.
   - Click **"Publish Event"**, select or upload a poster, and click **"Publish Event to Campus Portal"**.
   - Notice it is now officially live on the campus portal!
2. **Test Rotating QR Code**:
   - For any approved event (`TechKriti 2026`), click **"Project QR"**.
   - Watch the dynamic QR code automatically rotate and the countdown ring reset every 20 seconds.
3. **Test Anti-Proxy Selfie & Feedback**:
   - Switch to **`student1`** (Aarav Patel).
   - Click **"Live QR Check-In"** or scan from another window.
   - Capture a live selfie and submit the 3-category feedback form to unlock the official **`VERIFIED`** attendance certificate!
4. **Test Superadmin Control**:
   - Switch to **`admin`**.
   - Access **"User Directory"** from the navigation bar or visit `/admin/` to inspect, add, or edit students and faculty.

### 3. Run Automated Tests
```powershell
python manage.py test
```
*(All test suites pass successfully).*
