import sqlite3
from pathlib import Path
import json


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "university_scheduler.sqlite3"
COURSES_JSON_PATH = BASE_DIR.parent / "courses.json"
COURSE_SEED_COLUMNS = ("course_id", "ctype", "title", "credits", "description", "reqs")


SCHEMA = """
CREATE TABLE IF NOT EXISTS degrees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    total_credits INTEGER NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS degree_requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    degree_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    credits INTEGER NOT NULL,
    details TEXT NOT NULL,
    FOREIGN KEY (degree_id) REFERENCES degrees(id)
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id TEXT NOT NULL UNIQUE,
    ctype TEXT NOT NULL,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL,
    description TEXT NOT NULL,
    reqs TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
"""


SEED_DEGREES = [
    (
        "Computer Science (BCS)",
        20,
        "A flexible computing degree covering topics such as programming, computer systems, data, and ML/AI.",
        [
            ("Core Mathematics", 2.5, "Calculus, linear algebra, and combinatorics"),
            ("Core CS", 4.75, "Algorithms, data structures, software, and computer systems"),
            ("Core Statistics", 1, "Probability and statistics"),
            ("CS Electives", 3, "Advanced CS electives"),
            ("Non-Math", 5, "Non-math courses"),
            ("Communication", 1, "English and communication courses"),
        ],
    ),
    (
        "Computer Science (BMath)",
        20,
        "A flexible computing degree covering topics such as programming, computer systems, data, and ML/AI.",
        [
            ("Core Mathematics", 2.5, "Calculus, linear algebra, and combinatorics"),
            ("Core CS", 4.75, "Algorithms, data structures, software, and computer systems"),
            ("Core Statistics", 1, "Probability and statistics"),
            ("CS Electives", 3, "Advanced CS electives"),
            ("Non-Math", 5, "Non-math courses"),
            ("Communication", 1, "English and communication courses"),
        ],
    ),
]

def load_seed_courses(json_path: Path = COURSES_JSON_PATH) -> list[tuple]:
    """Load course seed data in the same column order used by SQLite inserts."""
    with json_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    courses = payload["courses"] if isinstance(payload, dict) else payload
    return [tuple(course[column] for column in COURSE_SEED_COLUMNS) for course in courses]


SEED_COURSES = load_seed_courses()

def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with get_connection() as connection:
        connection.executescript(SCHEMA)
        degree_count = connection.execute("SELECT COUNT(*) FROM degrees").fetchone()[0]
        if degree_count == 0:
            for name, credits, description, requirements in SEED_DEGREES:
                cursor = connection.execute(
                    "INSERT INTO degrees (name, total_credits, description) VALUES (?, ?, ?)",
                    (name, credits, description),
                )
                degree_id = cursor.lastrowid
                connection.executemany(
                    """
                    INSERT INTO degree_requirements (degree_id, category, credits, details)
                    VALUES (?, ?, ?, ?)
                    """,
                    [(degree_id, category, req_credits, details) for category, req_credits, details in requirements],
                )

        course_count = connection.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
        if course_count == 0:
            connection.executemany(
                """
                INSERT INTO courses (course_id, ctype, title, credits, description, reqs)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                SEED_COURSES,
            )


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]

def row_to_dict(row: sqlite3.Row) -> dict:
    if row is None:
        return {"This course does not exist"}
    return dict(row)
