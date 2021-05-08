# update_teaching_matrix.py - update BBE teaching matrix with survey data
# RMM, 9 Apr 2021

import numpy as np
import pandas as pd
import bbedata as bbe

# Read the current teaching matrix
teaching_df = pd.read_excel("BBE Teaching Matrix.xlsx", header=1)
teaching_df = teaching_df.astype(
    {col: object for col in bbe.preference_strings})

# Read the survey data
survey_df = bbe.load_teaching_survey(
    "BBE Teaching Interest Survey, 2021-22 (Responses).xlsx")

# Update the teaching matrix with survey information
bbe.update_teaching_matrix(teaching_df, survey_df)

# Write the updated teaching matrix
teaching_df.to_excel("BBE Teaching Matrix Updated.xlsx", "Courses")

