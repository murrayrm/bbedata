# bbedata.py - tools for reaching and processing BBE data
# RMM, 21 Mar 2021

import pandas as pd
import numpy as np
import re
import warnings
from html.parser import HTMLParser
from math import nan

# Module version number
__version__ = '1.0.0'

# Faculty name aliases
faculty_aliases = [
    (r"(^[a-zA-Z]+) ([^,]+)$", r"\2, \1"),              # last, first
    (r"([a-zA-Z \-]*), ([\S]+) [\S]+", r"\1, \2"),      # first names only
    (r"Bronner .*, Marianne", "Bronner, Marianne"),
    (r"Campbell, Judith", "Campbell, Judy"),
    (r"Dunphy, William", "Dunphy, Bill"),
    (r"Guttman, Mitchell", "Guttman, Mitch"),
    (r"Hong, Elizabeth", "Hong, Betty"),
    (r"Mayo, Stephen", "Mayo, Steve"),
    (r"Meyerowitz, Elliott", "Meyerowitz, Elliot"),
    (r"Phillips, Robert", "Phillips, Rob"),
    (r"Shimojo, Shinsuke", "Shimojo, Shin"),
    (r"Siapas, Athanassios", "Siapas, Thanos"),
    (r"Thanos, Siapas", "Siapas, Thanos"),
    (r"Stathopoulos, Angelike", "Stathopoulos, Angela"),
    (r"Van Valen, David", "Van Valen, Dave"),
    (r"Varshavsky, Alexander", "Varshavsky, Alex"),
    (r"Zernicka-Goetz, Magdalena", "Zernicka-Goetz, Magda"),
    (r"Fejes-Toth, Katalin", "Fejes-Toth, Kata"),
    (r"Yui, Mary.*", "Yui, Mary"),
]

# Normalize faculty names
def normalize_name(full_name, aliases=faculty_aliases, last_name_only=False):
    for rule in aliases:
        full_name = re.sub(*rule, full_name.strip())
    if last_name_only:
        full_name = re.sub(r"(.*), (.*)", r"\1", full_name)
    return full_name

# Create a (normalized) faculty name
def create_name(last_name, first_name, aliases=faculty_aliases):
    full_name = "%s, %s" % (last_name, first_name)
    return normalize_name(full_name, aliases=aliases)


# Function to create data frame with faculty information
def load_faculty_data(filename="BBE Faculty.xlsx", affiliated=None):
    # Tenure track faculty
    tenure_track = pd.read_excel(filename, "Tenure Track")

    # Create a new entry for the full name
    tenure_track = tenure_track.assign(Name=None, Rank=None)
    
    for id, entry in tenure_track.iterrows():
        if pd.isnull(entry['Last Name']) or pd.isnull(entry['First Name']):
            continue

        # Set the name
        full_name = create_name(entry['Last Name'], entry['First Name'])
        tenure_track.at[id, 'Name'] = full_name
    
        # Set the rank
        if entry['Tenure date'] == pd.NaT:
            tenure_track.at[id, 'Rank'] = 'Assistant Professor'
        else:
            tenure_track.at[id, 'Rank'] = 'Professor'

    # Save the entries that have a name assigned
    faculty_data = tenure_track[tenure_track['Name'] != None]

    # Non-tenure track faculty
    non_tenure_track = pd.read_excel(filename, "Non-Tenure track")
    non_tenure_track = non_tenure_track.assign(Name=None, Rank=None)
    for id, entry in non_tenure_track.iterrows():
        if pd.isnull(entry['Last Name']) or pd.isnull(entry['First Name']):
            continue

        # Set the name
        full_name = create_name(entry['Last Name'], entry['First Name'])
        non_tenure_track.at[id, 'Name'] = full_name

        # Set the rank
        non_tenure_track.at[id, 'Rank'] = re.sub(
            r"(.* Professor).*", r"\1", entry['Functional Job Title'])

    # Save the entries that have a name assigned
    faculty_data = faculty_data.append(
        non_tenure_track[non_tenure_track['Name'] != None])
    
    # Affiliated faculty
    if affiliated is not None:
        raise NotImpelementedError("Affiliated faculty not yet supported")

    return faculty_data

#
# Class used to parse Caltech catalog entries
#
# This class is used to read data from a Caltech catalog page and create a
# data frame with all of the course information.
#
# Each course in the Caltech catalog is inside a <div> tag with
# class="course-desription " (trailing space is stripped by the code). Inside
# that <div> there are <span> tags with the course data.  We use a dictionary
# to keep track of all entries we want to parse and eventually create a data
# frame that has all of the catalog information.
#

# Utility function to create a dataframe for courses
def create_course_dataframe(data=None):
    return pd.DataFrame(data, columns=[
        "ID", "Course", "Title", "Sections", "Instructors", "AY",
        "Term", "Enrollment",
        "Type", "Units", "Terms", "Description", "Prerequisites"])

# Dictionary of information that we want to store
catalog_data_dict = {
    "course-description__label": 'Course',
    "course-description__title": 'Title',
    "course-description__units": 'Units',
    "course-description__terms": 'Terms',
    "course-description__prerequisites": 'Prerequisites',
    "course-description__description": 'Description',
    "course-description__instructors": 'Instructors',
}

# 
class CaltechCatalogParser(HTMLParser):
    def __init__(self):
        super(CaltechCatalogParser, self).__init__()
        
        # Create a dataframe for holding the information
        self.courses = create_course_dataframe()

        # Keep track of the parser state
        self.div_class = None
        self.span_class = None

    # Process course data so that it has a uniform style
    def _process_course_data(self):
        # Get rid of trailing periods in selected entries
        for key in ['Title', 'Prerequisites']:
            if self.course_data.get(key):
                self.course_data[key] =self.course_data[key].strip(" .")

        # Remove header and extraneous info from prerequisites
        if self.course_data.get('Prerequisites'):
            # Find all BBE courses in the list
            prereqs = re.findall(
                # r'\S*([/]*(:?BE|Bi|BMB|CNS|NB)[/]*\s[0-9]\s*+[abcdx]*)',
                r'((?:BE|Bi|BMB|CNS|NB)[^ ]*\s[0-9]+\s*[abcdx]*)',
                self.course_data['Prerequisites'])

            # Get rid of spaces between course number and letter (a, b, c)
            for i, s in enumerate(prereqs):
                prereqs[i] = re.sub(r'(.*) ([abcdx]+)', r'\1\2', s)

            # Save as a comma separated list
            self.course_data['Prerequisites'] = ", ".join(prereqs)

    def handle_starttag(self, tag, attrs):
        # print("Encountered a start tag:", tag, attrs)
        
        # Convert the attributes to a dictionary to simplify things
        attrs = dict(attrs)

        # Look for the start of a course description
        if tag == "div" and attrs.get('class').strip() == "course-description":
            # Save the course ID
            self.div_class = attrs['id']

            # Initialize a dictionary to handle the course data
            self.course_data = {}
            self.course_data['ID'] = attrs['id']

        # See if we recognize an entry for course data
        if self.div_class is not None and tag == "span" and \
           attrs.get('class') in catalog_data_dict.keys():
            self.span_class = catalog_data_dict[attrs.get('class')]

    def handle_endtag(self, tag):
        # print("Encountered an end tag :", tag)
        if tag == "span":
            self.span_class = None
        if tag == "div" and self.div_class:
            self._process_course_data()
            self.courses = self.courses.append(
                self.course_data, ignore_index=True)
            self.div_class = None

    def handle_data(self, data):
        if self.span_class:
            self.course_data[self.span_class] = data
        

# Function to read a catalog entry
def read_catalog_section(filename):
    # Create the parser
    parser = CaltechCatalogParser()

    # Open the file
    with open(filename) as f:
        page = f.read()

    # Parse the contents
    parser.feed(page)
    
    return parser.courses


# Function to read REGIS spreadsheet
def read_regis_data(
        filename, options=['BE', 'Bi', 'BMB', 'CNS', 'NB'],
        last_name_only=False, verbose=False):
    # Read the data from the registrar
    regis_data = pd.read_excel(filename)

    # Create a regular expression for matching courses
    course_pattern = re.compile(r".*(" + "|".join(options) + r")+.*")

    # Initialize variables we will use in parsing spreadsheet entries
    course_list, label, course_data = [], None, None

    # Go through each line in the spreadsheet
    for index, entry in regis_data.iterrows():
        # Make sure this is a course we care about
        if course_pattern.match(entry["OFFERING_NAME"]) is None:
            continue

        # See if this is a repeated course entry
        if entry["OFFERING_NAME"] == label:
            repeat = True
            if verbose: print(".", end='')
                
            # Add instructor to the list of instructors
            if instructors:
                instructors.add(normalize_name(
                    entry["INSTRUCTOR"], last_name_only=last_name_only))
            else:
                warnings.warn("repeat course with no prior instructor (?)")
            
            # If this is a new section, add up enrollments
            if section != entry["SECTION"]:
                enrolled += int(entry["NUM_ENROLLED"])
                section = entry["SECTION"]      # keep track of new section
                sections += 1

                # Let the operator know we read a section entry
                if verbose: print("s", end='')
            else:
                # Same section => co-instructor (don't recount enrollment)
                if verbose: print("i", end='')
            
        else:
            repeat = False
            
            # Generate newline for verbose listing of previous entry
            if label and verbose: print("]")
        
            # Extract the information about the course
            term_year = entry["TERM_NAME"]
            label = entry["OFFERING_NAME"]
            title = entry["OFFERING_TITLE"]
            section, sections = entry["SECTION"], 1     # track id & count
            instructors = {normalize_name(              # store as set
                entry["INSTRUCTOR"], last_name_only=last_name_only)}  
            enrolled = int(entry["NUM_ENROLLED"])
            research = entry["Research"] == 'Y'
            option = entry["DEPARTMENT_NAME"]
            division = re.sub("Bi", "BBE", entry["DIVISION"])

            # If verbose, print course name
            if verbose: print("Found %s, %s [" % (label, term), end='') 

        # Find the term and year
        m = re.search(r"(FA|WI|SP|SU)\s*([0-9]+-[0-9]+)", term_year)
        if m is None:
            warnings.warn("%s: couldn't parse term: %s" % (label, term))
        else:
            term = m.group(1)
            year = m.group(2)

        # Normalize the course name
        m = re.search(r"([^0-9\s]+)\s*([0-9]+)\s*([a-zA-Z]*)", label)
        if m is None:
            warnings.warn("Couldn't parse course: %s" % label)
            course_id = label
        else:
            course_id = "%s %d%s" % (m.group(1), int(m.group(2)), m.group(3))

        if repeat:
            # Update appropriate entries
            course_list[-1]['Sections'] = sections
            course_list[-1]['Enrollment'] = enrolled
            if instructors:
                course_list[-1]['Instructors'] = "; ".join(instructors)
        else:
            # Add the course to the dataframe
            course_list.append({
                'Course': course_id, 'Title': title, 'Sections': sections,
                'Instructors': "; ".join(instructors),
                'Type': 'Research' if research else '',
                'AY': year, 'Term': term, 'Enrollment': enrolled,
            })

    # Generate newline for verbose listing of previous entry
    if label and verbose: print("]")

    courses = create_course_dataframe(course_list)

    return courses

# Keep track of preference types
preference_strings = ["Next", "Future", "Help", "Change", "Again"]

# Read in teaching survey
def load_teaching_survey(filename):
    # Read the survey data
    survey_df = pd.read_excel(filename)

    # Rename the columns to just be the courses
    course_pattern = re.compile(r".* \[([^-]+) - .*\]")
    for index, name in enumerate(survey_df.columns):
        m = course_pattern.search(name)
        if m is not None:
            survey_df.rename(columns={name: m.group(1)}, inplace=True)

    # Simplify the entries to a single word
    replacements = np.array([
        [r"Would like to teach this course next year", "Next"],
        [r"Interested in teaching this course at some point", "Future"],
        [r"Have some expertise .* willing to share", "Help"],
        [r"Currently teaching, .* would like to teach other courses", "Change"],
        [r"Have taught in the past, would like to teach again", "Again"]
    ])
    survey_df.replace(
        replacements[:, 0].tolist(), replacements[:, 1].tolist(),
        inplace=True, regex=True)
    
    return survey_df

# Update teaching matrix with new data
def update_teaching_matrix(teaching_df, survey_df, verbose=False):
    """Update an existing teaching matrix with new data, by course number.

    This function takes a dataframe corresponding to a teaching matrix and
    updates the columns based on data from a new dataframe.  The main purpose
    is to add data that come in from other sources (eg, the teaching survey).

    """
    # Go through all of the courses in the original teaching matrix
    for index, course in teaching_df.iterrows():
        # Get the course prefix from teaching matrix, strip leading 0's, term
        teaching_name = course[('Course')]
        if not isinstance(teaching_name, str):
            if verbose:
                print("Missing course name at line", index)
            continue
        teaching_prefix = re.sub(
            r"(\S*) 0*([1-9][0-9X]*).*", r"\1 \2", teaching_name)

        # Get course suffix, if any
        m = re.match(r"\S* [0-9X]+([a-dA-D]+).*", teaching_name)
        teaching_suffix = m.group(1) if m else None
        if verbose:
            print("Looking for", teaching_prefix, teaching_suffix)

        # See if we can find a matching entry in the survey
        course_name = None
        for survey_name in survey_df.columns:
            survey_prefix = re.sub(
                r"(\S*) 0*([1-9][0-9X]*).*", r"\1 \2", survey_name)
            m = re.match(r"\S* [0-9X]+([a-dA-D]+).*", survey_name)
            survey_suffix = m.group(1) if m else None
            
            if survey_prefix == teaching_prefix:
                # See whether this is a multi-term course listing
                if teaching_suffix is not None and len(teaching_suffix) > 0:
                    # Check to see if we match the term properly
                    if teaching_suffix not in survey_suffix:
                        continue
                    
                # Found a match
                course_name = survey_name
                break

        # Make sure we found a matching course
        if course_name is None:
            if verbose:
                print("Skipping", teaching_name)
            continue

        # Make sure that someone had a preference
        if survey_df[course_name].isnull().all():
            if verbose:
                print("No prefs", course_name)
            continue
        
        # Find people who want to teach this course next year
        for pref in preference_strings:
            names = survey_df[
                (survey_df[course_name].str.contains(pref, na=False))
            ]['Name'].unique()

            # Normalize the names (last names only, upper case)
            name_rules = [
                (r"[\S]+\s+([\S]+)", r"\1"),
                (r"[\S]* *[A-Z]\. *([\S]+)", r"\1"),
                (r"[\S]* Van *([\S]+)", r"Van \1"),
            ]
            for i, name in enumerate(names):
                for rule in name_rules:
                    name = re.sub(rule[0], rule[1], name)
                names[i] = name.strip().capitalize()
                
            if verbose:
                print(teaching_name, pref, ":", names)
            teaching_df.at[index, pref] = "; ".join(names)
