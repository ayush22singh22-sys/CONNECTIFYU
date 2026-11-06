# College Event Management System

A Django 6 web application for managing college events, approvals, check-ins, and compliance reporting.

## Features

- **Multi-role user system**: Faculty, HOD, Club Head, HR, Dean (Research/Accounts/Academics), Students, and Infrastructure staff
- **Event Proposal Workflow**: 5-stage approval chain (HOD/Club Head → HR → Dean of Research → Dean of Accounts → Dean of Academics)
- **QR Code Check-in**: Projected QR code at event entry; students capture selfie to check in
- **Post-event Feedback**: Rating and comments collected after check-in
- **Notifications**: Email alerts at each approval stage, revision requests, and infra staff notifications
- **Compliance Reports**: Auto-generated reports with attendance and feedback stats

## Setup

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd college-event-mgmt
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your SECRET_KEY and Gmail SMTP credentials
   ```

4. **Run migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create a superuser**
   ```bash
   python manage.py createsuperuser
   ```

6. **Start the development server**
   ```bash
   python manage.py runserver
   ```

7. Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in your browser.

## User Roles

| Role | Description |
|------|-------------|
| `faculty` | Proposes events |
| `club_head` | Proposes club events, Stage-1 approver for clubs |
| `hod` | Stage-1 approver for department events |
| `hr` | Stage-2 approver |
| `dean_research` | Stage-3 approver |
| `dean_accounts` | Stage-4 approver, reviews budgets |
| `dean_academics` | Stage-5 final approver |
| `student` | Registers for and attends events |
| `transport` | Receives transport requirement notifications |
| `mess` | Receives mess requirement notifications |
| `maintenance` | Receives maintenance requirement notifications |

## Approval Workflow

```
Faculty proposes event
        ↓
Stage 1: HOD (dept event) or Club Head (club event)
        ↓
Stage 2: HR
        ↓
Stage 3: Dean of Research
        ↓
Stage 4: Dean of Accounts (budget review)
        ↓
Stage 5: Dean of Academics / Director
        ↓
Event Published → Infra staff notified
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` for development, `False` for production |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts |
| `EMAIL_HOST` | SMTP host (default: `smtp.gmail.com`) |
| `EMAIL_PORT` | SMTP port (default: `587`) |
| `EMAIL_USE_TLS` | Use TLS (default: `True`) |
| `EMAIL_HOST_USER` | Gmail address |
| `EMAIL_HOST_PASSWORD` | Gmail App Password |
| `DEFAULT_FROM_EMAIL` | Sender email address |
