# CONNECTIFYU - College Event Management System

CONNECTIFYU is a centralized web platform designed for colleges to manage campus events, announcements, registrations, and student engagement smoothly.

---

## 🚀 Setup Steps (Day One Setup)

Follow these steps to set up the project locally:

### 1. Clone the Repository
```bash
git clone https://github.com/ayush22singh22-sys/CONNECTIFYU.git
cd CONNECTIFYU
```

### 2. Create and Activate Virtual Environment
- **Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```
- **macOS / Linux:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to create your local `.env`:
```bash
cp .env.example .env
```
Update `.env` values (e.g., set your `SECRET_KEY`, `DEBUG=True`, email credentials).

### 5. Database Migrations
```bash
python manage.py migrate
```

### 6. Run Development Server
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000/` in your browser.

---

## 🌿 Branching Strategy & Git Rules

Sabhi teammates ko ye rules strictly follow karne hain:

### Branch Roles
1. **`main`**:
   - Production / Stable release branch.
   - Protected: Direct push prohibited, require Pull Request (PR) with review.
2. **`develop`**:
   - Primary active development & integration branch.
   - All feature PRs target `develop`.
3. **`feature/<role>-<kaam>`**:
   - Individual task branches created off `develop`.

---

### Workflow Step-by-Step

#### 1. Always pull latest `develop` branch first:
```bash
git checkout develop
git pull origin develop
```

#### 2. Create your feature branch:
Naming rule: `feature/<role>-<kaam>`
Examples:
- `feature/admin-create-event`
- `feature/student-registration`
- `feature/auth-jwt-login`
- `feature/ui-dashboard-redesign`

```bash
git checkout -b feature/<role>-<kaam>
```

#### 3. Commit your work:
```bash
git add .
git commit -m "feat: description of work done"
```

#### 4. Push your branch to GitHub:
```bash
git push -u origin feature/<role>-<kaam>
```

#### 5. Open Pull Request (PR):
- GitHub pe jao aur **Pull Request** create karo.
- **Base branch**: `develop` (DO NOT target `main` directly).
- Team members se review lo aur approve hone ke baad merge karo.

---

## 📁 Project Structure Highlights
- `.env.example`: Template for environment variables (never commit `.env`).
- `requirements.txt`: Project dependencies (includes `python-decouple`).
- `docs/phase4-revisit.md`: Notes on Phase 4 architectural updates (Postgres & Cloudinary).
- `db.sqlite3` & `media/`: Ignored in git by default.
