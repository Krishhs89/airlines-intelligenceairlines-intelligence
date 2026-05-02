# Real-World Airline Operations Guide

## How Airlines Actually Work — A Practitioner's Primer

This guide explains the domain knowledge embedded in the UA Network Intelligence system: how a real airline operates, what decisions matter, and how AI can support them.

---

## 1. The Airline Operations Hierarchy

### Corporate Structure (Revenue & Strategy)
- **VP Network Planning** — long-range (12–18 months) route portfolio decisions
- **VP Revenue Management** — pricing strategy, capacity allocation, overbooking
- **VP Fleet Planning** — aircraft acquisition, retirement, maintenance contracts

### Day-of-Operations (AOC — Airline Operations Control)
- **Director of Operations Control** — owns the operation 24/7
- **Flight Dispatchers (Part 121)** — FAA-licensed; co-sign every flight release
- **Crew Scheduling** — tracks legality, reserves, and coverage
- **Aircraft Routing** — maintains fleet routing continuity
- **Customer Operations** — manages passenger re-accommodation

### Hub Control (Airport-Level)
- **Station Manager** — overall airport performance
- **Gate Controller** — assigns and swaps gates in real time
- **Ramp Supervisor** — ground equipment, weight & balance, fueling
- **Customer Service Agents** — boarding, irregular operations handling

---

## 2. How Routes Are Planned

### Schedule Build Cycle (18 months out)
1. **Demand Forecasting** — historical booking curves, OAG traffic data, market share analysis
2. **Route P&L Modeling** — revenue (yield × load factor × ASMs) vs. cost (fuel, crew, maintenance, airport fees)
3. **Fleet Assignment** — matching aircraft gauge to demand (wide-body vs. narrow-body)
4. **Slot Coordination** — Level 3 airports (JFK, LHR, NRT) require slot filing via IATA
5. **Crew Pairing** — FAA Part 121 duty limits constrain which flights can be paired
6. **Schedule Publication** — filed with OAG, GDSs (Sabre, Amadeus, Travelport), and DOT

### Key Metrics
| Metric | Definition | Good Target |
|--------|------------|-------------|
| ASMs | Available Seat Miles (capacity) | Network benchmark |
| RPMs | Revenue Passenger Miles (demand) | — |
| Load Factor | RPMs / ASMs | >80% |
| RASM | Revenue per ASM (yield) | >12¢ domestic |
| CASM | Cost per ASM | <11¢ domestic |
| Break-even Load Factor | CASM / Yield | <75% |

### Demand Score Interpretation (System Scale)
- **0.9–1.0**: High demand; consider frequency increase or up-gauge
- **0.6–0.8**: Healthy; optimize pricing and timing
- **0.4–0.6**: Watch list; review seasonality
- **<0.4**: Underperforming; candidate for frequency reduction or suspension

---

## 3. Irregular Operations (IROPS)

IROPS is airline jargon for anything that breaks the normal operating plan. It is the highest-stakes, highest-speed decision domain.

### Common IROPS Triggers

| Trigger | Lead Time | Typical Duration |
|---------|-----------|-----------------|
| Convective weather (thunderstorms) | 2–4 hours | 2–8 hours |
| Winter storm | 12–48 hours | 4–24 hours |
| Mechanical AOG (Aircraft on Ground) | Minutes | 2–72 hours |
| FAA Ground Delay Program (GDP) | 1–4 hours | Ongoing |
| ATC Ground Stop | Minutes | 1–4 hours |
| Gate/facility emergency | Minutes | 1–24 hours |
| Crew legality (FAR Part 121) | Hours | 1–8 hours |
| Security incident | Minutes | 1–4 hours |

### IROPS Decision Framework

1. **Triage**: Which flights are most impacted? Rank by: passenger count × missed connections × downstream disruption
2. **Cancel early**: A flight cancelled 3+ hours out = cheaper rebooking, less pax fury
3. **Aircraft swaps**: Can a different tail cover the trip? Check: maintenance release, crew qualification, ETOPS (over water), weight limits
4. **Crew coverage**: Check reserve banks, illegal pairings, domicile coverage
5. **Passenger recovery**: Auto-rebook via IROPS tools (Sabre Disruption Manager, etc.); proactive notification
6. **Ground stops**: Coordinate with ATC ATCSCC (Air Traffic Control System Command Center)
7. **Recovery**: Get the network back to baseline within 24–48 hours

### The Cancellation Decision Tree
```
Is the flight's aircraft available?
  No → Can we ferry a spare? → Check maintenance/crew → Swap or cancel
  Yes → Is crew legal? (Part 121 duty time)
    No → Is a reserve available? → Cover or cancel
    Yes → Is the destination open?
      No → Hold or cancel
      Yes → Is load factor sufficient?
        <20% → Consider consolidating with another flight
        >20% → Operate
```

---

## 4. Revenue Management

### Pricing Structure
Airlines use **EMSR (Expected Marginal Seat Revenue)** to optimize pricing across 10–30 fare buckets:

```
First/Business: F, C, J, Y (full)
Economy buckets: Y, B, M, H, Q, K, L, U, T, X, V (most restrictive)
```

### Key RM Decisions
- **Overbooking**: Airlines routinely sell 102–110% of capacity (based on historical no-show curves)
- **Upgrade clearing**: Premium upgrades are cleared at gate based on load and yield
- **Load factor vs. yield trade-off**: A 95% full flight at low yield < 80% full at high yield
- **Demand unconstraining**: Raw bookings under-report demand (flights sell out); RM systems "unconstrain" to model true demand

---

## 5. Fleet Operations

### Aircraft Type Differences (United's Main Fleet)

| Type | Seats | Range | Role |
|------|-------|-------|------|
| B737-MAX9 | 178 | 3,550 nm | Domestic/medium-haul |
| B787-9 | 252 | 7,635 nm | Long-haul international |
| B777-200 | 269 | 5,240 nm | International/transcontinental |
| A319 | 126 | 3,700 nm | Thin domestic routes |

### Maintenance Categories
- **A Check**: Every 400–600 flight hours (~1 day)
- **C Check**: Every 18–24 months (~2 weeks, heavy maintenance visit)
- **D Check**: Every 6–12 years (~2 months, major overhaul)
- **AOG (Aircraft on Ground)**: Unscheduled maintenance — highest priority

### Aircraft Routing Continuity
Airlines maintain a continuous routing string for each tail number. Breaking the string (e.g., swapping a plane mid-day) requires checking:
- Maintenance station capabilities (only certain stations have heavy maintenance)
- Parts availability (AOG parts may need to be ferried)
- Crew qualifications (pilots type-rated for specific aircraft)

---

## 6. Hub Operations

### United Airlines Hub Hierarchy
| Hub | IATA | Function |
|-----|------|----------|
| Chicago O'Hare | ORD | Primary domestic hub (largest) |
| Houston Intercontinental | IAH | International hub (Latin America) |
| Denver | DEN | West domestic hub |
| Newark | EWR | Northeast/transatlantic hub |
| Los Angeles | LAX | Pacific/West hub |
| San Francisco | SFO | Pacific/Asia hub |
| Washington Dulles | IAD | Mid-Atlantic/international |
| Las Vegas | LAS | Leisure/high-frequency |

### Hub Banking
Airlines structure departures/arrivals in **banks** to maximize connections:
- **Inbound bank**: Flights arrive within a 30-minute window from many origins
- **Connection window**: 45–120 minutes for passengers to connect
- **Outbound bank**: Flights depart together toward many destinations

### Gate Assignment Considerations
- **Gate conflicts**: Tight turns (<40 min) between arriving and departing flights risk delays
- **Aircraft size**: Wide-body gates cannot handle narrow-body efficiently (and vice versa)
- **International**: International gates require CBP, customs, and security screening space
- **Hardstand**: Some airports use remote gates that require bus service (slower, operationally costly)

---

## 7. On-Time Performance (OTP)

### DOT Reporting Thresholds
- On-time: Gate departure within 14 minutes of scheduled
- Reportable cancellation: Any cancellation within 24 hours of departure
- Mishandled bag rate: Must be filed monthly with DOT

### OTP Root Causes (Industry Distribution)
| Cause | Share |
|-------|-------|
| Carrier delay (carrier-caused) | ~35% |
| Late aircraft (propagated delay) | ~28% |
| NAS/ATC delay | ~24% |
| Weather | ~8% |
| Security | ~1% |
| Extreme weather (excusable) | ~4% |

### OTP Improvement Levers
- **Schedule padding**: Adding buffer time to flight plans (costly in block time)
- **Turn time optimization**: Faster ground handling processes
- **Early cancel**: Cancel underperforming flights proactively vs. suffering propagated delays
- **Gate proximity**: Reduce taxi times by optimizing gate assignments

---

## 8. AI Use Cases in Real Airlines

| Domain | Traditional Approach | AI Enhancement |
|--------|---------------------|----------------|
| IROPS | Rule-based systems (Sabre, AIMS) | LLM-powered triage and recommendation |
| Demand forecasting | Statistical time series (ARIMA, ES) | ML-based demand sensing |
| Route profitability | Spreadsheet P&L models | Multi-factor optimization |
| Crew scheduling | ILP solvers | Constraint-aware ML planners |
| Gate assignment | Manual/rule-based | Optimization with disruption awareness |
| Customer comms | Template-based IVR/email | Generative AI personalized messaging |
| Anomaly detection | Threshold alerts | Unsupervised ML clustering |

---

## 9. Glossary

| Term | Definition |
|------|------------|
| AOC | Airline Operations Control (24/7 nerve center) |
| AOG | Aircraft on Ground (unscheduled maintenance) |
| ASM | Available Seat Mile (one seat, one mile) |
| ATCSCC | Air Traffic Control System Command Center |
| ETOPS | Extended-range Twin-engine Operations (over-water rules) |
| FAR | Federal Aviation Regulation |
| GDP | Ground Delay Program (ATC manages departure rates) |
| GDS | Global Distribution System (Sabre, Amadeus, Travelport) |
| IATA | International Air Transport Association |
| IROPS | Irregular Operations |
| MCT | Minimum Connection Time |
| NAS | National Airspace System |
| OAG | Official Airline Guide (schedule data provider) |
| OTP | On-Time Performance |
| RASM | Revenue per Available Seat Mile |
| RPM | Revenue Passenger Mile |
| SROP | Standard Recovery Operating Procedure |
