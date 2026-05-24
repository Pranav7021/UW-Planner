from __future__ import annotations
import re
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langchain.agents.middleware import SummarizationMiddleware
from langchain.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel
from typing import Literal

from database import get_connection, rows_to_dicts, row_to_dict, initialize_database
import os

os.environ["OPENAI_API_KEY"] = 'your_api_key'
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGSMITH_API_KEY"] = "your_api_key"
os.environ["LANGSMITH_PROJECT"] = "uw_course_planner"

class courseInfo(BaseModel):
    course_id: str
    term: Literal['1A', '1B', '2A', '2B', '3A', '3B', '4A', '4B']

class PlannerResponse(BaseModel):
    message: str
    suggested_courses: list[courseInfo] = []
    degree: dict | None = None

initialize_database()

# GETTING COURSE DATA AND BUILDING THE COURSE VECTORSTORE
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
course_vectorstore = InMemoryVectorStore(embedding=embeddings)

with get_connection() as connection:
    courses = rows_to_dicts(connection.execute("SELECT * FROM courses").fetchall())

course_documents = [Document(page_content=d["description"],
                             metadata={'course_id': d["course_id"], 'type': d["ctype"], 'title': d["title"], 'reqs': d["reqs"]}) 
                            for d in courses]

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=2000,
    chunk_overlap=200,
)

course_splits = text_splitter.split_documents(course_documents)
course_document_ids = course_vectorstore.add_documents(course_splits)
print(f"INITIALIZED COURSE VECTORSTORE WITH {len(course_splits)} COURSES")

@tool
def get_specific_course_info(course_code: str) -> dict:
    """ Gets all course information from the provided course code from the database """
    with get_connection() as connection:
        course = row_to_dict(connection.execute((f"SELECT * FROM courses WHERE course_id IS \"{course_code}\"")).fetchone())

    return course

@tool
def get_relevant_courses_of_type(prompt: str, num_courses: int, course_type: str) -> str:
    """ 
    Gets the num_courses most relevant courses from the database given the user's prompt of the given course type.

    The course_type MUST be one of ["CS", "MATH", "ECON", "PHYS", "STAT", "ENGL", "AFM"].

    For example, calling this with course_type="CS", num_courses=5 and the user's prompt will get the 5 most relevant CS courses for the user.
    """
    filter_fun = lambda x: x.metadata.get("type") == course_type
    retrieved_courses = course_vectorstore.similarity_search(query=prompt, k=num_courses, filter=filter_fun)
    joined_context = "\n\n".join(
        (f"Course Information: {doc.metadata}\nCourse Description: {doc.page_content}")
        for doc in retrieved_courses
    )

    return joined_context

# THE AGENTS

config = {"configurable": {"thread_id": "1"}}
model = "openai:gpt-5.4-mini"

scheduler_agent = create_agent(
    model=model,
    tools = [get_relevant_courses_of_type, get_specific_course_info],
    system_prompt=
    """
    You are a University of Waterloo undergraduate course schedule planner.

    The user is in Honours CS.

    At the University of Waterloo, each year (from 1-4) has two terms (A and B).

    In each term, plan for 5 courses, unless otherwise specified.

    You MUST schedule a course to be taken in at least the year corresponding to the course's starting digit, unless otherwise specified.

    For example, CS 341 should only be taken in years 3 or 4, which corresponds to terms 3A or 3B or 4A or 4B.
    
    You can call a tool to get the top course recommendations of a specific subject using your tool.

    When calling this tool, provide it ONLY up to 5 key words that you want it to use to get the best course recommendations.

    You also have a tool to look up a specific courses's information.

    You can ONLY use the courses in the database that you have access to. Do NOT make up courses.

    Do NOT ask follow-up questions. If needed, just make a guess and go from there since the user can call another agent to modify the schedule if needed.

    Organize courses in chronological order into the terms 1A, 1B, and so on up to 4B, ensuring that the order you arrange them in satisfies the prerequisite, corequisite, and antirequisite requirements of each course.

    IGNORE the minimum grade requirements for prerequisites if they exist.

    For each course, return its course code and the term the user should take it in.

    Here is an example of what you should do:

    You are given: "The user is interested in ML and AI. Plan their schedule."

    You should reply:
    " MATH 135 (1A), MATH 137 (1A), CS 135 (1A), ECON 101 (1A), PHYS 121 (1A), MATH 136 (1B), MATH 138 (1B), CS 136 (1B), ECON 102 (1B), PHYS 121 (1B), MATH 239 (2A), CS 245 (2A), CS 246 (2A), ..., CS 480 (4B), CS 486 (4B) "
    """
)

@tool
def call_scheduler_agent(prompt: str):
    ''' Calls the course scheduler agent to create a new course schedule based on the prompt '''
    response = scheduler_agent.invoke({"messages": prompt})
    return response["messages"][-1].content

modifier_agent = create_agent(
    model=model,
    tools=[get_relevant_courses_of_type, get_specific_course_info],
    system_prompt=
    """
    You are a University of Waterloo course schedule modifier.

    You will be given a prompt on how to modify a schedule and you must follow those instructions.

    The user is in Honours CS.

    At the University of Waterloo, each year (from 1-4) has two terms (A and B).

    When calling this tool, provide it ONLY up to 5 key words that you want it to use to get the best course recommendations.

    You also have a tool to look up a specific courses's information.

    You can ONLY use the courses in the database that you have access to. Do NOT make up courses.

    Make sure that courses are organized into terms such that each course's prerequisite, corequisite, and antirequisite are satisfied.

    IGNORE the minimum grade requirements for prerequisites if they exist.

    For each course, return its course code and the term the user should take it in.

    Here is an example of what you should do:

    You are given: "The user wants to add 5 physics courses to get a good physics foundation. Modify their schedule. 
                    Current course schedule: MATH 135 (1A), MATH 137 (1A), CS 135 (1A), ECON 101 (1A), ECON 102 (1A), MATH 136 (1B), MATH 138 (1B), CS 136 (1B), ECON 201 (1B), MATH 239 (2A), CS 245 (2A), CS 246 (2A), ..., CS 480 (4B), CS 486 (4B)"

    You should: Look up 5 good physics courses to get a good physics foundation and insert these courses in the correct terms.

    Your response should be: " MATH 135 (1A), MATH 137 (1A), CS 135 (1A), ECON 101 (1A), PHYS 121 (1A), MATH 136 (1B), MATH 138 (1B), CS 136 (1B), ECON 102 (1B), PHYS 122 (1B), MATH 239 (2A), CS 245 (2A), CS 246 (2A), ..., CS 480 (4B), CS 486 (4B) "
    """
)

@tool
def call_modifier_agent(prompt: str, current_course_schedule: str):
    ''' Calls the course schedule modifier agent to modify the current course schedule based on the prompt '''
    response = modifier_agent.invoke({"messages": prompt + "\n\nCurrent course schedule: \n" + current_course_schedule})
    return response["messages"][-1].content

verifier_agent = create_agent(
    model=model,
    tools=[get_specific_course_info, call_modifier_agent],
    system_prompt=
    """
    You are a University of Waterloo course schedule verifier. The University of Waterloo has 4 years, each with terms A and B.

    The user is in Honours CS. The user has satisfied all courses that contain "4U", such as "4U Calculus and Vectors".
    
    You must verify the proposed schedule according to the following rules:
    1. The schedule is planned from terms 1A through 4B.
    2. In each term, there are exactly 5 courses.
    3. Each courses's prerequisites, corequisites, and antirequisites are met. Checking this will likely require you to use your tool to look up specific course information. IGNORE the minimum grade requirements for prerequisites if they exist.
    4. Ensure that the schedule has 16 - 20 CS courses, 5-7 MATH courses, 2-4 STAT courses, and 10-12 ECON and PHYS courses.
    5. A MATH/CS/STAT course must be taken in a year that is greater than or equal to the course's starting digit.
    6. There are no duplicate courses.

    If you need to change the schedule to fit these requirements, call the schedule modifier agent, which is a tool you have.
    """
)

@tool
def call_verifier_agent(prompt: str, current_course_schedule: str):
    ''' 
    Calls the course verifier agent to verify the current course schedule and change it to fit pre-defined requirements 

    current_course_schedule must be a list of courses that you are currently planning to propose to the user
    '''
    response = verifier_agent.invoke({"messages": prompt + "\n\nCurrent course schedule: \n" + current_course_schedule})
    return response["messages"][-1].content

summarizer = SummarizationMiddleware(model='gpt-5-nano', trigger=("fraction", 0.5))

main_agent = create_agent(
    model=model,
    tools=[call_scheduler_agent, call_modifier_agent, call_verifier_agent],
    system_prompt=
    """
    You are a helpful University of Waterloo undergraduate course schedule planning assistant.

    If the user asks you to create or modify a schedule, you MUST use your subagents. You MUST call the verifier agent.

    If the user asks a question about their schedule, then you do not need to use your subagents.

    Do NOT ask the user a question unless absolutely necessary. Your subagents have a lot of information already, for example:
    1. They know how many courses to plan per term
    2. How many terms there are

    However, IF the user makes a specific request about the structure of the schedule, then you should pass this information onto your subagents when you call them.

    You have access to three subagents:
    1. A scheduler subagent that can create a new course schedule.
    2. A modifier subagent that can modify the current course schedule based on instructions.
    3. A verifier subagent that can verify that the current course schedule meets some pre-defined requirements.

    Use ONLY courses you have access to through the scheduler, modifier, and verifier subagents. Do NOT make up any courses.

    Do NOT tell the user about your subagents. For example, do not mention the verifier in your response.

    Do NOT leave the suggested_courses field of your structured response blank.
    """,
    middleware=[summarizer],
    checkpointer=InMemorySaver(),
    response_format=PlannerResponse
)

def build_agent_response(user_message: str) -> PlannerResponse:
    message = HumanMessage(content=user_message)
    response = main_agent.invoke({"messages": [message]}, config=config)
    return response["structured_response"]
