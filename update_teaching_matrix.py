# update_teaching_matrix.py - update BBE teaching matrix with survey data
# RMM, 9 Apr 2021

import numpy as np
import pandas as pd
import bbedata as bbe
import re

# Parse the command line options (eventually)
survey_update = False
survey_file = 'BBE Teaching Interest Survey, 2021-22 (Responses).xlsx'

enrollment_update = True
enrollment_file = "All courses past 2 years 220225.xlsx"

# Read the current teaching matrix
teaching_df = pd.read_excel("BBE Teaching Matrix.xlsx", header=1)
teaching_df = teaching_df.astype(
    {col: object for col in bbe.preference_strings})

verbose = True

# Update table with survey data
if survey_update:
    # Read the survey data
    survey_df = bbe.load_teaching_survey(survey_file)

    # Update the teaching matrix with survey information
    bbe.survey_update(teaching_df, survey_df)

# Update data with latest enrollment data
if enrollment_update:
    # Read the enrollment data
    courses = bbe.read_regis_data(enrollment_file, last_name_only=True)

    # Go through all of the courses in the teaching matrix
    for index, course in teaching_df.iterrows():
        # Get the course prefix from teaching matrix, strip leading 0's, term
        course_name = course['Course']
        if not isinstance(course_name, str):
            if verbose:
                print("Missing course name at line", index)
        else:
            course_name = re.sub(
                r"(\S*) 0*([1-9][0-9X]*)+([a-dA-D]*) .*",
                r"\1 \2\3", course_name)

        # See if the course is in the REGIS course list
        if not any(courses['Course'] == course_name):
            print("Couldn't find course", course_name)
            continue

        # Go through each year of the new data that are available
        for i, entry in courses[courses['Course'] == course_name].iterrows():
            # Update the course enrollment and instructor data
            teaching_df.at[index, entry['AY'] + ' enroll'] = \
                entry['Enrollment']
            teaching_df.at[index, entry['AY'] + ' Instructor(s)'] = \
                entry['Instructors']

# Write the updated teaching matrix
teaching_df.to_excel("BBE Teaching Matrix Updated.xlsx", "Courses")
