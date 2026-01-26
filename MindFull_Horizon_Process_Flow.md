# MindFull Horizon - Process Flow Diagram

## 1. User Registration & Authentication Flow

```mermaid
flowchart TD
    A[User Visits Platform] --> B{New User?}
    B -->|Yes| C[Sign Up Page]
    B -->|No| D[Login Page]
    
    C --> E[Select Role: Patient/Provider]
    E --> F[Enter Details: Name, Email, Institution]
    F --> G[Set Strong Password]
    G --> H[Create Account]
    H --> I[Email Verification]
    I --> J[Account Created]
    
    D --> K[Enter Email & Password]
    K --> L[Select Role]
    L --> M{Valid Credentials?}
    M -->|No| N[Show Error Message]
    N --> D
    M -->|Yes| O{Role Match?}
    O -->|No| P[Role Mismatch Error]
    P --> D
    O -->|Yes| Q[Login Successful]
    
    J --> R[Redirect to Dashboard]
    Q --> R
    R --> S{User Role?}
    S -->|Patient| T[Patient Dashboard]
    S -->|Provider| U[Provider Dashboard]
```

## 2. Patient Journey - Mental Health Assessment Flow

```mermaid
flowchart TD
    A[Patient Dashboard] --> B[Assessment Section]
    B --> C{Assessment Type?}
    
    C -->|GAD-7| D[Anxiety Assessment]
    C -->|PHQ-9| E[Depression Assessment]
    C -->|Daily Mood| F[Mood Check-in]
    
    D --> G[7 Questions - Anxiety Symptoms]
    E --> H[9 Questions - Depression Symptoms]
    F --> I[Mood Scale 1-5 + Context]
    
    G --> J[Calculate GAD-7 Score 0-21]
    H --> K[Calculate PHQ-9 Score 0-27]
    I --> L[Record Mood Score]
    
    J --> M[AI Analysis - Severity Detection]
    K --> M
    L --> M
    
    M --> N{Severity Score?}
    N -->|0-3 Low| O[Positive Reinforcement]
    N -->|4-6 Moderate| P[Wellness Recommendations]
    N -->|7-8 High| Q[Recommend Appointment]
    N -->|9-10 Crisis| R[Emergency Protocol]
    
    O --> S[Award Points +20]
    P --> S
    Q --> T[Auto-suggest Provider]
    R --> U[Crisis Hotline Alert]
    
    S --> V[Update Gamification]
    T --> W[Schedule Appointment Flow]
    U --> X[Immediate Intervention]
    
    V --> Y[Save to Database]
    W --> Y
    X --> Y
    Y --> Z[Return to Dashboard]
```

## 3. AI-Powered Crisis Detection Flow

```mermaid
flowchart TD
    A[User Input Text] --> B[Heuristic Analysis]
    B --> C[Keyword Scanning]
    C --> D{Severe Keywords?}
    
    D -->|suicide, kill myself, end my life| E[Score +6]
    D -->|plan, intent, means| F[Score +2]
    D -->|hopeless, worthless| G[Score +3]
    D -->|panic, overwhelmed| H[Score +1]
    
    E --> I[Calculate Total Score]
    F --> I
    G --> I
    H --> I
    
    I --> J[Send to Gemini AI]
    J --> K[AI System Prompt: Dr. Anya]
    K --> L[AI Analysis with Context]
    L --> M[AI Returns JSON Response]
    
    M --> N{Parse JSON Success?}
    N -->|No| O[Use Heuristic Score]
    N -->|Yes| P[Extract AI Severity]
    
    O --> Q[Final Severity Score]
    P --> R[Max of Heuristic & AI Score]
    R --> Q
    
    Q --> S{Severity Level?}
    S -->|0-3| T[Normal Response]
    S -->|4-6| U[Supportive Response]
    S -->|7-8| V[Recommend Appointment]
    S -->|9-10| W[Emergency Hotline]
    
    T --> X[Continue Conversation]
    U --> X
    V --> Y[Provider Notification]
    W --> Z[Crisis Intervention]
    
    Y --> AA[Log Security Event]
    Z --> AA
    AA --> BB[Update User Record]
```

## 4. Provider Workflow - Patient Management Flow

```mermaid
flowchart TD
    A[Provider Dashboard] --> B[Caseload Overview]
    B --> C[Institution-based Patient Filter]
    C --> D[Patient List with Risk Levels]
    
    D --> E{Select Action?}
    E -->|View Patient| F[Patient Detail View]
    E -->|Appointments| G[Appointment Management]
    E -->|Analytics| H[Institutional Analytics]
    E -->|AI Documentation| I[Clinical Notes AI]
    
    F --> J[Patient Wellness Report]
    J --> K[Assessment History]
    K --> L[Digital Behavior Analysis]
    L --> M[Medication Adherence]
    M --> N[Risk Assessment Summary]
    
    G --> O[Pending Appointments]
    O --> P{Action on Appointment?}
    P -->|Accept| Q[Confirm Appointment]
    P -->|Reject| R[Provide Rejection Reason]
    Q --> S[Send Confirmation to Patient]
    R --> T[Notify Patient of Rejection]
    
    H --> U[Total Users Statistics]
    U --> V[Engagement Metrics]
    V --> W[High-Risk User Identification]
    W --> X[Wellness Score Trends]
    
    I --> Y[Upload Session Transcript]
    Y --> Z[AI Processes Transcript]
    Z --> AA[Generate Clinical Notes]
    AA --> BB[Review & Edit Notes]
    BB --> CC[Save to Patient Record]
    
    S --> DD[Update Database]
    T --> DD
    X --> DD
    CC --> DD
    DD --> EE[Return to Dashboard]
```

## 5. Gamification & Engagement Flow

```mermaid
flowchart TD
    A[User Completes Activity] --> B{Activity Type?}
    
    B -->|Assessment| C[Award 20 Points]
    B -->|Digital Detox Log| D[Award 15 Points]
    B -->|Medication Log| E[Award 10 Points]
    B -->|Breathing Exercise| F[Award 20 Points]
    B -->|Yoga Session| G[Award 20 Points]
    B -->|Journal Entry| H[Award 15 Points]
    
    C --> I[Update Gamification Record]
    D --> I
    E --> I
    F --> I
    G --> I
    H --> I
    
    I --> J[Check Last Activity Date]
    J --> K{Consecutive Day?}
    K -->|Yes| L[Increment Streak +1]
    K -->|No| M[Reset Streak to 1]
    
    L --> N[Update Total Points]
    M --> N
    N --> O[Check Badge Criteria]
    
    O --> P{Milestone Reached?}
    P -->|First Assessment| Q[Award "Getting Started" Badge]
    P -->|7-Day Streak| R[Award "Consistent" Badge]
    P -->|100 Points| S[Award "Achiever" Badge]
    P -->|30-Day Streak| T[Award "Dedicated" Badge]
    
    Q --> U[Add Badge to Profile]
    R --> U
    S --> U
    T --> U
    P -->|No Milestone| V[Continue]
    
    U --> W[Show Achievement Notification]
    V --> X[Update Dashboard Display]
    W --> X
    X --> Y[Save to Database]
```

## 6. Appointment Scheduling Flow

```mermaid
flowchart TD
    A[Patient Selects Schedule] --> B[View Available Providers]
    B --> C[Filter by Institution]
    C --> D[Select Provider]
    D --> E[Choose Date & Time]
    E --> F[Select Appointment Type]
    F --> G{Appointment Type?}
    
    G -->|In-Person| H[Confirm Location]
    G -->|Telehealth| I[Confirm Video Platform]
    G -->|Phone| J[Confirm Phone Number]
    
    H --> K[Add Optional Notes]
    I --> K
    J --> K
    K --> L[Submit Appointment Request]
    
    L --> M[Create Appointment Record]
    M --> N[Status: Pending]
    N --> O[Notify Provider]
    O --> P[Provider Reviews Request]
    
    P --> Q{Provider Decision?}
    Q -->|Accept| R[Status: Accepted]
    Q -->|Reject| S[Status: Rejected]
    
    R --> T[Send Confirmation to Patient]
    S --> U[Send Rejection with Reason]
    
    T --> V[Status: Booked]
    U --> W[Patient Can Reschedule]
    
    V --> X[Add to Both Calendars]
    W --> Y[Return to Scheduling]
    X --> Z[Send Reminder Notifications]
    Z --> AA[Appointment Day]
    
    AA --> BB{Appointment Type?}
    BB -->|Telehealth| CC[Launch Video Session]
    BB -->|In-Person| DD[Check-in Process]
    BB -->|Phone| EE[Initiate Call]
    
    CC --> FF[Record Session Notes]
    DD --> FF
    EE --> FF
    FF --> GG[Post-Session Follow-up]
```

## 7. Digital Detox & Wellness Tracking Flow

```mermaid
flowchart TD
    A[Patient Accesses Digital Detox] --> B[Input Screen Time Hours]
    B --> C[Rate Academic Performance 1-10]
    C --> D[Rate Social Interactions 1-10]
    D --> E[Submit Daily Log]
    
    E --> F[Calculate Correlation Scores]
    F --> G[Screen Time vs Academic Performance]
    G --> H[Screen Time vs Social Health]
    H --> I[Generate AI Insights]
    
    I --> J{Screen Time Analysis?}
    J -->|>8 hours| K[High Risk - Needs Improvement]
    J -->|6-8 hours| L[Moderate - Good Progress]
    J -->|<6 hours| M[Low Risk - Excellent]
    
    K --> N[Suggest Digital Detox Activities]
    L --> O[Encourage Current Habits]
    M --> P[Positive Reinforcement]
    
    N --> Q[Recommend: Phone-free study time]
    N --> R[Recommend: Outdoor activities]
    N --> S[Recommend: Social meetups]
    
    O --> T[Maintain balance tips]
    P --> U[Keep up great work]
    
    Q --> V[Award Engagement Points]
    R --> V
    S --> V
    T --> V
    U --> V
    
    V --> W[Update Wellness Dashboard]
    W --> X[Generate Weekly Report]
    X --> Y[Share with Provider (if consented)]
    Y --> Z[Save to Database]
```

## 8. Emergency Crisis Intervention Flow

```mermaid
flowchart TD
    A[Crisis Detected - Severity 9-10] --> B[Immediate Alert System]
    B --> C[Log Security Event]
    C --> D[Display Crisis Resources]
    
    D --> E[National Suicide Prevention Lifeline]
    E --> F[988 - Call/Text/Chat]
    F --> G[Crisis Text Line: Text HOME to 741741]
    G --> H[Campus Counseling Center Contact]
    
    H --> I[Emergency Contact Options]
    I --> J{User Response?}
    J -->|Calls Hotline| K[Monitor Session]
    J -->|Dismisses| L[Follow-up Protocol]
    J -->|No Response| M[Escalation Protocol]
    
    K --> N[Log Crisis Response]
    L --> O[Schedule Check-in in 24 hours]
    M --> P[Notify Campus Security/Counseling]
    
    N --> Q[Provider Notification]
    O --> Q
    P --> Q
    
    Q --> R[High-Priority Case Flag]
    R --> S[Immediate Provider Review]
    S --> T[Crisis Intervention Plan]
    T --> U[Follow-up Appointments]
    U --> V[Ongoing Monitoring]
```

## 9. Data Flow & AI Processing Pipeline

```mermaid
flowchart TD
    A[User Input Data] --> B[Input Validation & Sanitization]
    B --> C[Store in PostgreSQL Database]
    C --> D[Trigger AI Analysis]
    
    D --> E{Data Type?}
    E -->|Text/Chat| F[Sentiment Analysis]
    E -->|Assessment| G[Score Calculation]
    E -->|Voice Log| H[Emotion Detection]
    E -->|Journal Entry| I[Insight Generation]
    
    F --> J[Gemini API Call]
    G --> J
    H --> J
    I --> J
    
    J --> K[AI Processing with System Prompts]
    K --> L[JSON Response Parsing]
    L --> M{Valid Response?}
    
    M -->|No| N[Use Fallback Logic]
    M -->|Yes| O[Extract AI Insights]
    
    N --> P[Heuristic Analysis]
    O --> Q[Combine with Heuristic Score]
    P --> Q
    
    Q --> R[Generate Recommendations]
    R --> S[Update User Dashboard]
    S --> T[Provider Notifications (if needed)]
    T --> U[Gamification Updates]
    U --> V[Database Commit]
    
    V --> W[Real-time Dashboard Update]
    W --> X[Analytics Pipeline]
    X --> Y[Institutional Reporting]
```

## 10. System Architecture & Security Flow

```mermaid
flowchart TD
    A[User Request] --> B[Flask Application]
    B --> C[Authentication Check]
    C --> D{Authenticated?}
    
    D -->|No| E[Redirect to Login]
    D -->|Yes| F[Role-based Authorization]
    
    F --> G{Authorized?}
    G -->|No| H[Access Denied - 403]
    G -->|Yes| I[CSRF Token Validation]
    
    I --> J[Input Sanitization]
    J --> K[Rate Limiting Check]
    K --> L[Business Logic Processing]
    
    L --> M[Database Operations]
    M --> N[AI Service Calls (if needed)]
    N --> O[Response Generation]
    
    O --> P[Security Headers]
    P --> Q[Session Management]
    Q --> R[Audit Logging]
    R --> S[Return Response]
    
    E --> T[Login Flow]
    H --> U[Error Logging]
    S --> V[Client Receives Response]
```

This comprehensive process flow diagram covers all major user journeys and system processes in your MindFull Horizon platform, from user registration through crisis intervention and data processing pipelines.