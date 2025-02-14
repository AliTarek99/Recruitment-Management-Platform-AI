CV_EMBEDDING_PROMPT='''You are an expert in analyzing candidate CVs to assess skill proficiency. Given a CV and a list of extracted skills, evaluate the candidate’s experience in each skill and assign a rating from 1 (poor) to 5 (excellent) based on:
            - Years of experience
            - Projects or work history related to the skill
            - Certifications, courses, or achievements

            Return the result in the following **JSON format**:

            {
            "skills": {
                "Skill 1": rate,
                "Skill 2": rate
            }
            }

            **Rules:**
            - If the candidate has **no mention** of experience for a skill, rate it **1**.
            - If the skill is mentioned **briefly** or in a general context, rate it **2-3**.
            - If the candidate has **mid experience, projects**, rate it **4**.
            - If the candidate has **strong experience, projects, or certifications**, rate it **5**.
            - Write the JSON format without 'JSON' in the beginning.

            **Example Input:**
            ---
            CV:
            "I have been working as a Data Scientist for 5 years, primarily using Python and TensorFlow for Machine Learning. I also have experience with SQL databases and AWS cloud services. Recently, I completed a certification in NLP."

            Extracted Skills:
            ["Python", "Machine Learning", "SQL", "AWS", "NLP", "Deep Learning"]

            **Expected Output:**
            ---
            {
            "skills": {
                "Python": 5,
                "Machine Learning": 5,
                "SQL": 4,
                "AWS": 4,
                "NLP": 5,
                "Deep Learning": 2
            }
            }

            Now, analyze the following CV and extracted skills and return the JSON response.

            CV: \n'''
            

PROFILE_WEIGHING_PROMPT='''You are an expert in analyzing candidate CVs to assess skill proficiency. Given a CV, a list of extracted skills, Education as an array of dictionaries, and
            Experiences as an array of dictionaries, evaluate the candidate’s experience in each skill and assign a rating from 1 (poor) to 5 (excellent) based on:
            - Years of experience
            - Projects or work history related to the skill
            - Certifications, courses, or achievements

            Return the result in the following **JSON format**:

            {
            "skills": {
                "Skill 1": rate,
                "Skill 2": rate
            }
            }

            **Rules:**
            - If the candidate has **no mention** of experience for a skill, rate it **1**.
            - If the skill is mentioned **briefly** or in a general context, rate it **2-3**.
            - If the candidate has **mid experience, projects**, rate it **4**.
            - If the candidate has **strong experience, projects, and certifications**, rate it **5**.
            - Write the JSON format without 'JSON' in the beginning.
            - Look up the candidate's projects from the CV.
            - Look up the experience and education from both CV and the given list.
            - If the same experience/education is present in the CV and the list, consider only the one in the CV.
            - The output should be the JSON format only.

            **Example Input:**
            ---
            CV:
            "Assiut University, Faculty of Computers and Information, Egypt Aug 18 – Aug 22
            Bachelor's degree in bioinformatics.Overall Grade: 3.48 out of 4.0.
            I have worked as a Data Scientist at Microsoft for 5 years, primarily using Python and TensorFlow for Machine Learning. I also have experience with SQL databases and AWS cloud services. Recently, I completed a certification in NLP."

            Extracted Skills:
            ["Python", "Machine Learning", "SQL", "AWS", "NLP", "Deep Learning"]

            Extracted Experience:
            [{"company_name": "Microsoft",
            "start_date": "2020",
            "end_date": "2025",
            "description": "I have been working as a Data Scientist in Microsoft for 5 years, primarily using Python and TensorFlow for Machine Learning.",
            "job_title": "Data Scientist"}]

            Extracted Education:
            [{"school_name": "Assiut University",
            "field": "Faculty of Computers and Information",
            "degree": "Bachelor's degree in bioinformatics",
            "grade": "3.48"}]

            **Expected Output:**
            ---
            {
            "skills": {
                "Python": 5,
                "Machine Learning": 5,
                "SQL": 4,
                "AWS": 4,
                "NLP": 5,
                "Deep Learning": 2
            }
            }

            Now, analyze the following CV and extracted skills and return the JSON response.

            CV: \n'''
            
            
CV_TYPE='cv'
JOB_TYPE='job'
PROFILE_TYPE='profile'