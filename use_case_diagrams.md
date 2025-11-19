# Use Case Diagrams for Restaurant Management System

## UC-001: User Registration
```mermaid
sequenceDiagram
    participant V as Visitor
    participant S as System
    
    V->>S: Access registration page
    V->>S: Select user type (customer/chef/delivery)
    V->>S: Fill registration form
    S->>S: Validate form data
    S->>S: Check username uniqueness
    alt Username available
        S->>S: Create user account
        S->>S: Create role profile
        S->>V: Auto-login user
        S->>V: Redirect to dashboard
    else Username exists
        S->>V: Show error message
    end
```

## UC-002: User Login
```mermaid
sequenceDiagram
    participant U as User
    participant S as System
    
    U->>S: Enter username/password
    S->>S: Validate credentials
    alt Valid credentials
        S->>S: Create user session
        S->>U: Redirect to dashboard
        alt Customer
            S->>U: Show customer dashboard
        else Chef
            S->>U: Show chef dashboard
        else Delivery Person
            S->>U: Show delivery dashboard
        else Manager
            S->>U: Show manager dashboard
        end
    else Invalid credentials
        S->>U: Show error message
    end
```

## UC-004: Browse Menu
```mermaid
flowchart TD
    A[User visits homepage] --> B{User type?}
    B -->|Visitor| C[Show public menu]
    B -->|Customer| D[Show personalized menu]
    B -->|VIP Customer| E[Show VIP menu + exclusive dishes]
    
    C --> F[Display all available dishes]
    D --> G[Show most ordered dishes]
    E --> H[Show VIP exclusive dishes]
    
    F --> I[User can view dish details]
    G --> I
    H --> I
    
    I --> J[Add to cart if logged in]
    I --> K[View dish ratings and reviews]
```

## UC-007: Add Item to Cart
```mermaid
sequenceDiagram
    participant C as Customer
    participant S as System
    
    C->>S: Click "Add to Cart" on dish
    S->>S: Check if customer is logged in
    alt Not logged in
        S->>C: Redirect to login page
    else Logged in
        S->>S: Check VIP access for VIP-only dishes
        alt VIP dish and not VIP customer
            S->>C: Show "VIP exclusive" error
        else Access granted
            S->>S: Add item to session cart
            S->>C: Update cart display
            S->>C: Show success message
        end
    end
```

## UC-008: Create Order
```mermaid
flowchart TD
    A[Customer confirms cart] --> B[Calculate total amount]
    B --> C{Customer is VIP?}
    C -->|Yes| D[Apply 5% discount]
    C -->|No| E[No discount]
    
    D --> F[Check account balance]
    E --> F
    
    F --> G{Sufficient balance?}
    G -->|No| H[Add warning to customer]
    G -->|Yes| I[Create order record]
    
    H --> J[Reject order]
    I --> K[Create order items]
    K --> L[Deduct from account balance]
    L --> M[Update customer spending]
    M --> N[Check for VIP upgrade]
    N --> O[Order created successfully]
```

## UC-010: Delivery Person Bidding
```mermaid
sequenceDiagram
    participant DP as Delivery Person
    participant S as System
    participant M as Manager
    
    DP->>S: View available orders
    S->>S: Get confirmed orders
    S->>DP: Display order list
    DP->>S: Enter bid amount
    S->>S: Save bid information
    S->>M: Notify manager of new bid
    M->>S: Review all bids
    M->>S: Select winning bid
    S->>S: Update order with selected delivery person
    S->>DP: Notify of selection result
```

## UC-011: Delivery Route Planning
```mermaid
flowchart TD
    A[Delivery person accepts order] --> B[Get restaurant coordinates]
    B --> C[Get customer address]
    C --> D[Geocode customer address]
    D --> E{Coordinates found?}
    E -->|No| F[Show error message]
    E -->|Yes| G[Call OpenRouteService API]
    G --> H{API call successful?}
    H -->|No| I[Show fallback route info]
    H -->|Yes| J[Parse route data]
    J --> K[Display route on map]
    K --> L[Show distance and duration]
    L --> M[Provide navigation instructions]
```

## UC-013: AI Intelligent Q&A
```mermaid
sequenceDiagram
    participant U as User
    participant S as System
    participant KB as Knowledge Base
    participant LLM as Ollama LLM
    
    U->>S: Ask question via chat
    S->>KB: Search local knowledge base
    KB->>S: Return matching entries
    
    alt Found in knowledge base
        S->>U: Return knowledge base answer
        S->>U: Show rating buttons
        U->>S: Rate answer (0-5)
        alt Rating = 0 (bad)
            S->>KB: Flag answer for review
        end
    else Not found in knowledge base
        S->>LLM: Call Ollama API
        LLM->>S: Return AI-generated answer
        S->>U: Return LLM answer
    end
```

## UC-015: Submit Complaint
```mermaid
flowchart TD
    A[User wants to file complaint] --> B{User type?}
    B -->|Customer| C[Can complain about chef/delivery/customer]
    B -->|Delivery Person| D[Can complain about customer]
    
    C --> E[Select complaint target]
    D --> E
    E --> F[Fill complaint form]
    F --> G[Submit complaint]
    G --> H[System records complaint]
    H --> I[Set status to 'pending']
    I --> J[Notify manager]
    J --> K[Manager reviews complaint]
    K --> L{Manager decision}
    L -->|Accept| M[Update target warnings]
    L -->|Dismiss| N[Mark as dismissed]
    M --> O[Notify all parties]
    N --> O
```

## UC-018: VIP Status Check
```mermaid
flowchart TD
    A[Customer completes order] --> B[Update total spending]
    B --> C[Update order count]
    C --> D{Check VIP criteria}
    D --> E{Total spent ≥ $100?}
    E -->|Yes| F[Upgrade to VIP]
    E -->|No| G{Order count ≥ 3?}
    G -->|Yes| F
    G -->|No| H[Remain regular customer]
    
    F --> I[Set is_vip = True]
    I --> J[Apply VIP privileges]
    J --> K[5% discount on orders]
    J --> L[Access to VIP dishes]
    J --> M[Free delivery every 3 orders]
    J --> N[Double weight for feedback]
```

## UC-020: Account Top-up
```mermaid
sequenceDiagram
    participant C as Customer
    participant S as System
    
    C->>S: Access profile page
    C->>S: Click "Add Funds"
    C->>S: Enter top-up amount
    S->>S: Validate amount (must be > 0)
    alt Valid amount
        S->>S: Update account balance
        S->>S: Record transaction history
        S->>C: Show updated balance
        S->>C: Show success message
    else Invalid amount
        S->>C: Show error message
    end
```

## UC-021: Payment Verification
```mermaid
flowchart TD
    A[Customer submits order] --> B[Calculate order total]
    B --> C{Customer is VIP?}
    C -->|Yes| D[Apply 5% discount]
    C -->|No| E[No discount]
    
    D --> F[Final amount = total - discount]
    E --> F
    
    F --> G[Check customer balance]
    G --> H{Balance ≥ final amount?}
    H -->|Yes| I[Process payment]
    H -->|No| J[Add warning to customer]
    
    I --> K[Deduct amount from balance]
    K --> L[Update total spent]
    L --> M[Increment order count]
    M --> N[Order created successfully]
    
    J --> O[Reject order]
    O --> P[Show insufficient funds error]
```

---

## How to Use These Diagrams

### Option 1: Mermaid Live Editor
1. Go to https://mermaid.live/
2. Copy any of the diagram codes above
3. Paste into the editor
4. Export as PNG/SVG

### Option 2: GitHub
1. Create a new .md file on GitHub
2. Paste the diagram code
3. GitHub will automatically render the diagrams
4. Right-click to save as image

### Option 3: VS Code
1. Install Mermaid Preview extension
2. Open the .md file
3. Use preview mode to see diagrams
4. Export as needed

### Option 4: Professional Tools
Use the flowchart descriptions to create diagrams in:
- Lucidchart
- Draw.io
- Visio
- Figma
