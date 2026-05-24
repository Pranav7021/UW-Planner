import requests
import pprint
import json

headers = {
    "x-api-key": "your_api_key",
}

subjects = ["CS", "MATH", "ECON", "PHYS", "STAT", "ENGL", "AFM"]

response = requests.get("https://openapi.data.uwaterloo.ca/v3/Courses/1259", headers=headers)
course_data = response.json()

cleaned_course_data = {'courses': []}

for subject in subjects:
    for course in course_data:
        if course['associatedAcademicCareer'] == 'UG' and course['catalogNumber'].isnumeric() and subject == course['subjectCode'] and int(course['catalogNumber']) >= 100:
            course_obj = {"course_id": subject + ' ' + course['catalogNumber'],
                          "ctype": subject,
                          "title": course['title'],
                          "credits": 0.5,
                          "description": course['description'],
                          "reqs": course['requirementsDescription'] if course['requirementsDescription'] is not None else ""}
            
            print(course_obj)
            cleaned_course_data['courses'].append(course_obj)

json_file_path = './courses.json'

with open(json_file_path, "w") as file:
    json.dump(cleaned_course_data, file)
