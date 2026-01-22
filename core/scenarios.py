from dataclasses import dataclass
from typing import List

@dataclass
class Scenario:
    name: str # e.g. "Authentication Regression"
    change_summary: str # The "context" given to the LLM
    keywords: List[str] # Keywords to match test names/components against for fault injection

# Define standard scenarios for Monte Carlo simulation
SCENARIOS = [
    Scenario(
        name="Authentication Regression",
        change_summary="Refactored the session management and login validation logic to improve security. Updated the token refresh mechanism.",
        keywords=["bank account", "contact", "user", "auth", "login"] # Targeted at User/Account tests in RWA
    ),
    Scenario(
        name="Payment Gateway Integration Update",
        change_summary="Migrated to a new payment provider API. Updated the checkout flow and transaction validation.",
        keywords=["transaction", "transfer", "payment", "pay", "money"] # Targeted at Transaction tests
    ),
    Scenario(
        name="UI/Frontend Overhaul",
        change_summary="Updated the global CSS variables and responsive layout for the dashboard and landing pages. Refactored the navigation component.",
        keywords=["notification", "comment", "like", "ui", "css"] # Targeted at Social/UI components
    ),
    Scenario(
        name="Database Schema Migration",
        change_summary="Optimized database queries for the inventory and order history services. Added new indexes to the users table.",
        keywords=["api", "list", "query"] # Targeted at List/API tests (broad queries)
    ),
    Scenario(
        name="Critical Security Patch",
        change_summary="Applied a critical security patch to the input sanitization middleware.",
        keywords=["error", "invalid", "security", "input"] # Targeted at "errors when invalid..." tests
    )
]
