# Role

You are a Principal AI Agent Architect, Senior Python Engineer, Automation Engineer, Data Engineer, ATS Optimization Specialist, and Job Search Platform Expert.

Your responsibility is to design and implement a production-quality automated job discovery agent that searches for suitable opportunities, ranks them, tracks history, and generates Excel reports.

Always prefer simplicity, maintainability, reliability, and practical usability over unnecessary complexity.

---

# Objective

Build a fully automated job discovery agent that:

1. Runs daily at 9:00 AM IST.
2. Searches Naukri and Indeed.
3. Finds relevant jobs based on my resume and profile.
4. Scores and ranks jobs.
5. Evaluates company quality and sentiment.
6. Tracks previously discovered jobs.
7. Identifies newly discovered jobs.
8. Generates an Excel workbook.
9. Saves the workbook locally.
10. Requires minimal maintenance.

The Excel workbook is the primary deliverable.

No dashboard is required.

No web application is required.

No database is required.

---

# Candidate Profile

## Experience

6 Years 5 Months

## Current CTC

₹10.3 LPA

## Expected CTC

₹13 LPA

## Notice Period

Immediate Joiner (0 Days)

## Preferred Locations

* Remote
* Chennai
* Bengaluru
* Coimbatore
* Madurai

Location preference should influence ranking but should not exclude otherwise relevant jobs.

---

# Resume Handling

A resume PDF will be uploaded during implementation.

The system must automatically extract:

* Skills
* Certifications
* Technologies
* ATS Keywords
* Domain Experience
* Years of Experience
* Responsibilities

The extracted information should be used for job matching and ranking.

Do not require manual skill entry.

Resume-derived information should always take precedence over predefined skills.

---

# Search Sources

Search only:

1. Naukri
2. Indeed

Do not use LinkedIn.

---

# Target Roles

Search for:

* Site Reliability Engineer
* SRE Engineer
* Production Support Engineer
* Application Support Engineer
* Infrastructure Support Engineer
* Technical Support Engineer
* Cloud Support Engineer
* Platform Support Engineer
* IT Operations Engineer
* Monitoring Engineer
* Linux Support Engineer
* DevOps Support Engineer
* Operations Engineer
* L2 Support Engineer
* L3 Support Engineer

Also discover close title variations automatically.

---

# Search Strategy

Use combinations of:

* SRE
* Site Reliability Engineering
* Production Support
* Application Support
* Linux Support
* Infrastructure Support
* AWS Support
* Monitoring
* Cloud Support
* IT Operations
* Technical Support
* Incident Management
* Troubleshooting
* Platform Support
* Reliability Engineering

Prioritize jobs posted within:

* Last 24 Hours
* Last 3 Days
* Last 7 Days
* Last 14 Days

Older jobs may be included only when highly relevant.

---

# Company Inclusion Rules

Include:

* Product Companies
* Service Companies
* Consulting Companies
* Startups
* Enterprises
* Mass Hiring Opportunities

Do not exclude opportunities solely because they are:

* Mass hiring
* Consulting positions
* Service-based companies

The most important factor is role relevance.

Remote jobs are preferred but not mandatory.

Direct company hiring is preferred but not mandatory.

Positive employee reviews are preferred but not mandatory.

---

# Company Evaluation

When information is available, collect:

* Company Name
* Industry
* Company Type
* Employee Rating
* Review Count
* Sentiment

Classify sentiment as:

* Positive
* Neutral
* Negative
* Unknown

Never fabricate ratings, review counts, or sentiment.

If information is unavailable, mark it as:

Unknown

---

# Ranking Algorithm

Calculate a Match Score out of 100.

Weighting:

## Skill Match

40%

## Experience Match

20%

## ATS Compatibility

15%

## Job Relevance

10%

## Company Assessment

10%

## Location Preference

5%

Sort jobs by Match Score descending.

---

# Application URL Rules

The goal is to provide the most useful application URL possible.

## Scenario 1

If the application can be completed directly on Naukri:

* Store the Naukri job posting URL.
* Apply Type = Naukri Apply.

## Scenario 2

If the application can be completed directly on Indeed:

* Store the Indeed job posting URL.
* Apply Type = Indeed Apply.

## Scenario 3

If the Naukri or Indeed listing redirects to a company career page:

Store the final company job application URL.

Examples:

* Workday Job URL
* Greenhouse Job URL
* Lever Job URL
* Taleo Job URL
* SmartRecruiters Job URL
* SuccessFactors Job URL
* Company ATS Job URL

Do not store:

* Company Homepage
* Generic Careers Page
* Redirect Landing Page

Apply Type = Company Career Site.

## Scenario 4

If the application redirects to a third-party ATS platform:

Store the final ATS application URL.

Apply Type = External Application Site.

---

# URL Priority

Always store the highest-priority actionable URL:

1. Final Company Application URL
2. Final ATS Application URL
3. Naukri Job URL
4. Indeed Job URL

The stored URL must correspond to the specific job posting whenever possible.

---

# Historical Tracking

Do not use any database.

Specifically do not use:

* SQLite
* PostgreSQL
* MySQL
* MongoDB
* Redis

Use a CSV file for persistence.

File:

data/jobs_history.csv

Automatically create the file if it does not exist.

---

# CSV Structure

Columns:

* company
* role
* location
* final_apply_url
* source
* first_seen
* last_seen
* latest_match_score

---

# Unique Identifier

Use:

company + role + location + final_apply_url

as the unique identifier.

Use this identifier for:

* Duplicate detection
* New-job detection
* History tracking

---

# Daily Processing Workflow

1. Load jobs_history.csv.
2. Search Naukri and Indeed.
3. Collect matching jobs.
4. Score jobs.
5. Compare against history.
6. Mark newly discovered jobs.
7. Update existing jobs.
8. Save updated history.
9. Generate Excel workbook.

---

# Excel Output

Generate:

Job_Search_Report_YYYY_MM_DD.xlsx

Save automatically to the configured output folder.

---

# Worksheet 1

Top 20 Jobs Overall

Columns:

| Rank | Company | Role | Location | Experience Required | Salary | Match Score | Rating | Sentiment | Apply Type | Final Apply URL | Source |

Sort by Match Score descending.

---

# Worksheet 2

Top 20 Direct Company Career Site Jobs

Filter:

Apply Type = Company Career Site

Columns:

| Rank | Company | Role | Location | Experience Required | Salary | Match Score | Rating | Sentiment | Final Apply URL | Source |

Sort by Match Score descending.

---

# Worksheet 3

New Jobs Since Previous Run

Include only jobs not previously present in jobs_history.csv.

Columns:

| Company | Role | Date Found | Final Apply URL |

---

# Worksheet 4

Skill Insights & ATS Recommendations

Include:

## Most Requested Skills

## Trending Technologies

## Missing Skills

## Frequently Requested Certifications

## ATS Keyword Recommendations

ATS recommendations must appear only in this worksheet.

---

# Folder Structure

Recommended structure:

JobIntel-Agent/

├── docs/
│   └── requirements.md
│
├── resume/
│   └── resume.pdf
│
├── data/
│   └── jobs_history.csv
│
├── output/
│   └── Job_Search_Report_YYYY_MM_DD.xlsx
│
├── logs/
│   └── agent.log
│
├── config/
│   └── settings.yaml
│
└── src/

---

# Error Handling

If a source is unavailable:

* Continue using available sources.
* Log the failure.
* Generate the report anyway.

If salary is unavailable:

Use:

Not Specified

If ratings are unavailable:

Use:

Unknown

If sentiment is unavailable:

Use:

Unknown

---

# Constraints

1. Do not fabricate jobs.
2. Do not fabricate salaries.
3. Do not fabricate ratings.
4. Do not fabricate review counts.
5. Do not fabricate URLs.
6. Deduplicate results.
7. Prefer recent jobs.
8. Validate URLs when possible.
9. Keep the solution lightweight.
10. Avoid unnecessary infrastructure.
11. Avoid databases.
12. Use CSV-based persistence.

---

# Output Requirements

Before generating any code:

1. Analyze requirements.
2. Identify ambiguities.
3. Identify implementation risks.
4. Propose architecture.
5. Propose folder structure.
6. Propose CSV design.
7. Propose job search strategy.
8. Propose ranking algorithm.
9. Propose scheduling mechanism.
10. Recommend implementation approach.

Wait for approval.

Do not generate code until architecture approval is received.

After approval:

Generate complete production-ready code with:

* Python 3.12+
* Poetry dependency management
* Resume parsing
* Naukri integration
* Indeed integration
* CSV history management
* Excel generation
* Structured logging
* YAML configuration
* Scheduling
* Error handling
* Documentation
* Setup instructions
* README

All code should be modular, maintainable, and ready for local execution.
