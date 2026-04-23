# Tele CRM Project Workflow Guide

This document defines the end-to-end workflow for the **Interior Design CRM** platform, describing how data flows from initial lead capture to project completion.

---

## 1. The Lead Lifecycle

A **Lead** is the core entity of the system. Every lead follows a structured status flow:

| Status | Description |
| :--- | :--- |
| **NEW** | Lead captured from Website, Social Media, or Referral. |
| **CONTACTED** | Sales executive has made initial contact. |
| **MEETING** | An Office, Phone, or Site meeting has been scheduled/held. |
| **QUOTATION** | A pricing proposal has been generated and sent. |
| **DISCUSSION** | Final negotiations are in progress. |
| **CLOSED** | **Success!** Deal is signed and converted to a Project. |
| **LOST** | Lead did not convert. |

---

## 2. Core Modules & Operations

### A. Meeting Management
- **Site Visit**: Physical meeting at the customer's location for measurements/analysis.
- **Office Meeting**: Consultation at the design studio.
- **Phone Consultation**: Initial discovery call.
- *Outcome*: Automatically updates lead status to `MEETING`.

### B. Quotation & Billing
- Sales creates a Quotation with itemized services (Design, Consultation, Execution).
- Statuses: `PENDING` → `APPROVED` (Leads to Deal Closed) or `REJECTED`.
- *Outcome*: Updates lead status to `QUOTATION`.

### C. Follow-up Tracker
- Automated or manual reminders for Sales Executives to call back potential clients.
- Reminders are flagged for "Priority" and "Overdue" status to ensure no lead is forgotten.

---

## 3. Project Management (Post-Sale)

When a Lead status changes to **CLOSED**, the workflow transitions from Sales to Execution:
1.  **Project Automatic/Manual Initialization**: A record is created in the `Projects` table.
2.  **Stages**: Planning → Design → Execution → Quality Check → Completed.
3.  **Project Logs**: Every update in the project stage is logged with notes for transparency.

---

## 4. User Roles & Permissions

| Role | Access Level | Responsibilities |
| :--- | :--- | :--- |
| **Admin** | Full System Access | Configure users, view all data, delete records, system settings. |
| **Manager** | Operations View | View all leads and projects, generate reports, oversee performance. |
| **Sales Executive** | Assigned Data Only | Manage their own leads, schedule meetings, create quotations. |

---

## 5. System Architecture (Technical Flow)

1.  **Data Capture**: Leads entered via UI or REST API.
2.  **UI Layer**: Django Templates (Bootstrap 5) provide a real-time dashboard with Chart.js visualization.
3.  **Logic Layer**: Django Signals automate timeline entries (e.g., when a meeting is created, an "Activity" is logged automatically).
4.  **Database**: PostgreSQL/SQLite handles ACID-compliant relationships between Leads, Meetings, and Projects.
5.  **API Layer**: Django REST Framework (DRF) allows for easy integration with future Mobile or External apps.

---

## 6. How to Use (Quick Start)
1.  **Dashboard**: Check "Today's Meetings" and "Conversion Rates".
2.  **Lead List**: Add a new lead found from social media.
3.  **Detail Page**: Add a "Meeting" log.
4.  **Quotation**: Generate a quote for ₹5,00,000.
5.  **Close Deal**: Update status to `CLOSED` and start the **Project** phase!
