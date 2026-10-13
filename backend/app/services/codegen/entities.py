"""Domain intelligence: detects the application domain from a requirement and provides
entities, roles, screens and sample data used by agents and code generators."""

import re
from dataclasses import dataclass, field


@dataclass
class DomainTemplate:
    key: str
    label: str
    keywords: list[str]
    purpose_template: str
    target_users: list[str]
    user_roles: list[str]
    user_flow: list[str]
    features: list[str] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    prototype_screens: list[dict] = field(default_factory=list)
    sample_data: dict = field(default_factory=dict)


HOSPITAL = DomainTemplate(
    key="hospital",
    label="Hospital Management System",
    keywords=["hospital", "patient", "doctor", "medical", "clinic", "health", "care"],
    purpose_template="digitize hospital operations including patient registration, appointment scheduling, doctor management, and medical records",
    target_users=["Patients", "Doctors", "Administrators", "Reception Staff"],
    user_roles=["Patient", "Doctor", "Administrator", "Reception"],
    user_flow=["Patient registers and logs in", "Patient books an appointment with a doctor", "Doctor manages appointments and adds medical records", "Administrator manages users and roles", "Users view medical records and history"],
    features=["Patient Registration & Login", "Doctor Listing & Search", "Appointment Booking & Scheduling", "Dashboard (Patient & Doctor)", "Medical Records Management", "Prescription Management", "User Management (Admin)"],
    entities=[
        {"name": "User", "fields": [("name", "string"), ("email", "string"), ("password_hash", "string"), ("role", "string")]},
        {"name": "Patient", "fields": [("name", "string"), ("email", "string"), ("phone", "string"), ("address", "string"), ("date_of_birth", "date")], "relations": [("Patient", "User")]},
        {"name": "Doctor", "fields": [("name", "string"), ("specialty", "string"), ("email", "string"), ("phone", "string")], "relations": [("Doctor", "User")]},
        {"name": "Appointment", "fields": [("patient_id", "integer"), ("doctor_id", "integer"), ("scheduled_at", "datetime"), ("status", "string"), ("notes", "text")], "relations": [("Appointment", "Patient"), ("Appointment", "Doctor")]},
        {"name": "MedicalRecord", "fields": [("patient_id", "integer"), ("doctor_id", "integer"), ("diagnosis", "text"), ("prescription", "text"), ("record_date", "datetime")], "relations": [("MedicalRecord", "Patient"), ("MedicalRecord", "Doctor")]},
    ],
    prototype_screens=[
        {"name": "Home", "purpose": "Landing page presenting the hospital and its services", "sections": ["hero", "stats", "cards"]},
        {"name": "Login", "purpose": "Authentication for patients, doctors and admins", "sections": ["form"]},
        {"name": "Dashboard", "purpose": "Overview of appointments and activity", "sections": ["stats", "list"]},
        {"name": "Doctors", "purpose": "Doctor listing and search", "sections": ["list", "cards"]},
        {"name": "Appointments", "purpose": "Book and manage appointments", "sections": ["form", "list"]},
        {"name": "Medical Records", "purpose": "View medical records", "sections": ["list", "detail"]},
    ],
    sample_data={
        "Doctors": ["Dr. Sarah Chen - Cardiology", "Dr. James Patel - Orthopedics", "Dr. Maria Gomez - Pediatrics", "Dr. Alan Woods - Dermatology"],
        "Appointments": ["Sarah Malik with Dr. Chen - Sep 30, 10:00 (Confirmed)", "Ravi Kumar with Dr. Patel - Sep 30, 11:30 (Pending)", "Ana Silva with Dr. Gomez - Oct 1, 09:00 (Confirmed)"],
        "Patients": ["Sarah Malik", "Ravi Kumar", "Ana Silva", "John Doe"],
    },
)

FOOD = DomainTemplate(
    key="food",
    label="Food Delivery Platform",
    keywords=["food", "restaurant", "delivery", "menu", "cart", "dish", "meal"],
    purpose_template="let customers browse restaurants, order food, and track delivery",
    target_users=["Customers", "Restaurant Owners", "Delivery Staff"],
    user_roles=["Customer", "Restaurant Owner", "Delivery Staff"],
    user_flow=["Customer browses restaurants", "Customer selects food and adds to cart", "Customer checks out and pays", "Customer tracks the order", "Restaurant confirms and prepares the order"],
    features=["Restaurant Listing & Search", "Food Selection & Menu", "Cart Management", "Checkout & Ordering", "Order Tracking", "Restaurant Dashboard"],
    entities=[
        {"name": "User", "fields": [("name", "string"), ("email", "string"), ("password_hash", "string"), ("role", "string")]},
        {"name": "Restaurant", "fields": [("name", "string"), ("cuisine", "string"), ("address", "string"), ("rating", "float")], "relations": [("Restaurant", "User")]},
        {"name": "MenuItem", "fields": [("restaurant_id", "integer"), ("name", "string"), ("description", "text"), ("price", "float")], "relations": [("MenuItem", "Restaurant")]},
        {"name": "Order", "fields": [("customer_id", "integer"), ("restaurant_id", "integer"), ("status", "string"), ("total", "float"), ("created_at", "datetime")], "relations": [("Order", "User"), ("Order", "Restaurant")]},
        {"name": "OrderItem", "fields": [("order_id", "integer"), ("menu_item_id", "integer"), ("quantity", "integer")], "relations": [("OrderItem", "Order"), ("OrderItem", "MenuItem")]},
    ],
    prototype_screens=[
        {"name": "Home", "purpose": "Restaurant listing and search", "sections": ["hero", "cards"]},
        {"name": "Login", "purpose": "Authentication", "sections": ["form"]},
        {"name": "Menu", "purpose": "Food selection for a restaurant", "sections": ["list", "form"]},
        {"name": "Cart", "purpose": "Review selected food", "sections": ["list", "form"]},
        {"name": "Checkout", "purpose": "Place the order", "sections": ["form", "detail"]},
        {"name": "Order Tracking", "purpose": "Track order status", "sections": ["list", "detail"]},
    ],
    sample_data={
        "Restaurants": ["Pizza Palace - Italian (4.5)", "Sushi World - Japanese (4.8)", "Burger Barn - American (4.2)", "Curry House - Indian (4.6)"],
        "Menu": ["Margherita Pizza - $12", "Chicken Burger - $9", "Sushi Platter - $18", "Paneer Tikka - $11"],
        "Orders": ["#1023 Pizza Palace - Preparing", "#1022 Sushi World - Out for delivery", "#1021 Burger Barn - Delivered"],
    },
)

ECOMMERCE = DomainTemplate(
    key="ecommerce",
    label="E-Commerce Website",
    keywords=["e-commerce", "ecommerce", "shop", "store", "product", "catalog", "cart"],
    purpose_template="let customers browse products, manage a cart, and place orders",
    target_users=["Customers", "Store Administrators"],
    user_roles=["Customer", "Admin"],
    user_flow=["Customer browses products", "Customer adds products to cart", "Customer checks out", "Customer views order history", "Admin manages products"],
    features=["Product Catalog & Search", "Product Details", "Cart Management", "Checkout & Ordering", "Order History", "Admin Product Management"],
    entities=[
        {"name": "User", "fields": [("name", "string"), ("email", "string"), ("password_hash", "string"), ("role", "string")]},
        {"name": "Product", "fields": [("name", "string"), ("description", "text"), ("price", "float"), ("stock", "integer"), ("category", "string")]},
        {"name": "CartItem", "fields": [("user_id", "integer"), ("product_id", "integer"), ("quantity", "integer")], "relations": [("CartItem", "User"), ("CartItem", "Product")]},
        {"name": "Order", "fields": [("user_id", "integer"), ("status", "string"), ("total", "float"), ("created_at", "datetime")], "relations": [("Order", "User")]},
    ],
    prototype_screens=[
        {"name": "Home", "purpose": "Featured products", "sections": ["hero", "cards"]},
        {"name": "Login", "purpose": "Authentication", "sections": ["form"]},
        {"name": "Products", "purpose": "Product catalog", "sections": ["list", "form"]},
        {"name": "Cart", "purpose": "Cart management", "sections": ["list"]},
        {"name": "Checkout", "purpose": "Place order", "sections": ["form", "detail"]},
        {"name": "Orders", "purpose": "Order history", "sections": ["list"]},
    ],
    sample_data={
        "Products": ["Wireless Headphones - $59", "Smart Watch - $129", "Laptop Stand - $35", "USB-C Hub - $42"],
        "Orders": ["#501 - Shipped - $188", "#500 - Delivered - $59"],
    },
)

EDUCATION = DomainTemplate(
    key="education",
    label="Learning Management System",
    keywords=["student", "school", "course", "learning", "education", "lms", "university", "college", "portal", "assignment", "grade"],
    purpose_template="let students enroll in courses, submit assignments, and track grades",
    target_users=["Students", "Teachers", "Administrators"],
    user_roles=["Student", "Teacher", "Admin"],
    user_flow=["Student registers and logs in", "Student browses and enrolls in courses", "Student submits assignments", "Teacher grades submissions", "Student views grades"],
    features=["Course Catalog & Enrollment", "Assignment Submission", "Grade Tracking", "Course Dashboard", "User Management"],
    entities=[
        {"name": "User", "fields": [("name", "string"), ("email", "string"), ("password_hash", "string"), ("role", "string")]},
        {"name": "Course", "fields": [("title", "string"), ("description", "text"), ("teacher_id", "integer")], "relations": [("Course", "User")]},
        {"name": "Enrollment", "fields": [("student_id", "integer"), ("course_id", "integer")], "relations": [("Enrollment", "User"), ("Enrollment", "Course")]},
        {"name": "Assignment", "fields": [("course_id", "integer"), ("title", "string"), ("due_date", "date")], "relations": [("Assignment", "Course")]},
        {"name": "Grade", "fields": [("assignment_id", "integer"), ("student_id", "integer"), ("score", "float")], "relations": [("Grade", "Assignment"), ("Grade", "User")]},
    ],
    prototype_screens=[
        {"name": "Home", "purpose": "Overview and course highlights", "sections": ["hero", "stats", "cards"]},
        {"name": "Login", "purpose": "Authentication", "sections": ["form"]},
        {"name": "Courses", "purpose": "Course catalog and enrollment", "sections": ["list", "form"]},
        {"name": "My Courses", "purpose": "Enrolled courses", "sections": ["cards"]},
        {"name": "Assignments", "purpose": "Submit and view assignments", "sections": ["list", "form"]},
        {"name": "Grades", "purpose": "Track grades", "sections": ["list", "stats"]},
    ],
    sample_data={
        "Courses": ["Introduction to Python - Dr. Smith", "Data Structures - Prof. Lee", "Web Development - Ms. Clark"],
        "Assignments": ["Python Basics Exercise - due Oct 5", "Linked List Implementation - due Oct 8", "HTML Layout Task - due Oct 12"],
        "Grades": ["Python Basics: 92/100", "Data Structures: 85/100"],
    },
)

GENERIC = DomainTemplate(
    key="generic",
    label="Custom Web Application",
    keywords=[],
    purpose_template="manage records and workflows for its users",
    target_users=["End Users", "Administrators"],
    user_roles=["User", "Admin"],
    user_flow=["User registers and logs in", "User creates and manages records", "User views record details", "Admin manages users"],
    features=["User Registration & Login", "Record Management (Create/List/Update/Delete)", "Dashboard", "Search & Filtering"],
    entities=[
        {"name": "User", "fields": [("name", "string"), ("email", "string"), ("password_hash", "string"), ("role", "string")]},
        {"name": "Record", "fields": [("user_id", "integer"), ("title", "string"), ("description", "text"), ("status", "string")], "relations": [("Record", "User")]},
    ],
    prototype_screens=[
        {"name": "Home", "purpose": "Overview", "sections": ["hero", "stats", "cards"]},
        {"name": "Login", "purpose": "Authentication", "sections": ["form"]},
        {"name": "Records", "purpose": "Manage records", "sections": ["list", "form"]},
        {"name": "Dashboard", "purpose": "Summary dashboard", "sections": ["stats", "list"]},
    ],
    sample_data={"Records": ["First record - pending", "Second record - completed"]},
)

DOMAINS = [HOSPITAL, FOOD, ECOMMERCE, EDUCATION, GENERIC]


def detect_domain(requirement: str) -> DomainTemplate:
    text = (requirement or "").lower()
    best, best_score = GENERIC, 0
    for domain in DOMAINS:
        if domain.key == "generic":
            continue
        score = sum(1 for kw in domain.keywords if kw in text)
        if score > best_score:
            best, best_score = domain, score
    return best


def extract_app_name(requirement: str, domain: DomainTemplate) -> str:
    text = (requirement or "").strip()
    m = re.search(
        r"(?:build|create|develop|make)\s+(?:me\s+)?(?:a|an|the)?\s*([A-Za-z0-9 \-&]+?(?:System|Application|Platform|Portal|Website|App|Marketplace|Store))",
        text,
        re.IGNORECASE,
    )
    if m:
        name = m.group(1).strip()
        return name[0].upper() + name[1:]
    return domain.label


def extract_extra_features(requirement: str, known_features: list[str]) -> list[str]:
    """Detect additional features explicitly mentioned in the requirement text."""
    text = (requirement or "").lower()
    extras: list[str] = []
    extra_keywords = [
        ("cancel appointment", "Appointment Cancellation"),
        ("reschedule", "Appointment Rescheduling"),
        ("payment", "Payment Processing"),
        ("notification", "Notifications"),
        ("report", "Reports & Analytics"),
        ("chat", "In-App Chat"),
        ("review", "Ratings & Reviews"),
        ("inventory", "Inventory Management"),
        ("feedback", "Feedback Management"),
        ("track", "Order/Status Tracking"),
    ]
    for kw, feature in extra_keywords:
        if kw in text and feature not in known_features and feature not in extras:
            extras.append(feature)
    return extras


def normalize_entities(entities: list[dict]) -> list[dict]:
    """Normalize entity dicts to the codegen-internal format.

    Accepts DatabaseSchemaResult-style dicts (fields/relations as dicts) as well as
    domain-template style (fields/relations as tuples) and returns a uniform shape:
    {"name", "table", "fields": [(name, type)], "relations": [(from, to)], "description"}.
    """
    from app.services.codegen.database_sql import _table_name

    normalized = []
    for e in entities or []:
        fields: list[tuple] = []
        for f in e.get("fields", []):
            if isinstance(f, dict):
                fields.append((f.get("name", "field"), f.get("type", "string")))
            else:
                fields.append((f[0], f[1] if len(f) > 1 else "string"))
        relations: list[tuple] = []
        for r in e.get("relations", []):
            if isinstance(r, dict):
                relations.append((r.get("from_entity", ""), r.get("to_entity", "")))
            else:
                relations.append((r[0], r[1] if len(r) > 1 else ""))
        normalized.append(
            {
                "name": e.get("name", "Record"),
                "table": e.get("table") or _table_name({"name": e.get("name", "Record")}),
                "fields": fields,
                "relations": relations,
                "description": e.get("description", ""),
            }
        )
    return normalized
